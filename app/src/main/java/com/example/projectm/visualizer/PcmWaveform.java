package com.example.projectm.visualizer;

/** Match the engine's existing 8-bit unsigned mono input without changing the core API. */
final class PcmWaveform {
    private PcmWaveform() {}
    static void convert(short[] pcm, byte[] waveform, int count) {
        for (int i = 0; i < count; i++) waveform[i] = (byte) ((pcm[i] >> 8) + 128);
    }
}
