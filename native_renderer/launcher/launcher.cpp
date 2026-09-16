// Copyright © 2026 Lucky Kumar — ASTRA COSMOS
// Windows/Linux launcher for ASTRA COSMOS — resolves install dir, validates runtime, launches native renderer
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include <filesystem>
#include <iostream>
#include <algorithm>

namespace fs = std::filesystem;

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#include <limits.h>
#include <sys/wait.h>
#include <cstring>
#endif

static fs::path getExecutableDir() {
#ifdef _WIN32
    char buf[MAX_PATH];
    DWORD len = GetModuleFileNameA(nullptr, buf, MAX_PATH);
    if (len==0 || len==MAX_PATH) return fs::current_path();
    return fs::path(std::string(buf)).parent_path();
#else
    char buf[PATH_MAX];
    ssize_t len = readlink("/proc/self/exe", buf, sizeof(buf)-1);
    if (len==-1) return fs::current_path();
    buf[len]='\0';
    return fs::path(std::string(buf)).parent_path();
#endif
}

static bool fileExists(const fs::path& p) {
    return fs::exists(p);
}

static std::vector<std::string> checkRequiredFiles(const fs::path& root) {
    std::vector<std::string> missing;
    // Required files relative to repository/release root
    // Check multiple candidate layouts (installed release vs developer checkout)
    // We check from root (exe dir) and root/.. and root/native_renderer etc.
    // For validation we require at least one layout to have critical files.
    // Here we test developer layout first, then release layout.
    std::vector<fs::path> candidates = {
        root / "native_renderer" / "shaders" / "common" / "common.glsl",
        root / ".." / "native_renderer" / "shaders" / "common" / "common.glsl",
        root / "shaders" / "common" / "common.glsl",
        fs::path("native_renderer/shaders/common/common.glsl")
    };
    bool foundShader = false;
    for(auto &c: candidates) if(fileExists(c)) { foundShader=true; break; }
    if(!foundShader) missing.push_back("shaders/common/common.glsl");

    // astra_native binary candidates
    std::vector<fs::path> nativeCandidates = {
        root / "native_renderer" / "astra_native",
        root / "bin" / "astra_native",
        root / ".." / "native_renderer" / "astra_native",
        root / "astra_native",
        fs::path("/tmp/astra_build/astra_native"),
        fs::path("native_renderer/build/astra_native"),
        fs::path("build/astra_native")
    };
#ifdef _WIN32
    // on Windows also check .exe
    std::vector<fs::path> withExe;
    for(auto &p: nativeCandidates) {
        withExe.push_back(p);
        withExe.push_back(fs::path(p.string() + ".exe"));
    }
    nativeCandidates = withExe;
#endif
    bool foundNative=false;
    for(auto &c: nativeCandidates) if(fileExists(c)) { foundNative=true; break; }
    if(!foundNative) missing.push_back("native_renderer/astra_native (or bin/astra_native, /tmp/astra_build/astra_native)");

    // assets check
    std::vector<fs::path> assetCandidates = {
        root / "native_renderer" / "assets" / "benchmark.json",
        root / ".." / "native_renderer" / "assets" / "benchmark.json",
        fs::path("native_renderer/assets/benchmark.json")
    };
    bool foundAsset=false;
    for(auto &c: assetCandidates) if(fileExists(c)) foundAsset=true;
    if(!foundAsset) missing.push_back("native_renderer/assets/benchmark.json");

    // python engine check (optional but warn)
    std::vector<fs::path> pyCandidates = {
        root / "astra" / "core" / "engine.py",
        root / ".." / "astra" / "core" / "engine.py",
        fs::path("astra/core/engine.py")
    };
    bool foundPy=false;
    for(auto &c: pyCandidates) if(fileExists(c)) foundPy=true;
    if(!foundPy) missing.push_back("astra/core/engine.py (Python engine)");

    return missing;
}

static fs::path locateNativeBinary(const fs::path& root) {
    std::vector<fs::path> candidates = {
        root / "bin" / "astra_native",
        root / "native_renderer" / "astra_native",
        root / ".." / "native_renderer" / "astra_native",
        root / "astra_native",
        fs::path("/tmp/astra_build/astra_native"),
        fs::path("native_renderer/build/astra_native"),
        fs::path("build/astra_native"),
        fs::path("./astra_native")
    };
#ifdef _WIN32
    std::vector<fs::path> withExe;
    for(auto &p: candidates) {
        withExe.push_back(p);
        if(p.extension() != ".exe") withExe.push_back(fs::path(p.string() + ".exe"));
    }
    candidates = withExe;
    // also check build/Release etc.
    candidates.push_back(root / "native_renderer" / "build" / "Release" / "astra_native.exe");
    candidates.push_back(root / "build" / "Release" / "astra_native.exe");
#endif
    for(auto &c: candidates) if(fileExists(c)) return fs::canonical(c);
    return {};
}

