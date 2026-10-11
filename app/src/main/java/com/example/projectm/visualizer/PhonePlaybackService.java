package com.example.projectm.visualizer;

import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.AudioAttributes;
import android.media.AudioPlaybackCaptureConfiguration;
import android.media.AudioRecord;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;

/** Android requires a mediaProjection foreground service before obtaining a playback token. */
public final class PhonePlaybackService extends Service {
    static final String TOKEN = "projection_consent";
    private static final String STOP = "stop";
    private static volatile PhonePlaybackService active;
    private final Handler main = new Handler(Looper.getMainLooper());
    private MediaProjection projection;
    private PhonePcmCapture capture;
    private final MediaProjection.Callback callback = new MediaProjection.Callback() {
        @Override public void onStop() { stopCapture(); stopSelf(); }
    };
    static String status() {
        PhonePlaybackService service = active;
        return service == null || service.capture == null ? "Tap to start" : service.capture.status();
    }
    static long samples() {
        PhonePlaybackService service = active;
        return service == null || service.capture == null ? 0 : service.capture.samples();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (!BuildConfig.TOUCHSCREEN || Build.VERSION.SDK_INT < 29 || intent == null || STOP.equals(intent.getAction())) {
            stopSelf(); return START_NOT_STICKY;
        }
        Intent consent = intent.getParcelableExtra(TOKEN);
        if (consent == null) { stopSelf(); return START_NOT_STICKY; }
        stopCapture();
        try {
            NotificationManager manager = getSystemService(NotificationManager.class);
            manager.createNotificationChannel(new NotificationChannel("phone_audio", "Phone playback capture",
                    NotificationManager.IMPORTANCE_LOW));
            PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class),
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            PendingIntent stop = PendingIntent.getService(this, 1, new Intent(this, PhonePlaybackService.class).setAction(STOP),
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            Notification notification = new Notification.Builder(this, "phone_audio")
                    .setSmallIcon(android.R.drawable.ic_media_play).setContentTitle("ProjectM Android")
                    .setContentText("Visualizing phone playback").setContentIntent(open).setOngoing(true)
                    .addAction(new Notification.Action.Builder(null, "Stop", stop).build()).build();
            startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
            projection = getSystemService(MediaProjectionManager.class).getMediaProjection(Activity.RESULT_OK, consent);
            if (projection == null) throw new IllegalStateException("Playback consent unavailable");
            projection.registerCallback(callback, main);
            AudioPlaybackCaptureConfiguration config = new AudioPlaybackCaptureConfiguration.Builder(projection)
                    .addMatchingUsage(AudioAttributes.USAGE_MEDIA).addMatchingUsage(AudioAttributes.USAGE_GAME)
                    .addMatchingUsage(AudioAttributes.USAGE_UNKNOWN).build();
            capture = new PhonePcmCapture(() -> new AudioRecord.Builder().setAudioFormat(PhonePcmCapture.format())
                    .setBufferSizeInBytes(PhonePcmCapture.bufferSize()).setAudioPlaybackCaptureConfig(config).build(),
                    () -> main.post(() -> { stopCapture(); stopSelf(); }));
            active = this;
        } catch (RuntimeException error) {
            Log.w("ProjectMTV", "Phone playback capture unavailable", error);
            stopCapture(); stopSelf();
        }
        return START_NOT_STICKY;
    }
    private void stopCapture() {
        if (active == this) active = null;
        if (capture != null) { capture.stop(); capture = null; }
        if (projection != null) {
            projection.unregisterCallback(callback);
            projection.stop(); projection = null;
        }
        stopForeground(true);
    }
    @Override public void onDestroy() {
        stopCapture(); main.removeCallbacksAndMessages(null); super.onDestroy();
    }
}
