package com.example.projectm.visualizer;

import org.junit.Test;
import static org.junit.Assert.*;
import java.lang.reflect.Method;

public class OfficialCollectionTest {
    @Test public void initialOfferRequiresForegroundFocusAndNoInstalledCollection() throws Exception {
        Class<?> c=null;try{c=Class.forName("com.example.projectm.visualizer.OfficialCollection");}catch(ClassNotFoundException missing){}
        assertNotNull("official collection consent flow is missing",c);
        Method offer=c.getDeclaredMethod("shouldOffer",boolean.class,boolean.class,boolean.class,boolean.class,String.class,String.class);
        assertEquals(true,offer.invoke(null,false,true,true,true,"idle",""));
        assertEquals(false,offer.invoke(null,true,true,true,true,"idle",""));
        assertEquals(false,offer.invoke(null,false,false,true,true,"idle",""));
        assertEquals(false,offer.invoke(null,false,true,false,true,"idle",""));
        assertEquals(false,offer.invoke(null,false,true,true,false,"idle",""));
        assertEquals(false,offer.invoke(null,false,true,true,true,"restoring",""));
        assertEquals(false,offer.invoke(null,false,true,true,true,"installed","previous-collection"));
    }
    @Test public void timeoutCannotCommitBetweenStatusCheckAndDiscard() {
        java.util.concurrent.atomic.AtomicReference<Runnable> queued=new java.util.concurrent.atomic.AtomicReference<>();
        java.util.concurrent.atomic.AtomicBoolean applied=new java.util.concurrent.atomic.AtomicBoolean();
        java.util.concurrent.atomic.AtomicInteger discarded=new java.util.concurrent.atomic.AtomicInteger();
        boolean result=OfficialCollection.commitOnGlThread(1,queued::set,()->{applied.set(true);return true;},
                request->{int before=applied.get()?2:1;queued.get().run();return before;},discarded::incrementAndGet,1);
        assertEquals("failure cannot be reported after the generation was committed",applied.get(),result);
        assertFalse("a timed-out queued commit must never run",applied.get());
        assertEquals(1,discarded.get());queued.get().run();assertFalse(applied.get());
    }
    @Test public void startedCommitFinishesBeforeTimeoutReportsFailure()throws Exception {
        java.util.concurrent.CountDownLatch started=new java.util.concurrent.CountDownLatch(1),release=new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.atomic.AtomicBoolean applied=new java.util.concurrent.atomic.AtomicBoolean();
        java.util.concurrent.atomic.AtomicInteger discarded=new java.util.concurrent.atomic.AtomicInteger();
        java.util.concurrent.ExecutorService installer=java.util.concurrent.Executors.newSingleThreadExecutor();
        try {
            java.util.concurrent.Future<Boolean> result=installer.submit(()->OfficialCollection.commitOnGlThread(1,
                    task->{Thread gl=new Thread(task);gl.setDaemon(true);gl.start();
                        try{if(!started.await(3,java.util.concurrent.TimeUnit.SECONDS))throw new AssertionError("GL commit did not start");}
                        catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new RuntimeException(interrupted);}},
                    ()->{started.countDown();release.await();applied.set(true);return true;},
                    request->applied.get()?2:1,discarded::incrementAndGet,20));
            assertTrue(started.await(3,java.util.concurrent.TimeUnit.SECONDS));
            Thread.sleep(100);
            assertFalse("a running native commit must settle before rollback is allowed",result.isDone());
            release.countDown();assertTrue(result.get(3,java.util.concurrent.TimeUnit.SECONDS));assertEquals(0,discarded.get());
        }finally{release.countDown();installer.shutdownNow();}
    }
}
