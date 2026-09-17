using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Astra.Bootstrap;

internal sealed record PayloadFile(string Path, long Size, string Sha256);
internal sealed record Release(int Schema, string State, string? Reason, string? Version,
    string? Url, long Size, string? Sha256, string? EntryPoint, string? Python,
    List<PayloadFile>? Files);

internal static class Policy
{
    internal const long MaxArchive = 4L * 1024 * 1024 * 1024;
    internal const long MaxExpanded = 12L * 1024 * 1024 * 1024;
    internal static readonly JsonSerializerOptions Json = new() { PropertyNameCaseInsensitive = true };
    private static readonly Regex Hash = new("^[a-f0-9]{64}$");
    private static readonly Regex Semver = new(@"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$");
    private static readonly HashSet<string> Forbidden = new(StringComparer.OrdinalIgnoreCase) {
        "cmake.exe", "msbuild.exe", "cl.exe", "ninja.exe", "git.exe", "vulkaninfo.exe",
        "glslangvalidator.exe", "glslc.exe", "pip.exe", "conan.exe", "vcpkg.exe"
    };

    internal static Release Load(string file)
    {
        if ((File.GetAttributes(file) & FileAttributes.ReparsePoint) != 0) throw new IOException("Linked release metadata is prohibited.");
        if (new FileInfo(file).Length > 8 * 1024 * 1024) throw new InvalidDataException("Release metadata is oversized.");
        var r = JsonSerializer.Deserialize<Release>(File.ReadAllText(file), Json)
            ?? throw new InvalidDataException("Release metadata is empty.");
        Validate(r);
        return r;
    }

    internal static void Validate(Release r)
    {
        if (r.Schema != 1) throw new InvalidDataException("Unsupported release metadata version.");
        if (r.State == "blocked") throw new InvalidDataException("No verified Windows runtime is published for this distribution. Obtain an official ASTRA release when available.");
        if (r.State != "ready" || r.Version is null || !Semver.IsMatch(r.Version)) throw new InvalidDataException("Invalid runtime version/state.");
        if (r.EntryPoint != "ASTRA COSMOS.exe" || r.Sha256 is null || !Hash.IsMatch(r.Sha256)) throw new InvalidDataException("Invalid executable or archive checksum.");
        if (r.Python is not ("none" or "embedded")) throw new InvalidDataException("Runtime Python strategy is unspecified.");
        if (r.Size <= 0 || r.Size > MaxArchive) throw new InvalidDataException("Archive size is outside release limits.");
        if (!Uri.TryCreate(r.Url, UriKind.Absolute, out var uri) || uri.Scheme != "https" || uri.Host != "github.com" || !uri.IsDefaultPort || uri.UserInfo != "" || uri.Query != "" || uri.Fragment != "") throw new InvalidDataException("Untrusted release URL.");
        string expected = $"/luckygtr2023-bit/ASTRA-COSMOS-/releases/download/v{r.Version}/ASTRA-Windows-x64-Runtime.zip";
        if (uri.AbsolutePath != expected) throw new InvalidDataException("Release URL does not match its pinned version.");
        if (r.Files is null || r.Files.Count is < 1 or > 50000) throw new InvalidDataException("Invalid payload inventory.");
        var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        long total = 0;
        foreach (var f in r.Files)
        {
            SafePath(f.Path);
            if (!paths.Add(f.Path) || f.Size < 0 || !Hash.IsMatch(f.Sha256)) throw new InvalidDataException("Invalid or duplicate payload file.");
            total = checked(total + f.Size);
            if (total > MaxExpanded) throw new InvalidDataException("Expanded runtime exceeds size limit.");
        }
        if (!paths.Contains(r.EntryPoint)) throw new InvalidDataException("Application executable is missing from inventory.");
        foreach (var path in paths)
        {
            var parts = path.Split('/');
            for (int i = 1; i < parts.Length; ++i)
                if (paths.Contains(string.Join('/', parts.Take(i)))) throw new InvalidDataException("File/directory collision in inventory.");
        }
    }

    internal static void SafePath(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || path.Length > 200 || path.Contains('\\') || path.StartsWith('/')) throw new InvalidDataException("Unsafe archive path.");
        foreach (string part in path.Split('/'))
        {
            if (part.Length == 0 || part is "." or ".." || part.EndsWith('.') || part.EndsWith(' ') || part.Any(c => c < 32 || c > 126 || ":<>\"|?*".Contains(c))) throw new InvalidDataException("Unsafe archive path component.");
            if (part.Equals(".git", StringComparison.OrdinalIgnoreCase) || part.Equals(".env", StringComparison.OrdinalIgnoreCase) || part.StartsWith(".env.", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Repository credentials/environment files must not be packaged.");
            string stem = part.Split('.')[0];
            if (Regex.IsMatch(stem, @"^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])$", RegexOptions.IgnoreCase)) throw new InvalidDataException("Reserved Windows filename.");
        }
        string name = path.Split('/').Last();
        if (Forbidden.Contains(name) || new[] { ".bat", ".cmd", ".ps1", ".lnk", ".url" }.Contains(System.IO.Path.GetExtension(name).ToLowerInvariant())) throw new InvalidDataException("Development tool or executable script in runtime payload.");
    }

    internal static string Digest(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    internal static void NoLinks(string path)
    {
        for (var info = new DirectoryInfo(System.IO.Path.GetFullPath(path)); info != null; info = info.Parent)
            if (info.Exists && (info.Attributes & FileAttributes.ReparsePoint) != 0) throw new IOException("Runtime paths must not use junctions or symbolic links.");
    }

    internal static void CheckPe(string path)
    {
        using var stream = File.OpenRead(path);
        using var reader = new BinaryReader(stream);
        if (stream.Length < 256 || reader.ReadUInt16() != 0x5a4d) throw new InvalidDataException("Runtime binary is not Windows PE.");
        stream.Position = 60;
        uint offset = reader.ReadUInt32();
        if (offset > stream.Length - 26) throw new InvalidDataException("Invalid Windows PE header.");
        stream.Position = offset;
        if (reader.ReadUInt32() != 0x4550 || reader.ReadUInt16() != 0x8664) throw new InvalidDataException("Runtime binary is not Windows x64.");
        stream.Position = offset + 22;
        ushort flags = reader.ReadUInt16();
        if ((flags & 2) == 0 || reader.ReadUInt16() != 0x20b) throw new InvalidDataException("Invalid PE32+ image.");
        if (System.IO.Path.GetExtension(path).Equals(".exe", StringComparison.OrdinalIgnoreCase) && (flags & 0x2000) != 0) throw new InvalidDataException("DLL supplied as application executable.");
    }
}
