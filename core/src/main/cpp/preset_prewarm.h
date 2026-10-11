// Compiles the shaders of the upcoming presets on a background thread, with its own EGL context and
// projectM instance. The translated and linked programs land in projectM's process-wide caches
// (projectM patches 0002 and 0005), so the switch on the render thread loads them in milliseconds instead of stalling
// on the GPU driver's shader compiler for most of a second.
#pragma once

#include <condition_variable>
#include <deque>
#include <functional>
#include <mutex>
#include <memory>
#include <string>
#include <thread>
#include <vector>

class PresetPrewarmer {
public:
    struct Preset {
        std::string data;
        std::vector<std::string> texturePaths;
        // Retain every immutable disk generation until this projectM instance is destroyed.
        std::vector<std::shared_ptr<const void>> leases;
    };
    using Reader = std::function<Preset(const std::string& name)>;

    ~PresetPrewarmer() { Stop(); }

    // The reader captures data and per-preset search paths together. Shader sampler declarations
    // depend on the images found, so prewarming must use the render instance's exact lookup.
    void Start(Reader reader);
    void Stop();

    // Compiles these presets next, in order, replacing requests that have not started yet. Presets
    // compiled recently are skipped (their programs are in the cache).
    void Request(const std::vector<std::string>& names);

    bool Running() const { return thread_.joinable(); }
    bool UsesPresetPrefix(const std::string& prefix);
    bool UsesPresetDirectory(const std::string& directory);

private:
    void Run();

    std::thread thread_;
    std::mutex mutex_;
    std::condition_variable cv_;
    std::deque<std::string> pending_;
    std::deque<std::string> recent_;  // compiled lately, most recent last
    std::string active_; // Published before reading files; retained until the GL instance is gone.
    std::vector<std::string> activeTexturePaths_;
    bool stop_ = false;
    Reader reader_;
};
