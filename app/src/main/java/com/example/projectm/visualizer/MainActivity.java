package com.example.projectm.visualizer;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.drawable.BitmapDrawable;
import android.media.AudioManager;
import android.media.audiofx.Visualizer;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.KeyEvent;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import nl.neerdael.projectm.core.DeviceProfile;
import nl.neerdael.projectm.core.DisplayInfo;
import nl.neerdael.projectm.core.PresetFacets;
import nl.neerdael.projectm.core.ProjectMCore;
import nl.neerdael.projectm.core.ProjectMJNI;
import nl.neerdael.projectm.core.QualityController;
import nl.neerdael.projectm.core.VisualizerRenderer;
import nl.neerdael.projectm.core.VisualizerView;

import java.text.NumberFormat;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public class MainActivity extends Activity {
    private static final String TAG = "ProjectMTV";
    private static final int AUDIO_PERMISSION_REQUEST = 1;
    private static final long MENU_AUTO_HIDE_MS = 10000;
    private static final long NOTICE_SHOWN_MS = 20000;  // a notice in the lower-left pill
    private static final long TRACK_STOP_GRACE_MS = 2000;  // buffering or seeking does not hide the track
    private static final long TRACK_ACCESS_DELAY_MS = 1500;
    private static final long UI_REFRESH_MS = 500;
    private static final long AUDIO_METER_MS = 66;
    private static final long FADE_MS = 180;
    private static final long AUDIO_WATCH_MS = 2000;      // how often silence is checked
    private static final long FIRST_WATCH_MS = 500;       // first check after (re)starting
    private static final long SILENCE_BEFORE_SEARCH_MS = 4000;
    private static final long SEARCH_RETRY_MS = 60000;    // after a search found nothing (a new track allows one)
    private static final long AUDIO_POLL_MS = 50;         // shared Visualizer without callbacks

    private static final String PREFS = "projectm_settings";
    private static final String PREF_AUTO_CHANGE = "auto_change_enabled";
    private static final String PREF_MUSIC_CATEGORY = "music_category";
    private static final String PREF_FAVORITES = "favorite_presets";
    private static final String PREF_BEAT_CUTS = "beat_cuts";
    private static final String PREF_TRACK_ACCESS_EXPLAINED = "track_access_explained";
    private static final String PREF_TRACK_INFO = "track_info";
    private static final String PREF_TRACK_SECONDS = "track_seconds";  // 0 = always
    private static final String PREF_TRACK_PILL = "track_pill";
    private boolean trackAccessPromptShown;
    private AlertDialog trackAccessDialog;
    private AlertDialog customPackDialog;
    private PresetPackUploadServer customPackServer;
    private volatile boolean customPackCommitting;
    // The music player's audio session found last: tried first at the next launch.
    private static final String PREF_LAST_PLAYER_SESSION = "last_player_session";
    private static final String PREF_PRESET_DURATION = "preset_duration";
    private static final String PREF_TRANSITION_DURATION = "transition_duration";
    private static final String PREF_RESOLUTION_MODE = "resolution_mode";  // new opt-in; legacy render_height stays retired
    private static final String PREF_AUTO_HEIGHT = "auto_render_height";  // last automatic level
    private static final String PREF_FRAME_RATE_CAP = "frame_rate_cap";
    private static final String PREF_MESH_LEVEL = "mesh_level";
    private static final String PREF_NATIVE_TRAILS = "native_trails";
    private static final String PREF_SKIP_SLOW = "skip_slow_presets";
    // 1.9 made skipping black presets opt-in (dull output was often missing textures); 1.9.4 turns
    // it on for everyone (new key) with two strikes before a preset is skipped for good.
    private static final String PREF_BLANK_DETECTION = "blank_detection_v3";
    private static final String PREF_TRANSITION_MODE = "transition_mode";
    // Troubleshooting switches for GPU drivers that crash at preset switches (on by default).
    private static final String PREF_BACKGROUND_COMPILE = "background_compile";
    private static final String PREF_SHADER_BINARY_CACHE = "shader_binary_cache";

    private static final int[] PRESET_DURATIONS = {10, 15, 20, 30, 45, 60, 90};
    private static final int[] TRACK_SECONDS = {10, 20, 30, 60, 0};  // 0 = always
    private static final int MAX_TRANSITION = 10;

    private enum Menu { NONE, MAIN, ADVANCED, TRACK, MOOD }

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final NumberFormat numberFormat = NumberFormat.getIntegerInstance(Locale.getDefault());
    private SharedPreferences prefs;
    private DeviceProfile profile;
    private DisplayInfo display;
    private QualityController quality;
    private int frameRateTarget;
    private float targetFps = 60f;
    private long renderBudgetGeneration;
    private boolean budgetedDetailAllocation;
    private boolean budgetedBlendAllocation;

    private VisualizerView visualizerView;
    private VisualizerRenderer renderer;

    // Audio capture runs on its own looper so UI work (menu animations) never delays it.
    private HandlerThread audioThread;
    private Handler audioHandler;
    private volatile Visualizer audioVisualizer;
    // The session of the music player we found (see PlayerSessionFinder), 0 while none is known.
    // Only touched on audioThread.
    private PhoneAudioInput phoneAudio;
    private OptionRow audioInputRow;
    private volatile int audioSession;
    private int lastPlayerSession;
    private volatile long lastSignalAt;
    private long nextSearchAt;
    private boolean trackSearchDue;  // a new track started: allows one search despite the backoff
    private boolean musicActive;
    private boolean noAudioNoticeDue;  // after a (re)start: tell once when no player session is found
    private byte[] pollBuffer;
    private boolean audioPolled;
    private AudioManager audioManager;
    private volatile boolean resumed;  // also read on audioThread

    private View mainMenu;
    private View advancedMenu;
    private View trackMenu;
    private View moodMenu;
    private TextView moodHeader;
    private OptionRow moodCollectionRow;
    private OptionRow moodClearRow;
    private LinearLayout moodRows;
    private final List<FacetRow> facetRows = new ArrayList<>();
    private PresetFacets moodFacets;
    private MoodFacetsController mood;
    private SkipListFile skipListFile;
    private String moodSource;  // where the facet table came from; a change reloads it
    private int moodRevision;   // bumped on every Mood change, refreshes the main row's summary
    private View diagnosticsPanel;
    private TextView presetName;
    private TextView presetMeta;
    private OptionRow favoriteCurrentRow;
    private OptionRow playFavoritesRow;
    private OptionRow autoChangeRow;
    private TextView statusLine;
    private TextView diagnostics;
    private AudioMeterView audioMeter;
    private TextView audioStatus;
    private OptionRow skippedRow;
    private OptionRow lastExitRow;
    private List<ExitDiagnostics.Exit> recentExits;
    private OptionRow musicCategoryRow;
    private OptionRow nativeTrailsRow;
    private String requestedMusicCategory = "all";
    private String displayedMusicCategory = "";
    private View nowPlaying;
    private ImageView nowPlayingIcon;
    private TextView nowPlayingText;
    private Updater updater;
    private OfficialCollection officialCollection;
    private OptionRow installRow;
    private boolean updateAnnounced;  // the pill announces a ready update once per launch
    private final Updater.Listener updateListener = this::onUpdateReady;
    private Menu menu = Menu.NONE;
    private int lastPresetChange = -1;
    private String currentPreset = "";
    private String currentPresetPath = "";
    private boolean favoritesPlaying;
    private boolean favoritesPreviousAutoChange;

    private final Runnable hideMenu = () -> showMenu(Menu.NONE);
    private final Runnable audioMeterRefresh = new Runnable() {
        @Override
        public void run() {
            if (menu != Menu.MAIN) return;
            float level = ProjectMJNI.getAudioLevel();
            audioMeter.setLevel(level);
            setText(audioStatus, audioStatus(level));
            handler.postDelayed(this, AUDIO_METER_MS);
        }
    };
    private TrackWatcher trackWatcher;
    private TrackCorner trackCorner;
    private TrackWatcher.Track currentTrack;
    private boolean trackPlaying;
    private boolean pillHoldsTrack;  // the pill shows the track (Pill style), not a notice
    private final Runnable hideNowPlaying = () -> {
        boolean notice = !pillHoldsTrack;
        pillHoldsTrack = false;
        fade(nowPlaying, false);
        if (notice && trackSeconds() == 0) showTrack(true);  // a track shown always takes the pill back
    };
    private OptionRow trackInfoRow;
    private Boolean trackInfoRowAccess;  // whether the row was last set up with access
    private final Runnable trackTimeUp = this::hideTrack;
    private final Runnable trackStopped = () -> {
        trackPlaying = false;
        hideTrack();
    };
    private final Runnable uiRefresh = new Runnable() {
        @Override
        public void run() {
            refreshStatus();
            handler.postDelayed(this, UI_REFRESH_MS);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
                | WindowManager.LayoutParams.FLAG_FULLSCREEN);
        setContentView(R.layout.activity_main);
        getWindow().setBackgroundDrawable(null);  // the GL surface covers the screen

        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        if (BuildConfig.TOUCHSCREEN) phoneAudio = new PhoneAudioInput(this, prefs);
        lastPlayerSession = prefs.getInt(PREF_LAST_PLAYER_SESSION, 0);
        profile = DeviceProfile.detect(this);
        display = DisplayInfo.detect(this);

        // Settings go to the native engine before the surface exists; they are applied on the
        // GL thread as soon as projectM is created.
        int[] mesh = DeviceProfile.MESH_SIZES[meshLevel()];
        ProjectMJNI.setMeshSize(mesh[0], mesh[1]);
        ProjectMJNI.setAutoChange(prefs.getBoolean(PREF_AUTO_CHANGE, true));
        requestedMusicCategory = MusicCategories.normalize(prefs.getString(PREF_MUSIC_CATEGORY, "all"));
        reloadMood();
        mood.apply();  // the facet pool and the category (facets, all or custom)
        ProjectMJNI.setBeatCuts(prefs.getBoolean(PREF_BEAT_CUTS, false));
        ProjectMJNI.setPresetDuration(prefs.getInt(PREF_PRESET_DURATION, 30));
        ProjectMJNI.setBlankDetection(prefs.getBoolean(PREF_BLANK_DETECTION, true));
        ProjectMJNI.setTransitionMode(prefs.getInt(PREF_TRANSITION_MODE, ProjectMJNI.TRANSITION_AUTO),
                profile.lowerBlendResolutionByDefault());
        ProjectMJNI.setBackgroundCompile(prefs.getBoolean(PREF_BACKGROUND_COMPILE, true));
        ProjectMJNI.setShaderBinaryCache(prefs.getBoolean(PREF_SHADER_BINARY_CACHE, true));

        visualizerView = findViewById(R.id.visualizer_view);
        renderer = new VisualizerRenderer(new VisualizerRenderer.BudgetStatsListener() {
            @Override
            public void onFpsSample(float fps) {
                handler.post(() -> onFrameRate(fps));
            }

            @Override
            public void onBudgetFpsSample(float fps, long generation, int width, int height) {
                handler.post(() -> {
                    if (generation == renderBudgetGeneration && height == quality.currentHeight()
                            && width == display.widthForHeight(height)) onFrameRate(fps);
                });
            }

            @Override
            public void onRenderBudgetRequested(long generation) {
                handler.post(() -> {
                    if (!isFinishing() && !isDestroyed() && quality != null
                            && generation > renderBudgetGeneration) {
                        renderBudgetGeneration = generation;
                        quality.revalidateForResume(true);
                    }
                });
            }

            @Override
            public void onPresetChanged() {
                handler.post(() -> quality.onPresetChanged());
            }
        });
        createQualityController();
        visualizerView.start(renderer);
        applyFrameRateCap(prefs.getInt(PREF_FRAME_RATE_CAP, profile.defaultFrameRateCap()));

        initMenus();
        if (BuildConfig.TOUCHSCREEN) initTouchControls();

        audioThread = new HandlerThread("AudioCapture", android.os.Process.THREAD_PRIORITY_AUDIO);
        audioThread.start();
        audioHandler = new Handler(audioThread.getLooper());
        audioManager = getSystemService(AudioManager.class);
        if (hasAudioPermission()) {
            onAudioPermissionGranted();
        } else if (Build.VERSION.SDK_INT >= 23) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, AUDIO_PERMISSION_REQUEST);
        }
    }

    // ---------------------------------------------------------------------------------------
    // Quality: resolution and frame rate
    // ---------------------------------------------------------------------------------------

    /** (Re)creates dynamic resolution for the current memory limit. */
    private void createQualityController() {
        Log.i(TAG, "Automatic resolution: panel up to " + display.physicalHeight
                + "p, live memory budget (RAM " + profile.totalRamMb + " MB)");
        quality = new QualityController(display, profile, 0, this::applyRenderHeight);
        quality.setRenderAllocationSettings(nativeTrailsLevel(), transitionSeconds());
        quality.setSkipSlowPresets(prefs.getBoolean(PREF_SKIP_SLOW, profile.defaultSkipSlowPresets()));
        quality.setTargetFps(targetFps);
        quality.setResolutionMode(QualityController.validResolutionMode(display,
                prefs.getInt(PREF_RESOLUTION_MODE, 0)), prefs.getInt(PREF_AUTO_HEIGHT, 0));
    }

    @Override
    public void onTrimMemory(int level) {
        super.onTrimMemory(level);
        // While visible, these mean the system is about to kill other apps (e.g. the music player).
        if (level == TRIM_MEMORY_RUNNING_LOW || level == TRIM_MEMORY_RUNNING_CRITICAL) {
            // The lower resolution applies at the next preset switch.
            quality.onMemoryPressure(level);
            ProjectMJNI.onMemoryPressure();
        }
    }

    private void applyRenderHeight(int height) {
        if (quality != null && quality.wasLastChangeForMemoryPressure()) ProjectMJNI.onMemoryPressure();
        publishRenderConfiguration(height);
        ProjectMJNI.setForceHardCut(false);
        if (quality != null && quality.isAuto()) {
            prefs.edit().putInt(PREF_AUTO_HEIGHT, quality.autoHeightToRemember()).apply();
        }
    }

    private void onFrameRate(float fps) {
        if (ProjectMJNI.getCompletedRenderBudgetGeneration() != renderBudgetGeneration) return;
        int action = quality.onFpsSample(fps);
        // Resolution changes apply by themselves (the presets' frames are scaled to the new size);
        // only a preset that is too slow even at the lowest resolution is skipped.
        if (action == QualityController.ACTION_SKIP) ProjectMJNI.skipCurrentPreset();
    }

    /** Frame-rate options: the refresh rate divided by 4, 2 or 1 (at least 24 fps), ascending. */
    private int[] frameRateOptions() {
        List<Integer> rates = new ArrayList<>();
        for (int divisor : new int[]{4, 2, 1}) {
            int rate = Math.round(display.refreshRate / divisor);
            if (rate >= 24 && !rates.contains(rate)) rates.add(rate);
        }
        int[] result = new int[rates.size()];
        for (int i = 0; i < result.length; i++) result[i] = rates.get(i);
        return result;
    }

    private void applyFrameRateCap(int cap) {
        int best = 1;
        float bestDiff = Float.MAX_VALUE;
        for (int divisor : new int[]{1, 2, 4}) {
            float rate = display.refreshRate / divisor;
            if (rate < 24 && divisor > 1) continue;
            float diff = Math.abs(rate - cap);
            if (diff < bestDiff) {
                bestDiff = diff;
                best = divisor;
            }
        }
        frameRateTarget = Math.round(display.refreshRate / best);
        targetFps = display.refreshRate / best;
        visualizerView.setFrameDivisor(best);
        quality.setTargetFps(targetFps);
        ProjectMJNI.setForceHardCut(false);  // any queued resolution change was dropped
    }

    private int meshLevel() {
        int level = prefs.getInt(PREF_MESH_LEVEL, profile.defaultMeshLevel());
        return Math.max(0, Math.min(level, DeviceProfile.MESH_SIZES.length - 1));
    }

    private int nativeTrailsLevel() {
        int level = prefs.getInt(PREF_NATIVE_TRAILS, 0);
        return level >= 0 && level <= 2 ? level : 0;
    }

    /** Keep the selected gain while automatic resolution chooses whether native trails is active. */
    private void applyNativeTrails() {
        if (quality != null) {
            quality.setRenderAllocationSettings(nativeTrailsLevel(), transitionSeconds());
            publishRenderConfiguration(quality.currentHeight());
        }
    }

    private void publishRenderConfiguration(int height) {
        boolean detail = nativeTrailsLevel() > 0;
        boolean blend = transitionSeconds() > 0;
        if (detail != budgetedDetailAllocation || blend != budgetedBlendAllocation) {
            budgetedDetailAllocation = detail;
            budgetedBlendAllocation = blend;
            // Invalidate queued FPS for every topology change. Growth needs a full review;
            // confirmed reductions defer pressure sampling until GL releases the old textures.
            renderBudgetGeneration = ProjectMJNI.requireRenderBudget();
            quality.revalidateForAllocationChange(); // The listener publishes its chosen height.
            return;
        }
        visualizerView.setRenderConfiguration(display.widthForHeight(height), height,
                nativeTrailsLevel(), transitionSeconds(), renderBudgetGeneration);
    }

    private int transitionSeconds() {
        return Math.min(MAX_TRANSITION, prefs.getInt(PREF_TRANSITION_DURATION, profile.defaultTransitionSeconds()));
    }

    private static String heightLabel(int height) {
        if (height == QualityController.NATIVE_HEIGHT) return "Native";
        if (height == 2160) return "4K";
        if (height == 1440) return "1440p";
        return height + "p";
    }

    // ---------------------------------------------------------------------------------------
    // Menus
    // ---------------------------------------------------------------------------------------

    private void initMenus() {
        mainMenu = findViewById(R.id.overlay_menu);
        advancedMenu = findViewById(R.id.advanced_menu);
        trackMenu = findViewById(R.id.track_menu);
        moodMenu = findViewById(R.id.mood_menu);
        moodHeader = findViewById(R.id.mood_header);
        moodCollectionRow = findViewById(R.id.row_mood_collection);
        moodRows = findViewById(R.id.mood_rows);
        diagnosticsPanel = findViewById(R.id.diagnostics_panel);
        presetName = findViewById(R.id.preset_name);
        presetMeta = findViewById(R.id.preset_meta);
        statusLine = findViewById(R.id.status_line);
        diagnostics = findViewById(R.id.diagnostics);
        audioMeter = findViewById(R.id.audio_meter);
        audioStatus = findViewById(R.id.audio_status);
        nowPlaying = findViewById(R.id.now_playing);
        nowPlayingIcon = findViewById(R.id.now_playing_icon);
        nowPlayingText = findViewById(R.id.now_playing_text);
        trackCorner = new TrackCorner(findViewById(R.id.track_corner));
        trackWatcher = new TrackWatcher(this, handler, new TrackWatcher.Listener() {
            @Override
            public void onTrack(TrackWatcher.Track track, boolean newTrack) {
                onTrackChanged(track, newTrack);
            }

            @Override
            public void onStopped() {
                onTrackStopped();
            }
        });
        updater = Updater.get(this, prefs);
        updater.attach(handler, updateListener);
        officialCollection = new OfficialCollection(this, prefs, handler, visualizerView);
        // An official collection installed or removed meanwhile replaces the facet table and the pool.
        officialCollection.setOnCollectionChanged(() -> {
            reloadMood();
            renderMood();
        });

        TextView versionInfo = findViewById(R.id.version_info);
        versionInfo.setText(getString(R.string.engine_version_info,
                appVersion(), ProjectMJNI.getVersion()));

        findViewById(R.id.prev_preset_button).setOnClickListener(v -> ProjectMJNI.previousPreset(true));
        findViewById(R.id.random_preset_button).setOnClickListener(v -> ProjectMJNI.randomPreset(true));
        findViewById(R.id.next_preset_button).setOnClickListener(v -> ProjectMJNI.nextPreset(true));

        favoriteCurrentRow = findViewById(R.id.row_favorite_current);
        playFavoritesRow = findViewById(R.id.row_play_favorites);
        favoriteCurrentRow.setupAction("Favorite current visualizer", "Add", this::toggleCurrentFavorite);
        playFavoritesRow.setupAction("Favorites collection", "Play", this::toggleFavoritesPlayback);
        updateFavoriteRows();

        installRow = findViewById(R.id.row_install_update);
        installRow.setupAction("Update ready", "", () -> {
            if (!updater.install(this)) {
                Toast.makeText(this, "Android's installer could not be opened", Toast.LENGTH_LONG).show();
            }
        });

        audioInputRow = findViewById(R.id.row_audio_input);
        if (BuildConfig.TOUCHSCREEN) {
            audioInputRow.setVisibility(View.VISIBLE);
            audioInputRow.setupAction("Audio input", phoneAudio.label(), phoneAudio::choose);
        }

        autoChangeRow = findViewById(R.id.row_auto_change);
        updateAutoChangeRow();

        musicCategoryRow = findViewById(R.id.row_music_category);
        musicCategoryRow.setupAction("Preset mood", "›", this::showMoodMenu);
        refreshMusicCategory();

        // Mood panel
        moodClearRow = findViewById(R.id.row_mood_clear);
        moodClearRow.setupAction("Clear all", "", () -> {
            mood.clearAll();
            renderMood();
        });
        buildMoodRows();

        String[] durations = new String[PRESET_DURATIONS.length];
        for (int i = 0; i < durations.length; i++) durations[i] = PRESET_DURATIONS[i] + " s";
        OptionRow presetDuration = findViewById(R.id.row_preset_duration);
        presetDuration.setup("Preset duration", durations,
                nearestIndex(PRESET_DURATIONS, prefs.getInt(PREF_PRESET_DURATION, 30)), false, index -> {
                    ProjectMJNI.setPresetDuration(PRESET_DURATIONS[index]);
                    prefs.edit().putInt(PREF_PRESET_DURATION, PRESET_DURATIONS[index]).apply();
                });


        OptionRow trackDisplay = findViewById(R.id.row_track_display);
        trackDisplay.setupAction("Track display", "›", () -> showMenu(Menu.TRACK));

        OptionRow advanced = findViewById(R.id.row_advanced);
        advanced.setupAction("Advanced", "›", () -> showMenu(Menu.ADVANCED));

        // Track display panel
        trackInfoRow = findViewById(R.id.row_track_info);
        refreshTrackInfoRow();

        String[] trackDurations = new String[TRACK_SECONDS.length];
        for (int i = 0; i < trackDurations.length; i++) {
            trackDurations[i] = TRACK_SECONDS[i] == 0 ? "Always" : TRACK_SECONDS[i] + " s";
        }
        OptionRow trackDuration = findViewById(R.id.row_track_duration);
        trackDuration.setup("Show for", trackDurations, nearestIndex(TRACK_SECONDS, trackSeconds()), false, index -> {
            prefs.edit().putInt(PREF_TRACK_SECONDS, TRACK_SECONDS[index]).apply();
            applyTrackDisplay();
        });

        OptionRow trackPill = findViewById(R.id.row_track_pill);
        trackPill.setup("Pill style", new String[]{"Off", "On"}, trackPill() ? 1 : 0, true, index -> {
            prefs.edit().putBoolean(PREF_TRACK_PILL, index == 1).apply();
            applyTrackDisplay();
        });

        // Advanced panel
        OptionRow customPack = findViewById(R.id.row_custom_pack);
        customPack.setupAction("Custom preset pack", "Upload ZIP ›", this::showCustomPackUpload);
        int[] resolutions = QualityController.resolutionModes(display);
        String[] resolutionLabels = new String[resolutions.length];
        int selectedResolution = 0;
        int savedResolution = QualityController.validResolutionMode(display,
                prefs.getInt(PREF_RESOLUTION_MODE, 0));
        for (int i = 0; i < resolutions.length; i++) {
            int height = resolutions[i];
            resolutionLabels[i] = height == 0 ? getString(R.string.resolution_auto)
                    : height == QualityController.NATIVE_HEIGHT
                    ? getString(R.string.resolution_native, heightLabel(display.physicalHeight))
                    : heightLabel(height);
            if (height == savedResolution) selectedResolution = i;
        }
        OptionRow resolution = findViewById(R.id.row_resolution);
        resolution.setup(getString(R.string.resolution), resolutionLabels, selectedResolution, true, index -> {
            prefs.edit().putInt(PREF_RESOLUTION_MODE, resolutions[index]).apply();
            // Reject queued samples from the old mode before publishing its replacement tuple.
            renderBudgetGeneration = ProjectMJNI.requireRenderBudget();
            quality.setResolutionMode(resolutions[index], prefs.getInt(PREF_AUTO_HEIGHT, 0));
            refreshStatus();
        });
        int[] caps = frameRateOptions();
        String[] capLabels = new String[caps.length];
        int selectedCap = caps.length - 1;
        for (int i = 0; i < caps.length; i++) {
            capLabels[i] = caps[i] + " fps";
            if (caps[i] == frameRateTarget) selectedCap = i;
        }
        OptionRow frameRate = findViewById(R.id.row_frame_rate);
        frameRate.setup("Frame rate", capLabels, selectedCap, false, index -> {
            prefs.edit().putInt(PREF_FRAME_RATE_CAP, caps[index]).apply();
            applyFrameRateCap(caps[index]);
        });

        OptionRow detail = findViewById(R.id.row_detail);
        detail.setup("Detail", DeviceProfile.MESH_LABELS, meshLevel(), false, index -> {
            int[] size = DeviceProfile.MESH_SIZES[index];
            ProjectMJNI.setMeshSize(size[0], size[1]);
            prefs.edit().putInt(PREF_MESH_LEVEL, index).apply();
        });

        nativeTrailsRow = findViewById(R.id.row_native_trails);
        nativeTrailsRow.setup("Native trails", new String[]{"Standard", "Medium", "High"},
                nativeTrailsLevel(), false, index -> {
                    prefs.edit().putInt(PREF_NATIVE_TRAILS, index).apply();
                    applyNativeTrails();
                });
        applyNativeTrails();

        String[] transitions = new String[MAX_TRANSITION + 1];
        transitions[0] = "Instant";
        for (int i = 1; i <= MAX_TRANSITION; i++) transitions[i] = i + " s";
        OptionRow transition = findViewById(R.id.row_transition);
        transition.setup("Transition", transitions, transitionSeconds(), false, index -> {
            prefs.edit().putInt(PREF_TRANSITION_DURATION, index).apply();
            quality.setRenderAllocationSettings(nativeTrailsLevel(), index);
            publishRenderConfiguration(quality.currentHeight());
        });

        OptionRow transitionMode = findViewById(R.id.row_transition_mode);
        transitionMode.setup("Transitions", new String[]{"Auto", "Lightweight", "Classic"},
                prefs.getInt(PREF_TRANSITION_MODE, ProjectMJNI.TRANSITION_AUTO), true, index -> {
                    ProjectMJNI.setTransitionMode(index, profile.lowerBlendResolutionByDefault());
                    prefs.edit().putInt(PREF_TRANSITION_MODE, index).apply();
                });

        OptionRow beatCuts = findViewById(R.id.row_beat_cuts);
        beatCuts.setup("Cut on loud beats", new String[]{"Off", "On"},
                prefs.getBoolean(PREF_BEAT_CUTS, false) ? 1 : 0, true, index -> {
                    ProjectMJNI.setBeatCuts(index == 1);
                    prefs.edit().putBoolean(PREF_BEAT_CUTS, index == 1).apply();
                });

        OptionRow skipSlow = findViewById(R.id.row_skip_slow);
        skipSlow.setup("Skip slow presets", new String[]{"Off", "On"},
                prefs.getBoolean(PREF_SKIP_SLOW, profile.defaultSkipSlowPresets()) ? 1 : 0, true, index -> {
                    quality.setSkipSlowPresets(index == 1);
                    prefs.edit().putBoolean(PREF_SKIP_SLOW, index == 1).apply();
                });

        OptionRow blank = findViewById(R.id.row_blank_detection);
        blank.setup("Skip blank presets", new String[]{"Off", "On"},
                prefs.getBoolean(PREF_BLANK_DETECTION, true) ? 1 : 0, true, index -> {
                    ProjectMJNI.setBlankDetection(index == 1);
                    prefs.edit().putBoolean(PREF_BLANK_DETECTION, index == 1).apply();
                });

        OptionRow autoUpdate = findViewById(R.id.row_auto_update);
        if (updater.isViaFDroid()) {
            autoUpdate.setupAction("Auto-update", "Via F-Droid", () -> Toast.makeText(this,
                    "Installed from F-Droid, which keeps the app up to date", Toast.LENGTH_LONG).show());
        } else {
            autoUpdate.setup("Auto-update", new String[]{"Off", "On"}, updater.isEnabled() ? 1 : 0, true, index -> {
                updater.setEnabled(index == 1);
                if (index == 0) installRow.setVisibility(View.GONE);
            });
        }

        skippedRow = findViewById(R.id.row_skipped);
        skippedRow.setupAction("Skipped presets", "None", () -> {
            ProjectMJNI.resetSkippedPresets();
            // The pool sent to the engine left skipped presets out: send it again with them.
            if ("bundled".equals(mood.collection()) && !mood.selected().isEmpty()) {
                mood.apply();
                renderMood();
            }
            refreshStatus();
        });

        OptionRow backgroundCompile = findViewById(R.id.row_background_compile);
        backgroundCompile.setup("Background compile", new String[]{"Off", "On"},
                prefs.getBoolean(PREF_BACKGROUND_COMPILE, true) ? 1 : 0, true, index -> {
                    ProjectMJNI.setBackgroundCompile(index == 1);
                    prefs.edit().putBoolean(PREF_BACKGROUND_COMPILE, index == 1).apply();
                });

        OptionRow shaderBinaryCache = findViewById(R.id.row_shader_binary_cache);
        shaderBinaryCache.setup("Shader binary cache", new String[]{"Off", "On"},
                prefs.getBoolean(PREF_SHADER_BINARY_CACHE, true) ? 1 : 0, true, index -> {
                    ProjectMJNI.setShaderBinaryCache(index == 1);
                    prefs.edit().putBoolean(PREF_SHADER_BINARY_CACHE, index == 1).apply();
                });

        // Exit records of earlier processes do not change while this one runs: read them once.
        recentExits = ExitDiagnostics.recentExits(this);
        lastExitRow = findViewById(R.id.row_last_exit);
        lastExitRow.setupAction("Last exit", lastExitSummary(), () -> showExitReport(recentExits));

        mainMenu.setVisibility(View.GONE);
        advancedMenu.setVisibility(View.GONE);
        trackMenu.setVisibility(View.GONE);
        moodMenu.setVisibility(View.GONE);
        diagnosticsPanel.setVisibility(View.GONE);
    }

    /** Framework gesture detection stays on the surface; panels keep native click/scroll handling. */
    private void initTouchControls() {
        View root = findViewById(R.id.root_view);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            // The visualizer can fill the window; menus stay clear of transient phone system bars.
            int end = view.getLayoutDirection() == View.LAYOUT_DIRECTION_RTL
                    ? insets.getStableInsetLeft() : insets.getStableInsetRight();
            for (View panel : new View[]{mainMenu, advancedMenu, trackMenu, moodMenu}) {
                android.view.ViewGroup.MarginLayoutParams params =
                        (android.view.ViewGroup.MarginLayoutParams) panel.getLayoutParams();
                int top = dp(12) + insets.getStableInsetTop();
                int bottom = dp(12) + insets.getStableInsetBottom();
                if (params.getMarginEnd() != dp(12) + end || params.topMargin != top || params.bottomMargin != bottom) {
                    params.setMarginEnd(dp(12) + end);
                    params.topMargin = top;
                    params.bottomMargin = bottom;
                    panel.setLayoutParams(params);
                }
            }
            return insets;
        });
        root.requestApplyInsets();
        visualizerView.setOnClickListener(v -> showMenu(menu == Menu.NONE ? Menu.MAIN : Menu.NONE));
        int[] swipeDirection = {0};
        GestureDetector detector = new GestureDetector(this, new GestureDetector.SimpleOnGestureListener() {
            @Override public boolean onDown(MotionEvent event) {
                swipeDirection[0] = 0;
                return true;
            }
            @Override public boolean onSingleTapUp(MotionEvent event) {
                visualizerView.performClick();
                return true;
            }
            @Override public boolean onScroll(MotionEvent start, MotionEvent current, float dx, float dy) {
                if (start == null || menu != Menu.NONE) return true;
                float x = current.getX() - start.getX();
                float y = current.getY() - start.getY();
                if (Math.abs(x) >= dp(64) && Math.abs(x) > Math.abs(y) * 1.5f) {
                    swipeDirection[0] = x > 0 ? 1 : -1;
                } else {
                    swipeDirection[0] = 0;
                }
                return true;
            }
        });
        detector.setIsLongpressEnabled(false);
        boolean[] cancelled = {false};
        visualizerView.setOnTouchListener((view, event) -> {
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) cancelled[0] = false;
            // Cancel recognition when a second finger joins; a multi-touch release is no tap.
            if (event.getActionMasked() == MotionEvent.ACTION_POINTER_DOWN) {
                cancelled[0] = true;
                swipeDirection[0] = 0;
                MotionEvent cancel = MotionEvent.obtain(event);
                cancel.setAction(MotionEvent.ACTION_CANCEL);
                detector.onTouchEvent(cancel);
                cancel.recycle();
                return true;
            }
            if (cancelled[0]) return true;
            detector.onTouchEvent(event);
            if (event.getActionMasked() == MotionEvent.ACTION_UP && menu == Menu.NONE) {
                if (swipeDirection[0] > 0) ProjectMJNI.randomPreset(true);
                else if (swipeDirection[0] < 0) ProjectMJNI.previousPreset(true);
                swipeDirection[0] = 0;
            }
            if (event.getActionMasked() == MotionEvent.ACTION_CANCEL) swipeDirection[0] = 0;
            return true;
        });
        touchNavigation(R.id.menu_close, "Close menu", Menu.NONE);
        touchNavigation(R.id.advanced_back, "Back to menu", Menu.MAIN);
        touchNavigation(R.id.track_back, "Back to menu", Menu.MAIN);
        touchNavigation(R.id.mood_back, "Back to menu", Menu.MAIN);
    }

    private void touchNavigation(int id, String text, Menu target) {
        TextView view = findViewById(id);
        view.setText(text);
        view.setGravity(Gravity.CENTER);
        view.setMinHeight(dp(48));
        view.setBackgroundResource(R.drawable.bg_option_row);
        view.setFocusable(true);
        view.setOnClickListener(v -> showMenu(target));
    }

    @Override
    public boolean dispatchTouchEvent(MotionEvent event) {
        if (BuildConfig.TOUCHSCREEN && menu != Menu.NONE) {
            handler.removeCallbacks(hideMenu);
            if (event.getActionMasked() == MotionEvent.ACTION_UP
                    || event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
                handler.postDelayed(hideMenu, MENU_AUTO_HIDE_MS);
            }
        }
        return super.dispatchTouchEvent(event);
    }

    private static int nearestIndex(int[] values, int target) {
        int best = 0;
        for (int i = 1; i < values.length; i++) {
            if (Math.abs(values[i] - target) < Math.abs(values[best] - target)) best = i;
        }
        return best;
    }

    private View panel(Menu which) {
        switch (which) {
            case MAIN: return mainMenu;
            case ADVANCED: return advancedMenu;
            case TRACK: return trackMenu;
            case MOOD: return moodMenu;
            default: return null;
        }
    }

    /**
     * Shows one panel (or none). The advanced and track display panels slide in over the main panel.
     * The track stays on screen: the corner and the pill keep clear of the panels.
     */
    private void showMenu(Menu target) {
        handler.removeCallbacks(hideMenu);
        if (target == menu) return;
        Menu previous = menu;
        menu = target;

        if (target == Menu.NONE) {
            slide(panel(previous), false);
            if (previous == Menu.ADVANCED) fade(diagnosticsPanel, false);
            return;
        }
        if (!pillHoldsTrack) fade(nowPlaying, false);  // a notice goes, the track stays
        refreshStatus();
        handler.removeCallbacks(audioMeterRefresh);
        if (target == Menu.MAIN) handler.post(audioMeterRefresh);
        if (target == Menu.MAIN) {
            if (previous != Menu.NONE) {
                slide(panel(previous), false);
                if (previous == Menu.ADVANCED) fade(diagnosticsPanel, false);
                fade(mainMenu, true);
                findViewById(previous == Menu.ADVANCED ? R.id.row_advanced
                        : previous == Menu.MOOD ? R.id.row_music_category : R.id.row_track_display).requestFocus();
            } else {
                slide(mainMenu, true);
                (installRow.getVisibility() == View.VISIBLE ? installRow
                        : findViewById(R.id.random_preset_button)).requestFocus();
            }
        } else {
            if (target == Menu.MOOD) {
                reloadMood();  // picks up an official collection installed meanwhile
                mood.revalidateCollection();
                mood.skipsChanged(ProjectMJNI.getSkippedCount());  // baseline for the polling check
                renderMood();
            }
            fade(mainMenu, false);
            slide(panel(target), true);
            if (target == Menu.ADVANCED) {
                if (!BuildConfig.TOUCHSCREEN) fade(diagnosticsPanel, true);
                findViewById(R.id.row_resolution).requestFocus();
            } else if (target == Menu.MOOD) {
                (moodCollectionRow.getVisibility() == View.VISIBLE ? moodCollectionRow
                        : !facetRows.isEmpty() ? facetRows.get(0) : findViewById(R.id.row_mood_clear)).requestFocus();
            } else {
                trackInfoRow.requestFocus();
            }
        }
        handler.postDelayed(hideMenu, MENU_AUTO_HIDE_MS);
    }

    private void slide(View view, boolean in) {
        float offset = dp(24);
        view.animate().cancel();
        if (in) {
            view.setTranslationX(offset);
            view.setVisibility(View.VISIBLE);
            // The window's transparent region, where the visualizer surface shows through, is only
            // recomputed at a layout. Laid out while still offset, the panel would leave the strip it
            // slides into see-through on some TVs (e.g. a MediaTek Google TV) until the next layout.
            view.animate().translationX(0).alpha(1f).setDuration(FADE_MS).withLayer()
                    .withEndAction(view::requestLayout).start();
        } else if (view.getVisibility() == View.VISIBLE) {
            view.animate().translationX(offset).alpha(0f).setDuration(FADE_MS).withLayer()
                    .withEndAction(() -> view.setVisibility(View.GONE)).start();
        }
    }

    /** Alpha fade that ends with GONE, so hidden views cost nothing to compose. */
    private static void fade(View view, boolean in) {
        view.animate().cancel();  // a cancelled animation does not run its end action
        if (in) {
            if (view.getTranslationX() != 0) {
                view.setTranslationX(0);  // a panel returning from a submenu may have been mid-slide
                view.requestLayout();     // see slide(): the transparent region follows layouts only
            }
            view.setVisibility(View.VISIBLE);
            view.animate().alpha(1f).setDuration(FADE_MS).withLayer().start();
        } else if (view.getVisibility() == View.VISIBLE) {
            view.animate().alpha(0f).setDuration(FADE_MS).withLayer()
                    .withEndAction(() -> view.setVisibility(View.GONE)).start();
        }
    }

    /** Updates text only when it changed: a changed text restarts the marquee and costs a layout. */
    private static void setText(TextView view, CharSequence text) {
        if (!text.toString().contentEquals(view.getText())) view.setText(text);
    }

    /**
     * Keeps the Preset mood row's summary current. When the engine fell back to All (no eligible
     * preset left in the pool, e.g. all skipped), only the category is updated: the Mood panel's
     * stored facets stay, so a later change or launch can use them again.
     */
    private void refreshMusicCategory() {
        if (musicCategoryRow == null || customPackCommitting || mood == null) return;
        if (favoritesPlaying) {
            displayedMusicCategory = "favorites|" + ProjectMJNI.getSkippedCount();
            musicCategoryRow.setActionValue("Favorites playing  ›");
            return;
        }
        String applied = MusicCategories.appliedSelection(requestedMusicCategory,
                ProjectMJNI.getMusicCategory(), ProjectMJNI.isMusicCategoryPending());
        if (!ProjectMJNI.isMusicCategoryPending() && !applied.equals(requestedMusicCategory)) {
            requestedMusicCategory = applied;
            prefs.edit().putString(PREF_MUSIC_CATEGORY, applied).apply();
            Toast.makeText(this, "No eligible presets in that category; using All", Toast.LENGTH_SHORT).show();
            // A custom pack that is gone (or failed to restore) must not leave the facets disabled.
            if (mood.revalidateCollection()) renderMood();
        }
        // The facets count joins the key so the summary follows the engine once the pool is rebuilt.
        String key = applied + "|" + ProjectMJNI.getSkippedCount() + "|" + moodRevision
                + ("facets".equals(applied) ? "|" + ProjectMJNI.getCategoryPresetCount("facets") : "");
        if (key.equals(displayedMusicCategory)) return;
        displayedMusicCategory = key;
        musicCategoryRow.setActionValue(moodSummary(applied) + "  ›");
    }

    /** The Preset mood row's value: Custom, All or the size of the facet pool. */
    private String moodSummary(String applied) {
        if ("all".equals(applied) && mood.exhausted()) return "All (mix empty)";
        if ("facets".equals(applied)) {
            // The engine's count is the truth; the table's count stands in while the category is pending.
            int engine = ProjectMJNI.isMusicCategoryPending() ? 0 : ProjectMJNI.getCategoryPresetCount("facets");
            if (engine > 0) return numberFormat.format(engine) + " presets";
            PresetFacets.Selection selection = mood.selection();
            return selection == null ? "All" : numberFormat.format(selection.poolSize()) + " presets";
        }
        return MusicCategories.label(applied);
    }

    private Set<String> favoritePresets() {
        return new HashSet<>(prefs.getStringSet(PREF_FAVORITES, Collections.<String>emptySet()));
    }

    private void saveFavorites(Set<String> favorites) {
        prefs.edit().putStringSet(PREF_FAVORITES, new HashSet<>(favorites)).apply();
        ProjectMJNI.setFavorites(favorites.toArray(new String[0]));
        if (favoritesPlaying && favorites.isEmpty()) stopFavoritesPlayback();
        updateFavoriteRows();
    }

    private void toggleCurrentFavorite() {
        if (currentPresetPath == null || currentPresetPath.isEmpty()) {
            Toast.makeText(this, "The current visualizer is not ready yet", Toast.LENGTH_SHORT).show();
            return;
        }
        Set<String> favorites = favoritePresets();
        if (!favorites.remove(currentPresetPath)) favorites.add(currentPresetPath);
        saveFavorites(favorites);
    }

    private void showMoodMenu() {
        if (favoritesPlaying) {
            Toast.makeText(this, "Stop the Favorites collection before changing the preset mood", Toast.LENGTH_SHORT).show();
            return;
        }
        showMenu(Menu.MOOD);
    }

    private void toggleFavoritesPlayback() {
        if (favoritesPlaying) {
            stopFavoritesPlayback();
            return;
        }
        Set<String> favorites = favoritePresets();
        if (favorites.isEmpty()) {
            Toast.makeText(this, "Add a visualizer to Favorites first", Toast.LENGTH_SHORT).show();
            return;
        }
        ProjectMJNI.setFavorites(favorites.toArray(new String[0]));
        if (ProjectMJNI.getCategoryPresetCount("favorites") == 0) {
            Toast.makeText(this, "No saved favorites are available in the installed collection", Toast.LENGTH_SHORT).show();
            return;
        }
        favoritesPreviousAutoChange = prefs.getBoolean(PREF_AUTO_CHANGE, true);
        ProjectMJNI.setAutoChange(true);  // collection playback advances even if normal auto-change is off
        favoritesPlaying = true;
        updateAutoChangeRow();
        requestedMusicCategory = "favorites";
        ProjectMJNI.setMusicCategory("favorites");
        updateFavoriteRows();
    }

    private void stopFavoritesPlayback() {
        if (!favoritesPlaying) return;
        favoritesPlaying = false;
        ProjectMJNI.setAutoChange(favoritesPreviousAutoChange);
        updateAutoChangeRow();
        mood.apply();  // restore the saved All, Custom or mood selection
        requestedMusicCategory = prefs.getString(PREF_MUSIC_CATEGORY, "all");
        updateFavoriteRows();
    }

    private void updateFavoriteRows() {
        if (favoriteCurrentRow == null || playFavoritesRow == null) return;
        Set<String> favorites = favoritePresets();
        boolean currentIsFavorite = currentPresetPath != null && favorites.contains(currentPresetPath);
        favoriteCurrentRow.setActionValue(currentIsFavorite ? "Remove" : "Add");
        playFavoritesRow.setActionValue((favoritesPlaying ? "Stop" : "Play") + "  ·  "
                + numberFormat.format(favorites.size()));
    }

    private void updateAutoChangeRow() {
        if (autoChangeRow == null) return;
        boolean selected = favoritesPlaying || prefs.getBoolean(PREF_AUTO_CHANGE, true);
        autoChangeRow.setup("Auto change", new String[]{"Off", "On"}, selected ? 1 : 0, true, index -> {
            boolean enabled = index == 1;
            ProjectMJNI.setAutoChange(enabled);
            prefs.edit().putBoolean(PREF_AUTO_CHANGE, enabled).apply();
            if (favoritesPlaying) favoritesPreviousAutoChange = enabled;
        });
    }

    /** Loads the facet table (official collection first, else the bundled one) when its source changed. */
    private void reloadMood() {
        File official = OfficialCollection.attributesFile(this);
        String source = official == null ? "assets" : official.getAbsolutePath() + "@" + official.lastModified();
        if (mood != null && source.equals(moodSource)) return;
        boolean replacing = mood != null;
        moodSource = source;
        // A committed official collection without attributes (downloaded before collections carried
        // them) offers no facets, only the collection; the Mood header says how to get them.
        boolean outdatedDownload = official != null && !official.isFile();
        moodFacets = official == null ? PresetFacets.load(getAssets()) : outdatedDownload ? null : parseFacets(official);
        mood = new MoodFacetsController(moodFacets, new MoodFacetsController.Prefs() {
            @Override public String get(String key, String fallback) { return prefs.getString(key, fallback); }
            @Override public void put(String key, String value) { prefs.edit().putString(key, value).apply(); }
        }, new MoodFacetsController.Engine() {
            @Override public void setPresetPool(String[] names) { ProjectMJNI.setPresetPool(names); }
            @Override public void setMusicCategory(String id) {
                requestedMusicCategory = id;
                ProjectMJNI.setMusicCategory(id);
            }
            @Override public int count(String category) { return ProjectMJNI.getCategoryPresetCount(category); }
            @Override public boolean customPending() { return ProjectMJNI.isCustomPresetPackPending(); }
        }, skipList(), outdatedDownload);
        moodRevision++;
        if (replacing) {
            buildMoodRows();
            mood.apply();  // the pool from the new table
        }
    }

    private static PresetFacets parseFacets(File file) {
        try (java.io.Reader reader = new java.io.InputStreamReader(new java.io.FileInputStream(file),
                java.nio.charset.StandardCharsets.UTF_8)) {
            return PresetFacets.parse(reader);
        } catch (IOException | RuntimeException unreadable) {
            Log.w(TAG, "Preset attributes unreadable: " + file, unreadable);
            return null;
        }
    }

    /** The engine's skip list, re-read only when the file changed; one per activity. */
    private SkipListFile skipList() {
        if (skipListFile == null) skipListFile = new SkipListFile(ProjectMCore.skipListFile(this));
        return skipListFile;
    }

    /** One FacetRow per facet group; none without a facet table. */
    private void buildMoodRows() {
        if (moodRows == null) return;
        moodRows.removeAllViews();
        facetRows.clear();
        if (moodFacets == null) return;
        for (PresetFacets.Group group : moodFacets.groups()) {
            FacetRow row = new FacetRow(this);
            row.bind(group.label, group.options, id -> {
                mood.toggle(id);
                renderMood();
            });
            moodRows.addView(row, new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
            facetRows.add(row);
        }
        renderMood();
    }

    /** Shows the Mood state: selected options, live counts, dimmed options, header and collection. */
    private void renderMood() {
        if (moodMenu == null || mood == null) return;
        moodRevision++;
        boolean bundled = "bundled".equals(mood.collection());
        // One skip list read for every count, the dimming and the header.
        MoodFacetsController.Snapshot snapshot = mood.snapshot();
        if (snapshot.selection() != null) {
            Set<String> selected = mood.selected();
            Map<String, Integer> counts = new HashMap<>();
            Set<String> dimmed = new HashSet<>();
            for (PresetFacets.Group group : moodFacets.groups()) {
                for (PresetFacets.Option option : group.options) {
                    // "→ N": the presets left if this option were toggled (for a selected one, without it).
                    counts.put(option.id, snapshot.optionCount(option.id));
                    if (snapshot.isDimmed(option.id)) dimmed.add(option.id);
                }
            }
            for (FacetRow row : facetRows) row.update(selected, counts, dimmed, bundled);
        }
        setText(moodHeader, snapshot.header());
        // Custom plays without facets: Clear all would wipe the hidden stored selection, so it rests.
        if (moodClearRow != null) moodClearRow.setAlpha(mood.canClear() ? 1f : 0.4f);
        refreshMoodCollectionRow();
        refreshMusicCategory();
    }

    /** The collection choice appears while a custom pack is installed or Custom is chosen. */
    private void refreshMoodCollectionRow() {
        boolean custom = "custom".equals(mood.collection());
        // Shown while Custom is chosen too, so the viewer can always switch back.
        boolean available = custom || ProjectMJNI.getCategoryPresetCount("custom") > 0;
        int visibility = available ? View.VISIBLE : View.GONE;
        if (moodCollectionRow.getVisibility() == visibility && Boolean.valueOf(custom).equals(moodCollectionRow.getTag())) return;
        moodCollectionRow.setVisibility(visibility);
        moodCollectionRow.setTag(custom);
        moodCollectionRow.setup("Collection", new String[]{"Built-in", "Custom"}, custom ? 1 : 0, true, index -> {
            mood.setCollection(index == 1 ? "custom" : "bundled");
            renderMood();
        });
    }

    private void showCustomPackUpload() {
        if (customPackServer != null) return;
        File root = new File(getNoBackupFilesDir(), "custom-presets");
        TextView message = new TextView(this);
        message.setTextSize(18);
        try {
            customPackServer = new PresetPackUploadServer(root, PresetPackUploadServer.localAddress(), new PresetPackUploadServer.Commit() {
                private long request;
                @Override public void prepare(CustomPresetPack.Pack pack, CustomPresetPack.Cancellation cancel) throws IOException {
                    long restore = ((ProjectMApplication)getApplication()).customRestoreRequest();
                    if (restore != 0) CustomPresetPack.awaitStatus(restore, 2,
                            ProjectMJNI::getCustomPresetPackStatus, cancel, 30000);
                    request = ProjectMJNI.prepareCustomPresetPack(pack.directory.getAbsolutePath());
                    CustomPresetPack.awaitStatus(request, 1, ProjectMJNI::getCustomPresetPackStatus, cancel, 30000);
                }
                @Override public void imported(CustomPresetPack.Pack pack) throws IOException {
                    File previous = CustomPresetPack.current(root);
                    customPackCommitting = true;
                    boolean committed = false;
                    try {
                        CustomPresetPack.activate(root, pack);
                        if (!ProjectMJNI.commitCustomPresetPack(request)) {
                            CustomPresetPack.restore(root, previous);
                            throw new IOException("Preset library changed during import; previous pack retained. Try again.");
                        }
                        prefs.edit().putString(PREF_MUSIC_CATEGORY, "custom")
                                .putString(MoodFacetsController.PREF_COLLECTION, "custom")
                                .putString("custom_pack_generation", pack.directory.getName()).apply();
                        CustomPresetPack.scheduleCleanup(root, directory -> ProjectMJNI.isCustomPresetPackInUse(directory.getAbsolutePath()));
                        committed = true;
                        handler.post(() -> {
                            customPackCommitting = false;
                            mood.setCollection("custom");
                            renderMood();
                            if (customPackDialog != null)
                                message.setText("Imported " + numberFormat.format(pack.count) + " presets and "
                                        + numberFormat.format(pack.textureCount) + " textures. Custom is now selected.\n\n"
                                        + "You can close this dialog or upload another ZIP to replace the pack.");
                        });
                    } finally {
                        if (!committed) customPackCommitting = false;
                    }
                }
                @Override public void abandoned() { ProjectMJNI.discardCustomPresetPack(request); }
            }, count -> handler.post(() -> {
                if (customPackDialog != null) message.setText(customUploadInstructions()
                        + "\n\n" + (count < 0 ? "Upload unsuccessful. Check the message in your browser and try again."
                        : "Importing: " + numberFormat.format(count) + " presets…"));
            }));
            message.setText(customUploadInstructions());
            int side = Math.min(dp(240), getResources().getDisplayMetrics().heightPixels - dp(160));
            Bitmap bitmap = Bitmap.createBitmap(UploadQrCode.pixels(customPackServer.url(), side), side, side, Bitmap.Config.ARGB_8888);
            BitmapDrawable drawable = new BitmapDrawable(getResources(), bitmap);
            drawable.setFilterBitmap(false);
            ImageView qr = new ImageView(this);
            qr.setId(R.id.custom_upload_qr);
            qr.setImageDrawable(drawable);
            qr.setContentDescription("Scan to upload a custom preset pack");
            LinearLayout content = new LinearLayout(this);
            content.setOrientation(LinearLayout.HORIZONTAL);
            content.setGravity(Gravity.CENTER_VERTICAL);
            content.setPadding(dp(24), dp(16), dp(24), dp(8));
            content.addView(qr, new LinearLayout.LayoutParams(side, side));
            LinearLayout.LayoutParams copy = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
            copy.leftMargin = dp(24);
            content.addView(message, copy);
            customPackDialog = new AlertDialog.Builder(this, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                    .setTitle("Custom preset pack")
                    .setView(content)
                    .setNegativeButton("Close", (dialog, which) -> {})
                    .create();
            customPackDialog.setOnDismissListener(dialog -> closeCustomPackUpload());
            handler.removeCallbacks(hideMenu);
            customPackDialog.show();
            customPackDialog.getWindow().setLayout(Math.min(dp(720), getResources().getDisplayMetrics().widthPixels - dp(96)),
                    android.view.ViewGroup.LayoutParams.WRAP_CONTENT);
        } catch (IOException failure) {
            closeCustomPackUpload();
            Toast.makeText(this, failure.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private String customUploadInstructions() {
        return "Upload one ZIP with up to 50,000 .milk presets. "
                + "Supported texture images are imported too. Other files are ignored. "
                + "A successful upload replaces the previous pack and selects Custom. Keep this dialog open.";
    }

    private void closeCustomPackUpload() {
        if (customPackServer != null) { customPackServer.close(); customPackServer = null; }
        AlertDialog dialog = customPackDialog;
        customPackDialog = null;
        if (dialog != null && dialog.isShowing()) dialog.dismiss();
        if (resumed && menu != Menu.NONE) handler.postDelayed(hideMenu, MENU_AUTO_HIDE_MS);
    }

    private String lastExitSummary() {
        return ExitDiagnostics.summary(recentExits, Build.VERSION.SDK_INT, System.currentTimeMillis());
    }

    /** Settings › Advanced › Last exit: the latest exits and what the engine was doing then. */
    private void showExitReport(List<ExitDiagnostics.Exit> exits) {
        String header = String.format(Locale.US, "%s %s, Android %s (API %d)%nGPU: %s%nNow: background compile %s, shader binary cache %s%n",
                Build.MANUFACTURER, Build.MODEL, Build.VERSION.RELEASE, Build.VERSION.SDK_INT,
                renderer.getGlRenderer().isEmpty() ? "unknown" : renderer.getGlRenderer(),
                prefs.getBoolean(PREF_BACKGROUND_COMPILE, true) ? "on" : "off",
                prefs.getBoolean(PREF_SHADER_BINARY_CACHE, true) ? "on" : "off");
        String report = ExitDiagnostics.report(exits, Build.VERSION.SDK_INT,
                ExitDiagnostics.previousTrail(), System.currentTimeMillis(), header);
        Log.i(TAG, "Exit report:\n" + report);
        handler.removeCallbacks(hideMenu);
        AlertDialog dialog = new AlertDialog.Builder(this, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle("Recent exits")
                .setMessage(report)
                .setNegativeButton("Close", (d, which) -> {})
                .create();
        dialog.setOnDismissListener(d -> {
            if (resumed && menu != Menu.NONE) handler.postDelayed(hideMenu, MENU_AUTO_HIDE_MS);
        });
        dialog.show();
    }

    private void refreshStatus() {
        CustomPresetPack.retryPendingCleanups(directory -> ProjectMJNI.isCustomPresetPackInUse(directory.getAbsolutePath())
                || ProjectMJNI.isOfficialPresetPackInUse(directory.getAbsolutePath()));
        refreshMusicCategory();
        int change = ProjectMJNI.getPresetChangeCounter();
        if (change != lastPresetChange) {
            lastPresetChange = change;
            currentPreset = displayName(ProjectMJNI.getCurrentPresetName());
            currentPresetPath = ProjectMJNI.getCurrentPresetName();
            if (!currentPreset.isEmpty()) {
                setText(presetName, currentPreset);
                presetName.setSelected(true);  // start marquee for long names
            }
        }
        if (BuildConfig.TOUCHSCREEN) audioInputRow.setActionValue(phoneAudio.label());
        if (menu == Menu.NONE) return;

        int skipped = ProjectMJNI.getSkippedCount();
        String mode = quality.isAuto() ? "auto" : quality.isNative() ? "native" : "fixed";
        if (menu == Menu.MAIN) {
            updateFavoriteRows();
            setText(presetMeta, numberFormat.format(ProjectMJNI.getPresetCount()) + " presets in rotation"
                    + (skipped > 0 ? "  ·  " + numberFormat.format(skipped) + " skipped" : ""));
            setText(statusLine, String.format(Locale.US, "%5.1f fps  ·  %s %s",
                    renderer.getCurrentFps(), heightLabel(quality.currentHeight()), mode));
        } else if (menu == Menu.TRACK) {
            refreshTrackInfoRow();  // access may have been granted meanwhile
        } else if (menu == Menu.MOOD) {
            refreshMoodCollectionRow();  // a custom pack may have finished indexing meanwhile
            // New skips (blank detection, failed loads) change the pool, counts and dimming.
            if (mood.skipsChanged(skipped)) renderMood();
        } else {
            skippedRow.setActionValue(skipped > 0 ? numberFormat.format(skipped) + "  ·  Reset" : "None");
            lastExitRow.setActionValue(lastExitSummary());  // keeps its age current
            setText(diagnostics, String.format(Locale.US,
                    "Render  %dx%d (%s)%nRAM     %s%nPanel   %dx%d @ %.0f Hz%nUI      %dx%d%nFPS     %.1f of %d%nTrails  %s%nBlend   %s%nAudio   %s%nTrack   %s%nUpdate  %s%nDevice  %s tier, %d MB RAM%nGPU     %s",
                    renderer.getSurfaceWidth(), renderer.getSurfaceHeight(), mode,
                    quality.isMemoryConstrained() ? "resolution reduced for memory headroom" : "automatic headroom budget",
                    display.physicalWidth, display.physicalHeight, display.refreshRate,
                    display.uiWidth, display.uiHeight,
                    renderer.getCurrentFps(), frameRateTarget, ProjectMJNI.getNativeTrailsStatus(), transitionLabel(), audioLabel(), trackLabel(), updater.statusLabel(),
                    profile.tier.name().toLowerCase(Locale.US), profile.totalRamMb,
                    renderer.getGlRenderer().isEmpty() ? "unknown" : renderer.getGlRenderer()));
        }
    }

    private String transitionLabel() {
        if (ProjectMJNI.isLightweightTransition()) return "lightweight";
        if (prefs.getInt(PREF_TRANSITION_MODE, ProjectMJNI.TRANSITION_AUTO) != ProjectMJNI.TRANSITION_AUTO) {
            return "blend";
        }
        int percent = ProjectMJNI.getBlendScalePercent();
        return percent > 0 ? "blend at " + percent + "% (auto)" : "blend (auto)";
    }

    /** Short status next to the level bar in the main panel. */
    private String audioStatus(float level) {
        if (!hasAudioPermission()) return "No access";
        if ((!BuildConfig.TOUCHSCREEN && audioVisualizer == null) || level <= 0f) return "No sound";
        return level < 0.02f ? "Very quiet" : "Listening";
    }

    /** Audio input as seen by the engine: tells whether the TV actually delivers sound to us. */
    private String audioLabel() {
        if (!hasAudioPermission()) return "no capture (permission?)";
        if (BuildConfig.TOUCHSCREEN) return phoneAudio.label();
        if (audioVisualizer == null) return "no player session found yet";
        String source = sourceName();
        float level = ProjectMJNI.getAudioLevel();
        if (level <= 0f) return source + ", silent / no data";
        return String.format(Locale.US, "%s, %.2f %s", source, level, level < 0.02f ? "(very quiet)" : "(live)");
    }

    /** From the music app's media session. A new track also allows one search for its audio. */
    private void onTrackChanged(TrackWatcher.Track track, boolean newTrack) {
        if (newTrack && resumed) {
            // On audioThread, so no watch run is in progress: the chain is restarted, not doubled.
            audioHandler.post(() -> {
                trackSearchDue = true;
                audioHandler.removeCallbacks(audioWatch);
                if (resumed) audioHandler.post(audioWatch);
            });
        }
        handler.removeCallbacks(trackStopped);
        boolean restart = newTrack || !trackPlaying;  // a new track, or playing again after a pause
        trackPlaying = true;
        currentTrack = track;
        showTrack(restart);
    }

    /** Nothing plays: the track goes, unless playback resumes within a moment (buffering, seeking). */
    private void onTrackStopped() {
        handler.removeCallbacks(trackStopped);
        handler.postDelayed(trackStopped, TRACK_STOP_GRACE_MS);
    }

    private boolean trackInfoOn() {
        return prefs.getBoolean(PREF_TRACK_INFO, true);
    }

    /** How long a track is shown, 0 for as long as it plays. */
    private int trackSeconds() {
        return prefs.getInt(PREF_TRACK_SECONDS, 0);
    }

    private boolean trackPill() {
        return prefs.getBoolean(PREF_TRACK_PILL, false);
    }

    /**
     * Shows the playing track in the upper-left corner, or in the pill with Pill style.
     * {@code restart} shows it (again) for the chosen time; otherwise only a track on screen is
     * updated (the artist or cover arrived, or playback resumed within the grace period).
     */
    private void showTrack(boolean restart) {
        if (currentTrack == null || !trackPlaying || !trackInfoOn()) return;
        long shownMs = trackSeconds() * 1000L;
        if (trackPill()) {
            if (!restart && !pillHoldsTrack) return;
            pillHoldsTrack = true;
            showPill(R.drawable.ic_music_note, currentTrack.label(), restart, shownMs);
            return;
        }
        if (!restart && !trackCorner.isVisible()) return;
        trackCorner.show(currentTrack);
        if (!restart) return;
        handler.removeCallbacks(trackTimeUp);
        if (shownMs > 0) handler.postDelayed(trackTimeUp, shownMs);
    }

    /** A Track display setting changed: show the track (again) as it now says, with the panel open. */
    private void applyTrackDisplay() {
        if (!trackInfoOn() || trackPill()) trackCorner.hide();
        if ((!trackInfoOn() || !trackPill()) && pillHoldsTrack) {
            pillHoldsTrack = false;
            handler.removeCallbacks(hideNowPlaying);
            fade(nowPlaying, false);
        }
        showTrack(true);
    }

    /** Hides the track, wherever it is shown; notices in the pill stay. */
    private void hideTrack() {
        handler.removeCallbacks(trackTimeUp);
        trackCorner.hide();
        if (pillHoldsTrack) {
            pillHoldsTrack = false;
            handler.removeCallbacks(hideNowPlaying);
            fade(nowPlaying, false);
        }
    }

    /** Text in the lower-left pill; {@code restart} shows it (again) for {@code shownMs}, 0 for good. */
    private void showPill(int icon, String text, boolean restart, long shownMs) {
        nowPlayingIcon.setImageResource(icon);
        setText(nowPlayingText, text);
        nowPlayingText.setSelected(true);
        if (!restart) return;
        fade(nowPlaying, true);
        handler.removeCallbacks(hideNowPlaying);
        if (shownMs > 0) handler.postDelayed(hideNowPlaying, shownMs);
    }

    /** A notice in the pill for 20 s; it takes the pill from a track shown there. */
    private void showNotice(int icon, String text) {
        pillHoldsTrack = false;
        showPill(icon, text, true, NOTICE_SHOWN_MS);
    }

    /** Music plays at start but no player session carries it: say so in the pill, once. */
    private void showNoAudioNotice() {
        if (!resumed || menu != Menu.NONE) return;
        showNotice(R.drawable.ic_music_note, "No audio detected");
    }

    /**
     * A downloaded update: the settings panel gets an Install row at the top, and the pill says so
     * once per launch.
     */
    private void onUpdateReady(String version) {
        if (!updater.isEnabled()) return;
        installRow.setActionValue("Install " + version);
        installRow.setVisibility(View.VISIBLE);
        if (updateAnnounced || menu != Menu.NONE) return;
        updateAnnounced = true;
        showNotice(R.drawable.ic_system_update, getString(R.string.app_name) + " " + version
                + " is ready to install: open the settings");
    }

    /** Diagnostics line: whether the playing track can be read, and how it is shown. */
    private String trackLabel() {
        if (!trackWatcher.hasAccess()) return "no access (" + TRACK_ACCESS_PATH + ")";
        if (!trackInfoOn()) return "off";
        int seconds = trackSeconds();
        return (trackPill() ? "pill" : "corner") + ", " + (seconds == 0 ? "always" : seconds + " s");
    }

    /** Track info: Off/On with access, otherwise an action that explains how to allow it. */
    private void refreshTrackInfoRow() {
        boolean access = trackWatcher.hasAccess();
        if (trackInfoRowAccess != null && trackInfoRowAccess == access) return;
        trackInfoRowAccess = access;
        if (access) {
            trackInfoRow.setup("Track info", new String[]{"Off", "On"}, trackInfoOn() ? 1 : 0, true, index -> {
                prefs.edit().putBoolean(PREF_TRACK_INFO, index == 1).apply();
                applyTrackDisplay();
            });
        } else {
            trackInfoRow.setupAction("Track info", "Off  ·  Allow", this::explainTrackAccess);
        }
    }

    private static String displayName(String preset) {
        if (preset == null) return "";
        int slash = preset.lastIndexOf('/');
        String name = slash >= 0 ? preset.substring(slash + 1) : preset;
        return name.regionMatches(true, Math.max(0, name.length() - 5), ".milk", 0, 5)
                ? name.substring(0, name.length() - 5) : name;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    // ---------------------------------------------------------------------------------------
    // Remote control
    // ---------------------------------------------------------------------------------------

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (menu != Menu.NONE) {  // any interaction keeps the menu open
            handler.removeCallbacks(hideMenu);
            handler.postDelayed(hideMenu, MENU_AUTO_HIDE_MS);
        }
        return super.dispatchKeyEvent(event);
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (menu != Menu.NONE) {
            if (keyCode == KeyEvent.KEYCODE_BACK) {
                showMenu(menu == Menu.MAIN ? Menu.NONE : Menu.MAIN);
                return true;
            }
            if (keyCode == KeyEvent.KEYCODE_MENU) {
                showMenu(Menu.NONE);
                return true;
            }
            return super.onKeyDown(keyCode, event);  // focus navigation inside the panel
        }
        switch (keyCode) {
            case KeyEvent.KEYCODE_DPAD_RIGHT:
            case KeyEvent.KEYCODE_MEDIA_NEXT:
            case KeyEvent.KEYCODE_MEDIA_FAST_FORWARD:
                ProjectMJNI.randomPreset(true);
                return true;
            case KeyEvent.KEYCODE_DPAD_LEFT:
            case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
            case KeyEvent.KEYCODE_MEDIA_REWIND:
                ProjectMJNI.previousPreset(true);
                return true;
            case KeyEvent.KEYCODE_DPAD_UP:
            case KeyEvent.KEYCODE_DPAD_DOWN:
            case KeyEvent.KEYCODE_INFO:
                showTrack(true);  // the playing track again (nothing without access)
                return true;
            case KeyEvent.KEYCODE_DPAD_CENTER:
            case KeyEvent.KEYCODE_ENTER:
            case KeyEvent.KEYCODE_MENU:
                showMenu(Menu.MAIN);
                return true;
            default:
                return super.onKeyDown(keyCode, event);
        }
    }

    // ---------------------------------------------------------------------------------------
    // Audio (all Visualizer calls run on audioThread)
    // ---------------------------------------------------------------------------------------

    private boolean hasAudioPermission() {
        return Build.VERSION.SDK_INT < 23
                || checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == AUDIO_PERMISSION_REQUEST && grantResults.length > 0
                && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            onAudioPermissionGranted();
        } else {
            Log.w(TAG, "Audio permission denied - visuals will not react to music");
        }
    }

    private void onAudioPermissionGranted() {
        if (BuildConfig.TOUCHSCREEN) phoneAudio.permissionGranted();
        else audioHandler.post(this::startAudio);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (BuildConfig.TOUCHSCREEN && requestCode == PhoneAudioInput.CONSENT_REQUEST) {
            phoneAudio.result(resultCode, data);
        }
    }

    private String sourceName() {
        if (BuildConfig.TOUCHSCREEN) return phoneAudio.label();
        int session = audioSession;
        return session != 0 ? "player session " + session : "none";
    }

    private void stopAudio() {
        if (audioVisualizer == null) return;
        audioHandler.removeCallbacks(audioPoll);
        audioVisualizer.setEnabled(false);
        audioVisualizer.release();
        audioVisualizer = null;
        Log.i(TAG, "Standard audio capture released");
    }

    private void onWaveform(byte[] waveform, int length) {
        ProjectMJNI.addWaveform(waveform, length);
        if (PlayerSessionFinder.rms(waveform, length) >= PlayerSessionFinder.MIN_RMS) {
            lastSignalAt = SystemClock.elapsedRealtime();
        }
    }

    private void startAudio() {
        if (BuildConfig.TOUCHSCREEN || audioVisualizer != null || audioSession == 0) return;
        Visualizer visualizer = null;
        try {
            // The player's session found by PlayerSessionFinder. The waveform is 8-bit unsigned mono PCM, passed to projectM
            // unchanged. Callbacks arrive on the looper of the thread that registers the listener,
            // i.e. audioThread.
            visualizer = new Visualizer(audioSession);
            // A Visualizer on a session is shared. If another client holds it enabled and keeps
            // control, ours cannot be configured or start its capture callbacks, only be read:
            // then the waveform is polled instead.
            boolean controlled = !visualizer.getEnabled() || visualizer.setEnabled(false) == Visualizer.SUCCESS;
            if (controlled) {
                try {
                    visualizer.setCaptureSize(Visualizer.getCaptureSizeRange()[1]);
                } catch (IllegalStateException e) {
                    Log.w(TAG, "Audio capture: keeping the default capture size on " + sourceName());
                }
                visualizer.setDataCaptureListener(new Visualizer.OnDataCaptureListener() {
                    @Override
                    public void onWaveFormDataCapture(Visualizer v, byte[] waveform, int samplingRate) {
                        if (waveform != null) onWaveform(waveform, waveform.length);
                    }

                    @Override
                    public void onFftDataCapture(Visualizer v, byte[] fft, int samplingRate) {}
                }, Visualizer.getMaxCaptureRate(), true, false);
            }
            int status = controlled ? visualizer.setEnabled(true) : Visualizer.SUCCESS;
            audioVisualizer = visualizer;
            lastSignalAt = SystemClock.elapsedRealtime();  // grace period before judging silence
            audioPolled = !controlled;
            if (audioPolled) {
                pollBuffer = new byte[visualizer.getCaptureSize()];
                audioHandler.post(audioPoll);
            }
            Log.i(TAG, "Audio capture enabled on " + sourceName() + " (status " + status
                    + (controlled ? ")" : ", shared: polled)"));
        } catch (RuntimeException e) {
            Log.e(TAG, "Audio capture unavailable", e);
            if (visualizer != null) visualizer.release();
            audioVisualizer = null;
            // The player's session is gone: the watch searches again after the backoff.
            audioSession = 0;
            nextSearchAt = SystemClock.elapsedRealtime() + SEARCH_RETRY_MS;
            Log.i(TAG, "Audio source now: none");
        }
    }

    /** Reads the waveform of a shared Visualizer whose capture callbacks we cannot start. */
    private final Runnable audioPoll = new Runnable() {
        @Override
        public void run() {
            Visualizer visualizer = audioVisualizer;
            if (visualizer == null || !resumed) return;  // setAudioEnabled(true) restarts it
            audioHandler.postDelayed(this, AUDIO_POLL_MS);
            try {
                if (visualizer.getWaveForm(pollBuffer) == Visualizer.SUCCESS) {
                    onWaveform(pollBuffer, pollBuffer.length);
                }
            } catch (RuntimeException ignored) {
                // released underneath us; the watch notices the silence
            }
        }
    };

    /**
     * While music plays but we hear nothing (no session yet, or the player moved to a new one), look
     * for the session of the app that plays it (see PlayerSessionFinder). While the player's
     * session carries the music, and while nothing plays, no search runs.
     */
    private final Runnable audioWatch = new Runnable() {
        @Override
        public void run() {
            audioHandler.postDelayed(this, AUDIO_WATCH_MS);
            if (!resumed || !hasAudioPermission()) return;
            long now = SystemClock.elapsedRealtime();
            if (ProjectMJNI.getAudioLevel() > 0f) {
                lastSignalAt = now;
                noAudioNoticeDue = false;  // audio was heard after the (re)start
            }
            if (!audioManager.isMusicActive()) {
                musicActive = false;
                return;
            }
            if (!musicActive) {  // music (re)started
                musicActive = true;
                lastSignalAt = now;
                // If we hear nothing, look for the player's session right away (the last one
                // first): waiting for 4 s of silence first only delayed the visuals after a launch.
                if (ProjectMJNI.getAudioLevel() > 0f) return;
                lastSignalAt = now - SILENCE_BEFORE_SEARCH_MS;
            }
            if (now - lastSignalAt < SILENCE_BEFORE_SEARCH_MS) return;
            // After a search that found nothing, wait a minute, unless a new track has started
            // since: each track allows one search. The session found last is probed first.
            if (now < nextSearchAt && !trackSearchDue) return;
            trackSearchDue = false;
            int previous = audioSession;
            stopAudio();  // releases our instance so the probe sees the session as it is
            int found = PlayerSessionFinder.find(audioManager.generateAudioSessionId(), lastPlayerSession);
            if (found == 0) {
                nextSearchAt = now + SEARCH_RETRY_MS;
                if (noAudioNoticeDue) handler.post(MainActivity.this::showNoAudioNotice);
            }
            noAudioNoticeDue = false;  // only the first search after a (re)start tells
            if (found != 0) {  // otherwise keep the current session
                audioSession = found;
                lastPlayerSession = found;
                nextSearchAt = 0;
                prefs.edit().putInt(PREF_LAST_PLAYER_SESSION, found).apply();
            }
            startAudio();
            // tools/tv-diagnostics.sh reports the latest of these lines as the source in use.
            if (audioSession != previous) Log.i(TAG, "Audio source now: " + sourceName());
        }
    };

    private void setAudioEnabled(boolean enabled) {
        audioHandler.post(() -> {
            if (audioVisualizer == null) return;
            audioVisualizer.setEnabled(enabled);  // no effect on a polled, shared Visualizer
            audioHandler.removeCallbacks(audioPoll);
            if (enabled && audioPolled) audioHandler.post(audioPoll);
        });
    }

    // ---------------------------------------------------------------------------------------
    // Lifecycle
    // ---------------------------------------------------------------------------------------

    @Override
    protected void onResume() {
        super.onResume();
        quality.revalidateForResume(false);
        visualizerView.onResume();
        resumed = true;
        if (hasAudioPermission()) audioHandler.post(this::startAudio);  // no-op if running
        setAudioEnabled(true);
        audioHandler.post(() -> {  // the watch starts fresh, and searches right away
            musicActive = false;
            noAudioNoticeDue = true;
            nextSearchAt = 0;
        });
        audioHandler.removeCallbacks(audioWatch);
        if (BuildConfig.TOUCHSCREEN) phoneAudio.resume();
        else audioHandler.postDelayed(audioWatch, FIRST_WATCH_MS);
        handler.post(uiRefresh);
        if (menu == Menu.MAIN) handler.post(audioMeterRefresh);
        updater.onResume();
        officialCollection.onResume();
        // Checked on every resume: access may have been granted while the app was in the background.
        if (!trackWatcher.start()) {
            Log.i(TAG, "Track titles off: no notification-listener access");
            // Dismiss is saved permanently; Configure is only an acknowledgement for this launch.
            // Track display › Track info always remains available on request.
            if (!trackAccessPromptShown && !prefs.getBoolean(PREF_TRACK_ACCESS_EXPLAINED, false) && hasAudioPermission()) {
                handler.postDelayed(() -> {
                    if (!resumed || trackAccessPromptShown || trackWatcher.hasAccess() || prefs.getBoolean(PREF_TRACK_ACCESS_EXPLAINED, false)) return;
                    explainTrackAccess();
                }, TRACK_ACCESS_DELAY_MS);
            }
        }
    }

    /** Where Android TV settings keep notification access. */
    private static final String TRACK_ACCESS_PATH =
            "Settings › Device Preferences › Apps › Special app access › Notification access";

    /**
     * Explains how to allow notification-listener access, which the app needs to read the playing
     * track from the music app's media session. Configure opens settings; the user enables access.
     */
    private void explainTrackAccess() {
        if (trackAccessDialog != null && trackAccessDialog.isShowing()) return;
        trackAccessPromptShown = true;
        trackAccessDialog = new AlertDialog.Builder(this, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle("Show track titles")
                .setMessage("To show the cover, artist and title of the playing track, allow " + getString(R.string.app_name)
                        + " under\n\n" + TRACK_ACCESS_PATH + "\n\nThe app reads no notifications; Android requires"
                        + " this access to see which track the music app is playing.")
                .setPositiveButton("Configure", (dialog, which) -> openTrackAccessSettings())
                .setNegativeButton("Dismiss", (dialog, which) ->
                        prefs.edit().putBoolean(PREF_TRACK_ACCESS_EXPLAINED, true).apply())
                .setOnDismissListener(dialog -> trackAccessDialog = null)
                .show();
    }

    private void openTrackAccessSettings() {
        boolean opened = TrackAccessNavigation.open(Build.VERSION.SDK_INT, action -> {
            Intent intent = new Intent(action);
            if (TrackAccessNavigation.DETAIL.equals(action)) {
                intent.putExtra("android.provider.extra.NOTIFICATION_LISTENER_COMPONENT_NAME",
                        new ComponentName(this, TrackListenerService.class).flattenToString());
            }
            try {
                startActivity(intent);
                return true;
            } catch (ActivityNotFoundException | SecurityException unavailable) {
                Log.i(TAG, "Notification access settings unavailable for " + action);
                return false;
            }
        });
        if (!opened) Toast.makeText(this, "Open " + TRACK_ACCESS_PATH, Toast.LENGTH_LONG).show();
    }


    @Override
    protected void onPause() {
        closeCustomPackUpload();
        trackWatcher.stop();
        handler.removeCallbacks(uiRefresh);
        handler.removeCallbacks(audioMeterRefresh);
        resumed = false;
        if (BuildConfig.TOUCHSCREEN) phoneAudio.pause();
        updater.onPause();
        officialCollection.onPause();
        audioHandler.removeCallbacks(audioWatch);
        setAudioEnabled(false);
        visualizerView.onPause();
        super.onPause();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (officialCollection != null) officialCollection.focusChanged(hasFocus);
        if (hasFocus) {
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        }
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (BuildConfig.TOUCHSCREEN) phoneAudio.pause();
        audioHandler.removeCallbacks(audioWatch);
        audioHandler.post(this::stopAudio);
        audioThread.quitSafely();
        updater.detach(updateListener);
        officialCollection.onDestroy();
        // projectM owns GL objects, so it is destroyed on the GL thread. If the thread is already
        // gone, the next onSurfaceCreated() cleans up instead.
        visualizerView.queueEvent(renderer::release);
        super.onDestroy();
    }

    void holdCollectionDialog(boolean held) {
        handler.removeCallbacks(hideMenu);
        if (!held && resumed && menu != Menu.NONE) handler.postDelayed(hideMenu, MENU_AUTO_HIDE_MS);
    }

    private String appVersion() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (PackageManager.NameNotFoundException e) {
            return "?";
        }
    }
}
