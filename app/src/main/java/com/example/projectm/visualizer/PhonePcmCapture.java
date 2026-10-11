package com.example.projectm.visualizer;

import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Process;
import android.util.Log;
import nl.neerdael.projectm.core.ProjectMJNI;

/** One blocking read worker per input; stopping unblocks reads, and the worker releases its recorder. */
final class PhonePcmCapture {
    interface Factory { AudioRecord create(); }
    static final int SAMPLE_RATE = 44100;
    private volatile boolean running = true;
    private AudioRecord recorder;
    private volatile String status = "Starting";
    private volatile long samples;

    static AudioFormat format() {
        return new AudioFormat.Builder().setSampleRate(SAMPLE_RATE)
                .setChannelMask(AudioFormat.CHANNEL_IN_MONO).setEncoding(AudioFormat.ENCODING_PCM_16BIT).build();
    }
    static int bufferSize() {
        int minimum = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT);
        if (minimum <= 0) throw new IllegalStateException("Audio format unavailable");
        return Math.max(minimum, 8192);
    }
    static PhonePcmCapture microphone() {
        return new PhonePcmCapture(() -> new AudioRecord(MediaRecorder.AudioSource.MIC,
                SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, bufferSize()), null);
    }
    PhonePcmCapture(Factory factory, Runnable failed) {
        new Thread(() -> read(factory, failed), "PhoneAudioCapture").start();
    }
    private void read(Factory factory, Runnable failed) {
        Process.setThreadPriority(Process.THREAD_PRIORITY_AUDIO);
        AudioRecord created = null;
        try {
            created = factory.create();
            synchronized (this) {
                if (!running) return;
                if (created.getState() != AudioRecord.STATE_INITIALIZED) throw new IllegalStateException("Audio input unavailable");
                recorder = created;
                created.startRecording();
                if (created.getRecordingState() != AudioRecord.RECORDSTATE_RECORDING)
                    throw new IllegalStateException("Audio input did not start");
                status = "Listening";
            }
            short[] pcm = new short[1024];
            byte[] waveform = new byte[pcm.length];
            while (running) {
                int count = created.read(pcm, 0, pcm.length);
                if (!running) break;
                if (count <= 0) throw new IllegalStateException("Audio read failed: " + count);
                PcmWaveform.convert(pcm, waveform, count);
                synchronized (this) {
                    if (!running) break;
                    ProjectMJNI.addWaveform(waveform, count);
                    samples += count;
                }
            }
        } catch (RuntimeException error) {
            if (running) {
                status = "Unavailable";
                Log.w("ProjectMTV", "Phone audio input unavailable", error);
                if (failed != null) failed.run();
            }
        } finally {
            synchronized (this) {
                running = false;
                recorder = null;
                if (created != null) created.release();
            }
        }
    }
    synchronized void stop() {
        running = false;
        if (recorder != null) {
            try { recorder.stop(); } catch (RuntimeException ignored) { /* worker releases it */ }
        }
    }
    String status() { return status; }
    long samples() { return samples; }
}
