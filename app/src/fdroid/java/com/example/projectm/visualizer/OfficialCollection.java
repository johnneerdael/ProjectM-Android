package com.example.projectm.visualizer;

import android.app.*;
import android.content.*;
import android.os.*;
import android.view.View;
import nl.neerdael.projectm.core.*;
import java.util.Locale;
import java.util.concurrent.*;

/** Framework dialog/focus adapter. No transfer starts without the download button. */
final class OfficialCollection {
    private static final String OFFER_SHOWN="official_collection_offer_shown";
    private final Activity activity;
    private final SharedPreferences prefs;
    private final Handler handler;
    private final OfficialPresetDownload download;
    private final OptionRow row;
    private final OfficialPresetDownload.NativeIndex nativeIndex;
    private final OfficialPresetDownload.Listener listener=this::changed;
    private final Runnable offer=this::maybeOffer;
    private boolean resumed;
    private long resumedAt;
    private AlertDialog dialog;
    private boolean showingProgress;
    private Runnable collectionChanged;
    private String settledIdentity;  // the installed identity last reported to collectionChanged

    OfficialCollection(Activity activity,SharedPreferences prefs,Handler handler,VisualizerView view) {
        this.activity=activity;this.prefs=prefs;this.handler=handler;download=OfficialPresetDownload.get(activity);
        row=activity.findViewById(R.id.row_official_collection);
        row.setVisibility(View.VISIBLE);row.setupAction("Cream of the Crop","20 starter presets ›",this::open);
        nativeIndex=new OfficialPresetDownload.NativeIndex() {
            public long prepare(String directory){return ProjectMJNI.prepareOfficialPresetPack(directory);}
            public int status(long request){return ProjectMJNI.getOfficialPresetPackStatus(request);}
            public void discard(long request){ProjectMJNI.discardOfficialPresetPack(request);}
            public boolean inUse(String directory){return ProjectMJNI.isOfficialPresetPackInUse(directory);}
            public boolean commit(long request) {
                return commitOnGlThread(request,view::queueEvent,
                        ()->ProjectMJNI.commitOfficialPresetPack(request),
                        ProjectMJNI::getOfficialPresetPackStatus,
                        ()->ProjectMJNI.discardOfficialPresetPack(request),30000);
            }
        };
    }
    static boolean commitOnGlThread(long request,Executor gl,Callable<Boolean> commit,
            CustomPresetPack.IndexStatus status,Runnable discard,long timeoutMs) {
        Object gate=new Object();boolean[] abandoned={false};
        FutureTask<Boolean> task=new FutureTask<>(()->{
            synchronized(gate){return !abandoned[0]&&commit.call();}
        });
        try{gl.execute(task);return task.get(timeoutMs,TimeUnit.MILLISECONDS);}
        catch(Exception failed){
            if(failed instanceof InterruptedException)Thread.currentThread().interrupt();
            // A queued commit must never execute after rollback. If it has already
            // entered native publication, settle its result before reporting failure.
            synchronized(gate){
                abandoned[0]=true;task.cancel(false);
                if(status.status(request)==2)return true;
                discard.run();return false;
            }
        }
    }
    static void restore(Context context){OfficialPresetDownload.get(context);}
    /** Runs on the UI thread whenever the installed collection settles on a different identity (installed, replaced or removed). */
    void setOnCollectionChanged(Runnable listener){collectionChanged=listener;}
    /**
     * The first settled report always counts as a change: the cold-start restore may have validated
     * and cleared a corrupt pointer before this listener attached, after Mood read the unvalidated
     * pointer. The reload is keyed on the table source, so an unchanged source costs nothing.
     */
    static boolean settledChange(String previous,boolean busy,String identity) {
        if(busy)return false;
        return previous==null||!previous.equals(identity);
    }
    /**
     * The preset attributes of the official generation committed in the native engine; null while
     * the engine uses the bundled starters (no collection, a pending first restore, or a failed or
     * timed-out restore whose durable pointer remains), so the starter table applies. A pending
     * install or removal keeps the previous source; the settled report reloads Mood. A committed
     * pack from an archive without attributes yields the expected path although it does not exist,
     * so the starter table never describes a full library. No file is read or hashed here.
     */
    static java.io.File attributesFile(Context context) {
        return attributesFile(OfficialPresetDownload.get(context).committed());
    }
    static java.io.File attributesFile(java.io.File committedGeneration) {
        return committedGeneration==null?null:new java.io.File(committedGeneration,"preset-attributes/attributes.tsv");
    }
    static boolean shouldOffer(boolean seen,boolean resumed,boolean focus,boolean ready,String phase,String identity) {
        return !seen&&resumed&&focus&&ready&&identity.isEmpty()&&(phase.equals("idle")||phase.equals("error"));
    }
    void onResume(){resumed=true;resumedAt=SystemClock.elapsedRealtime();download.attach(handler,listener);handler.postDelayed(offer,3000);}
    void onPause(){resumed=false;handler.removeCallbacks(offer);download.detach(listener);download.cancel();close();}
    void onDestroy(){onPause();}
    void focusChanged(boolean focused){if(focused&&resumed)handler.post(offer);}
    private void maybeOffer() {
        if(!resumed||dialog!=null)return;
        long wait=3000-(SystemClock.elapsedRealtime()-resumedAt);
        if(wait>0){handler.removeCallbacks(offer);handler.postDelayed(offer,wait);return;}
        OfficialPresetDownload.Status status=download.status();
        if(shouldOffer(prefs.getBoolean(OFFER_SHOWN,false),resumed,activity.hasWindowFocus(),download.descriptor()!=null,status.phase,status.identity))open();
    }
    private static String size(long bytes){return String.format(Locale.getDefault(),"%.1f MiB",bytes/1048576.0);}
    private String message(OfficialPresetDownload.Status status) {
        OfficialPresetPack.Descriptor d=download.descriptor();
        if(d==null)return status.error==null?"Preparing the collection information…":status.error;
        if(status.busy())return status.phase.equals("downloading")?"Downloading: "+size(status.bytes)+" of "+size(status.total)+"\n\nCancel to keep the current presets.":"Collection: "+status.phase+"…";
        String text=status.identity.isEmpty()?"20 starter presets are ready to use offline. Download the full "+d.presetCount+"-preset collection for more variety, including all preset moods.":"The full collection is installed and available offline.";
        if(!status.identity.isEmpty()&&!status.identity.equals(d.identity))text+="\n\nA newer collection is available.";
        text+="\n\nDownload: "+size(d.bytes)+". Unpacked: "+size(d.expandedBytes)+".\nAllow "+size(d.bytes+d.expandedBytes+16L*1024*1024)+" of free storage to install.\n\nHosted on GitHub, outside F-Droid's build checks.";
        if(status.error!=null)text+="\n\n"+status.error;
        return text;
    }
    void open() {
        if(!resumed||dialog!=null||activity.isFinishing())return;
        OfficialPresetDownload.Status status=download.status();OfficialPresetPack.Descriptor d=download.descriptor();
        showingProgress=status.busy();
        AlertDialog.Builder builder=new AlertDialog.Builder(activity,android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle("Cream of the Crop").setMessage(message(status));
        if(status.busy())builder.setNegativeButton("Cancel",(v,which)->download.cancel());
        else {
            builder.setNegativeButton(status.identity.isEmpty()?"Use 20 starters":"Close",(v,which)->{});
            if(d!=null&&!d.identity.equals(status.identity))builder.setPositiveButton("Download (recommended)",(v,which)->download.start(d,nativeIndex));
            if(!status.identity.isEmpty())builder.setNeutralButton("Remove collection",(v,which)->download.remove(nativeIndex));
        }
        dialog=builder.create();
        dialog.setOnDismissListener(v->{dialog=null;((MainActivity)activity).holdCollectionDialog(false);});
        ((MainActivity)activity).holdCollectionDialog(true);
        dialog.show();
        dialog.getButton(AlertDialog.BUTTON_NEGATIVE).requestFocus();
        prefs.edit().putBoolean(OFFER_SHOWN,true).apply();
    }
    private void changed(OfficialPresetDownload.Status status) {
        if(!resumed)return;
        boolean settled=settledChange(settledIdentity,status.busy(),status.identity);
        if(!status.busy())settledIdentity=status.identity;
        if(settled&&collectionChanged!=null)collectionChanged.run();
        row.setActionValue(status.busy()?status.phase+" ›":status.phase.equals("error")?"Download failed ›":status.phase.equals("canceled")?"Canceled ›":status.identity.isEmpty()?"20 starter presets ›":"Full collection ›");
        if(dialog!=null){dialog.setMessage(message(status));if(showingProgress&&!status.busy())close();}
        maybeOffer();
    }
    private void close(){AlertDialog old=dialog;dialog=null;if(old!=null)old.dismiss();}
}
