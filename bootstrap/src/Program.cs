using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace Astra.Bootstrap;

internal static class Program
{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBoxW(IntPtr window, string text, string title, uint type);
    private static string? logFile;
    private static void Log(string text)
    {
        // Curated metadata only. Never dump environment, credentials, URLs with signed queries or child streams.
        if (logFile != null) File.AppendAllText(logFile, $"{DateTimeOffset.UtcNow:O} {text}{Environment.NewLine}");
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string stage = "SYSTEM";
        try
        {
            if (!OperatingSystem.IsWindowsVersionAtLeast(10, 0, 19041) || RuntimeInformation.OSArchitecture != Architecture.X64)
                throw new InvalidOperationException("This distribution requires Windows x64, version 10 build 19041 or newer. Actual production minimum requirements remain subject to release validation.");
            if (args.Length > 1 || (args.Length == 1 && args[0] is not ("--update" or "--rollback"))) throw new InvalidOperationException("Only --update and --rollback are supported.");
            string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ASTRA COSMOS");
            Policy.NoLinks(root);
            Directory.CreateDirectory(root);
            foreach (string area in new[] { "logs", "versions", "staging", "userdata" }) Policy.NoLinks(Path.Combine(root, area));
            Directory.CreateDirectory(Path.Combine(root, "logs"));
            logFile = Path.Combine(root, "logs", "astra_bootstrap.log");
            Log("Bootstrap started; Windows=" + Environment.OSVersion.Version + "; x64; state directory=" + root);
            // One install/update/game session at a time. OS releases this on crash; no stale PID lock.
            using var session = new FileStream(Path.Combine(root, "session.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
            string current = Path.Combine(root, "current.json");
            Release? installed = null;
            stage = "INSTALLED_RUNTIME";
            if (File.Exists(current) && !args.Contains("--rollback")) installed = Policy.Load(current);
            Release selected;
            bool commit = false;
            if (args.Contains("--rollback"))
            {
                selected = Policy.Load(Path.Combine(root, "previous.json"));
                Installer.ValidateInstalled(Installer.DirectoryFor(root, selected), selected);
                commit = true;
            }
            else if (installed != null && !args.Contains("--update"))
                selected = installed; // OFFLINE: no catalog request, no download, no Supabase check.
            else
            {
                stage = "RELEASE_CATALOG";
                // Catalog ships with the trusted bootstrap ZIP; no unsigned remote 'latest' feed.
                selected = Policy.Load(Path.Combine(AppContext.BaseDirectory, "bootstrap", "release.json"));
                if (installed != null)
                {
                    int order = Version.Parse(selected.Version!).CompareTo(Version.Parse(installed.Version!));
                    if (order < 0) throw new InvalidOperationException("Update catalog would downgrade ASTRA. Use the explicit rollback option for the previous installed release.");
                    if (order == 0 && selected.Sha256 != installed.Sha256) throw new InvalidOperationException("A published runtime version must not change its content hash.");
                }
                commit = installed == null || installed.Sha256 != selected.Sha256;
            }
            string directory = Installer.DirectoryFor(root, selected);
            stage = "RUNTIME_INSTALL";
            if (!Directory.Exists(directory))
                directory = Installer.Prepare(root, selected, Log).GetAwaiter().GetResult();
            Installer.ValidateInstalled(directory, selected);
            stage = "SYSTEM_DRIVER";
            if (!File.Exists(Path.Combine(Environment.SystemDirectory, "vulkan-1.dll")))
                throw new InvalidOperationException("The system Vulkan loader was not found. Install/update the official GPU manufacturer's driver. Do not install development SDKs to run ASTRA.");
            Log("System Vulkan loader file exists; actual GPU compatibility must be verified by the production runtime.");
            string data = Path.Combine(root, "userdata");
            foreach (string name in new[] { "config", "saves", "screenshots", "recordings", "scenarios" }) Directory.CreateDirectory(Path.Combine(data, name));
            // Writable state outside immutable version dirs. Production integration must honor this contract.
            string nonce = Guid.NewGuid().ToString("N");
            string health = Path.Combine(root, "logs", "ready-" + nonce + ".json");
            var info = new ProcessStartInfo(Path.Combine(directory, selected.EntryPoint!)) {
                WorkingDirectory = directory, UseShellExecute = false, CreateNoWindow = true
            };
            info.Environment["ASTRA_USER_DATA"] = data;
            info.Environment["ASTRA_READY_FILE"] = health;
            info.Environment["ASTRA_READY_NONCE"] = nonce;
            // Prevent global Python variables altering an embedded runtime. Payload must use isolated Python APIs.
            info.Environment.Remove("PYTHONPATH");
            info.Environment.Remove("PYTHONHOME");
            info.Environment["PYTHONNOUSERSITE"] = "1";
            stage = "PROCESS_CREATED";
            using var process = Process.Start(info) ?? throw new IOException("Windows did not create the ASTRA runtime process.");
            Log("PROCESS_CREATED PID=" + process.Id + "; version=" + selected.Version + "; entry=" + info.FileName);
            bool ready = false;
            var elapsed = Stopwatch.StartNew();
            try
            {
                stage = "RUNTIME_INITIALIZATION";
                while (!process.HasExited && elapsed.Elapsed < TimeSpan.FromSeconds(90))
                {
                    if (File.Exists(health))
                    {
                        try
                        {
                            if (new FileInfo(health).Length > 4096) throw new InvalidDataException("Readiness record too large.");
                            using var json = JsonDocument.Parse(File.ReadAllText(health));
                            var e = json.RootElement;
                            ready = e.GetProperty("protocol").GetInt32() == 1 && e.GetProperty("nonce").GetString() == nonce &&
                                e.GetProperty("stage").GetString() == "ASTRA_READY" && e.GetProperty("renderer").GetString() == "real-vulkan" &&
                                e.GetProperty("science").GetString() == "connected" && e.GetProperty("presented_frames").GetInt64() >= 1;
                            if (!ready) throw new InvalidDataException("Runtime did not attest real rendering and scientific integration.");
                            break;
                        }
                        catch (JsonException) { /* A partial readiness write is retried, never treated as success. */ }
                        catch (IOException) { /* Runtime may still hold its readiness file. */ }
                    }
                    Thread.Sleep(100);
                }
                if (!ready || process.HasExited)
                {
                    string detail = process.HasExited ? $"Runtime exited before readiness; code {process.ExitCode} (0x{unchecked((uint)process.ExitCode):X8})." : "Runtime did not establish readiness within 90 seconds.";
                    throw new InvalidOperationException(detail + " Previous runtime selection and user data are unchanged.");
                }
                Log("Runtime reported ASTRA_READY via the required contract. This is not independent GPU certification.");
                stage = "ACTIVATE_VERSION";
                if (commit) Installer.Commit(root, selected);
                stage = "RUNTIME";
                process.WaitForExit();
                Log($"Runtime exited; code={process.ExitCode}; lifetime_seconds={elapsed.Elapsed.TotalSeconds:F1}.");
                if (process.ExitCode != 0) throw new InvalidOperationException($"ASTRA exited with code {process.ExitCode} (0x{unchecked((uint)process.ExitCode):X8}). Use --rollback if a new version fails.");
                return 0;
            }
            finally
            {
                if (!process.HasExited) { process.Kill(true); process.WaitForExit(); }
                if (File.Exists(health)) File.Delete(health);
            }
        }
        catch (Exception error)
        {
            string detail = error is System.ComponentModel.Win32Exception w ? $"{w.Message} (Windows error {w.NativeErrorCode})" : error.Message;
            try { Log("FAILED stage=" + stage + "; " + detail); } catch { /* Preserve original failure if disk logging is unavailable. */ }
            string message = "ASTRA COSMOS could not start.\n\nProblem:\nThe ASTRA runtime could not be prepared or launched.\n\nStage:\n" + stage + "\n\nDetails:\n" + detail + "\n\nRecommended action:\nClose another running ASTRA session if present. Check your connection for first setup; obtain a trusted ASTRA release if files are missing or invalid. Your saves are not deleted.\n\nLog:\n" + (logFile ?? "Unavailable before startup log creation.");
            if (OperatingSystem.IsWindows()) MessageBoxW(IntPtr.Zero, message, "ASTRA COSMOS", 0x10);
            else Console.Error.WriteLine(message);
            return 1;
        }
    }
}
