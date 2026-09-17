using System.IO.Compression;
using System.Net;
using System.Net.Http;
using System.Text.Json;

namespace Astra.Bootstrap;

internal static class Installer
{
    internal static async Task Download(Release release, string output)
    {
        using var handler = new HttpClientHandler { AllowAutoRedirect = false, AutomaticDecompression = DecompressionMethods.None, UseCookies = false };
        using var client = new HttpClient(handler) { Timeout = TimeSpan.FromMinutes(15) };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("ASTRA-Bootstrap/1.0");
        Uri uri = new(release.Url!);
        for (int hop = 0; hop <= 5; hop++)
        {
            if (uri.Scheme != "https" || !uri.IsDefaultPort || uri.UserInfo != "" || uri.Fragment != "" || !(uri.Host == "github.com" || uri.Host == "release-assets.githubusercontent.com")) throw new IOException("Release download redirected to an untrusted host.");
            using var response = await client.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead);
            if ((int)response.StatusCode is 301 or 302 or 303 or 307 or 308)
            {
                if (response.Headers.Location is null) throw new IOException("Release redirect has no destination.");
                uri = new Uri(uri, response.Headers.Location);
                continue;
            }
            response.EnsureSuccessStatusCode();
            if (response.Content.Headers.ContentLength is long size && size != release.Size) throw new IOException("Release download size differs from pinned metadata.");
            using var deadline = new CancellationTokenSource(TimeSpan.FromMinutes(15));
            await using var source = await response.Content.ReadAsStreamAsync(deadline.Token);
            await using var destination = new FileStream(output, FileMode.CreateNew, FileAccess.Write, FileShare.None);
            await CopyExact(source, destination, release.Size, deadline.Token);
            return;
        }
        throw new IOException("Too many release redirects.");
    }

    private static async Task CopyExact(Stream source, Stream target, long expected, CancellationToken ct = default)
    {
        byte[] buffer = new byte[128 * 1024];
        long count = 0;
        int n;
        while ((n = await source.ReadAsync(buffer, ct)) > 0)
        {
            count = checked(count + n);
            if (count > expected) throw new InvalidDataException("Payload exceeds pinned size.");
            await target.WriteAsync(buffer.AsMemory(0, n), ct);
        }
        if (count != expected) throw new InvalidDataException("Payload is truncated.");
        await target.FlushAsync(ct);
    }

    internal static string DirectoryFor(string root, Release r) => Path.Combine(root, "versions", r.Version + "-" + r.Sha256);

    internal static void ValidateInstalled(string directory, Release r)
    {
        Policy.Validate(r);
        Policy.NoLinks(directory);
        var expected = r.Files!.ToDictionary(f => f.Path, StringComparer.OrdinalIgnoreCase);
        // Do not follow reparse points while enumerating the version tree.
        var options = new EnumerationOptions { RecurseSubdirectories = true, AttributesToSkip = 0, IgnoreInaccessible = false };
        foreach (var entry in Directory.EnumerateFileSystemEntries(directory, "*", options))
        {
            if ((File.GetAttributes(entry) & FileAttributes.ReparsePoint) != 0) throw new IOException("Linked payload entry rejected.");
            if (Directory.Exists(entry)) continue;
            string relative = Path.GetRelativePath(directory, entry).Replace('\\', '/');
            if (!expected.Remove(relative, out var record)) throw new IOException("Unexpected file in installed runtime.");
            if (new FileInfo(entry).Length != record.Size || Policy.Digest(entry) != record.Sha256) throw new IOException("Installed runtime integrity check failed; obtain a fresh verified release.");
            if (new[] { ".exe", ".dll", ".pyd" }.Contains(Path.GetExtension(entry).ToLowerInvariant())) Policy.CheckPe(entry);
        }
        if (expected.Count != 0) throw new IOException("Installed runtime is incomplete.");
    }

    internal static async Task<string> Prepare(string root, Release release, Action<string> log)
    {
        string final = DirectoryFor(root, release);
        if (Directory.Exists(final)) { ValidateInstalled(final, release); return final; }
        string work = Path.Combine(root, "staging", Guid.NewGuid().ToString("N"));
        Policy.NoLinks(root);
        Directory.CreateDirectory(work);
        string zip = Path.Combine(work, "download.zip");
        string payload = Path.Combine(work, "payload");
        Directory.CreateDirectory(payload);
        try
        {
            log("Downloading pinned runtime " + release.Version + ". No build tools are used.");
            await Download(release, zip);
            if (Policy.Digest(zip) != release.Sha256) throw new IOException("Downloaded runtime SHA-256 differs from trusted metadata.");
            using (var archive = ZipFile.OpenRead(zip))
            {
                var expected = release.Files!.ToDictionary(f => f.Path, StringComparer.OrdinalIgnoreCase);
                if (archive.Entries.Count != expected.Count) throw new InvalidDataException("Archive inventory mismatch.");
                foreach (var entry in archive.Entries)
                {
                    Policy.SafePath(entry.FullName);
                    int kind = (entry.ExternalAttributes >> 16) & 0xf000;
                    if (kind is not (0 or 0x8000) || (entry.ExternalAttributes & 0x400) != 0) throw new InvalidDataException("Archive links or special files are prohibited.");
                    if (!expected.Remove(entry.FullName, out var record) || record.Path != entry.FullName || entry.Length != record.Size) throw new InvalidDataException("Unexpected or duplicate archive entry.");
                    string path = Path.GetFullPath(Path.Combine(payload, entry.FullName));
                    if (!path.StartsWith(payload + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Archive traversal rejected.");
                    Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                    await using var input = entry.Open();
                    await using (var output = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                        await CopyExact(input, output, record.Size);
                    if (Policy.Digest(path) != record.Sha256) throw new InvalidDataException("Extracted file checksum mismatch.");
                }
            }
            ValidateInstalled(payload, release);
            Directory.CreateDirectory(Path.GetDirectoryName(final)!);
            Directory.Move(payload, final); // Same-volume immutable version; current remains unchanged.
            log("Pinned runtime extracted and validated. Application readiness is not established yet.");
            return final;
        }
        finally
        {
            // Only delete our own random staging directory. Never touch saves/config or old versions.
            try { Policy.NoLinks(work); Directory.Delete(work, true); }
            catch (IOException) { log("Temporary staging files retained; no active runtime was replaced."); }
        }
    }

    internal static void Commit(string root, Release release)
    {
        string temp = Path.Combine(root, "current-" + Guid.NewGuid().ToString("N") + ".json");
        string current = Path.Combine(root, "current.json");
        using (var file = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        {
            JsonSerializer.Serialize(file, release, Policy.Json);
            file.Flush(true);
        }
        if (File.Exists(current)) File.Replace(temp, current, Path.Combine(root, "previous.json"));
        else File.Move(temp, current);
    }
}
