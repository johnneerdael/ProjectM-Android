package com.example.projectm.visualizer;

import org.junit.Test;
import static org.junit.Assert.*;

public class PcmWaveformTest {
    @Test public void signedPcmUsesTheExistingUnsignedEngineFormat() {
        short[] pcm = {Short.MIN_VALUE, -256, -1, 0, 255, 256, Short.MAX_VALUE};
        byte[] waveform = new byte[pcm.length];
        PcmWaveform.convert(pcm, waveform, pcm.length);
        assertArrayEquals(new byte[]{0, 127, 127, (byte)128, (byte)128, (byte)129, (byte)255}, waveform);
    }
    @Test public void onlyTheReadSamplesAreConverted() {
        byte[] waveform = {42, 42, 42};
        PcmWaveform.convert(new short[]{0, 32767, -32768}, waveform, 1);
        assertArrayEquals(new byte[]{(byte)128, 42, 42}, waveform);
    }
}
