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
}
