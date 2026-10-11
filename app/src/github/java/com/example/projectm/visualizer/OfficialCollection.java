package com.example.projectm.visualizer;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import nl.neerdael.projectm.core.VisualizerView;

/** GitHub editions already bundle the complete official collection. */
final class OfficialCollection {
    OfficialCollection(Activity activity,SharedPreferences preferences,Handler handler,VisualizerView view) { }
    static void restore(Context context) { }
    void onResume() { }
    void onPause() { }
    void onDestroy() { }
    void focusChanged(boolean focused) { }
    void open() { }
}