static int launchNative(const fs::path& binary, const std::vector<std::string>& args) {
    std::string cmd;
#ifdef _WIN32
    // Windows: quote binary path to handle spaces
    cmd = "\"" + binary.string() + "\"";
    for(size_t i=1;i<args.size();++i) {
        // quote arg if contains space
        std::string a = args[i];
        if(a.find(' ')!=std::string::npos || a.find('"')!=std::string::npos) {
            // simple quoting
            cmd += " \"" + a + "\"";
        } else {
            cmd += " " + a;
        }
    }
    std::printf("[Launcher] Executing: %s\n", cmd.c_str());
    // Use CreateProcess for better control, but system suffices for portability and preserves exit code via system()
    int ret = std::system(cmd.c_str());
    // system returns encoded; on Windows it's direct exit code
    return ret;
#else
    // Linux/macOS: fork/exec to preserve stdout/stderr and handle spaces via execv
    cmd = "\"" + binary.string() + "\"";
    for(size_t i=1;i<args.size();++i) cmd += " " + args[i];
    std::printf("[Launcher] Executing: %s\n", cmd.c_str());
    std::fflush(stdout);
    pid_t pid = fork();
    if(pid==0) {
        // child
        std::vector<char*> argv;
        argv.push_back(const_cast<char*>(binary.c_str()));
        for(size_t i=1;i<args.size();++i) argv.push_back(const_cast<char*>(args[i].c_str()));
        argv.push_back(nullptr);
        execv(binary.c_str(), argv.data());
        // if exec fails
        std::perror("execv");
        _exit(127);
    } else if(pid>0) {
        int status=0;
        waitpid(pid, &status, 0);
        if(WIFEXITED(status)) return WEXITSTATUS(status);
        if(WIFSIGNALED(status)) return 128 + WTERMSIG(status);
        return status;
    } else {
        std::perror("fork");
        return 2;
    }
#endif
}

int main(int argc, char* argv[]) {
    std::vector<std::string> args;
    for(int i=0;i<argc;++i) args.emplace_back(argv[i]);

    fs::path exeDir = getExecutableDir();
    // Also consider current working directory as fallback root for developer checkout
    fs::path cwd = fs::current_path();
    std::printf("[ASTRA COSMOS Launcher] v0.1.1 (ASTRA COSMOS) — Copyright © 2026 Lucky Kumar\n");
    std::printf("[Launcher] exeDir: %s\n", exeDir.string().c_str());
    std::printf("[Launcher] cwd: %s\n", cwd.string().c_str());

    // Check required files from exeDir, then cwd
    auto missingExeDir = checkRequiredFiles(exeDir);
    auto missingCwd = checkRequiredFiles(cwd);
    fs::path useRoot = exeDir;
    // Prefer exeDir if it has files, else cwd if cwd has fewer missing
    if(missingExeDir.size() > missingCwd.size()) {
        std::printf("[Launcher] exeDir missing %zu files, cwd missing %zu — using cwd as root\n", missingExeDir.size(), missingCwd.size());
        useRoot = cwd;
        missingExeDir = missingCwd;
    }

    if(!missingExeDir.empty()) {
        std::fprintf(stderr, "[Launcher] ERROR: Missing required runtime files (%zu):\n", missingExeDir.size());
        for(auto &m: missingExeDir) std::fprintf(stderr, "  - %s\n", m.c_str());
        std::fprintf(stderr, "[Launcher] Checked root: %s\n", useRoot.string().c_str());
        std::fprintf(stderr, "[Launcher] Please ensure ASTRA COSMOS is installed correctly and launch from its directory.\n");
        std::fprintf(stderr, "[Launcher] Tried locations: native_renderer/shaders/common/common.glsl, native_renderer/astra_native, native_renderer/assets/benchmark.json, astra/core/engine.py\n");
        // Do not require Python engine to be fatal if native binary exists; but warn
        bool hasNative = true;
        for(auto &m: missingExeDir) if(m.find("astra_native")!=std::string::npos) hasNative=false;
        if(!hasNative) {
            std::fprintf(stderr, "[Launcher] FATAL: native renderer binary not found — cannot launch.\n");
            return 1;
        } else {
            std::fprintf(stderr, "[Launcher] WARNING: some optional files missing but native binary found — continuing.\n");
        }
    } else {
        std::printf("[Launcher] All required files found under %s\n", useRoot.string().c_str());
    }

    fs::path nativeBin = locateNativeBinary(useRoot);
    if(nativeBin.empty()) {
        // try cwd again
        nativeBin = locateNativeBinary(cwd);
    }
    if(nativeBin.empty()) {
        std::fprintf(stderr, "[Launcher] ERROR: Could not locate native renderer binary 'astra_native' (searched bin/astra_native, native_renderer/astra_native, /tmp/astra_build/astra_native)\n");
        return 1;
    }
    std::printf("[Launcher] Found native binary: %s\n", nativeBin.string().c_str());

    // Security: verify binary is not in protected Windows directory requiring admin
#ifdef _WIN32
    std::string binStr = nativeBin.string();
    std::transform(binStr.begin(), binStr.end(), binStr.begin(), ::tolower);
    if(binStr.rfind("c:\\windows\\",0)==0 || binStr.rfind("c:\\program files\\windows",0)==0) {
        std::fprintf(stderr, "[Launcher] WARNING: binary in protected system directory — may require admin (avoid).\n");
    }
#endif
    // Avoid hard-coded developer paths: we use relative paths above, not /home/user/...

    // Launch native renderer with forwarded args (skip argv[0])
    std::vector<std::string> launchArgs;
    launchArgs.push_back(nativeBin.string());
    for(int i=1;i<argc;++i) launchArgs.push_back(args[i]);

    // If no args, normal runtime; if --help, show launcher help
    bool showHelp=false;
    for(auto &a: args) if(a=="--help" || a=="-h") showHelp=true;
    if(showHelp) {
        std::printf("[Launcher] Usage: \"ASTRA COSMOS\" [--headless] [--benchmark] [--validate] [--help]\n");
        std::printf("[Launcher] Forwards arguments to native renderer. Example: \"ASTRA COSMOS.exe\" --headless\n");
    }

    int exitCode = launchNative(nativeBin, launchArgs);
    std::printf("[Launcher] Native process exited with code %d\n", exitCode);
    return exitCode;
}
