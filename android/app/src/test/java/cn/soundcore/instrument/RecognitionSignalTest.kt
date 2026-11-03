package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class RecognitionSignalTest {
    private fun sine(gain:Double,offset:Double=0.0)=FloatArray(16000){(gain*sin(2*PI*440*it/16000)+offset).toFloat()}
    @Test fun ordinaryRecordingIsNotAltered(){val a=sine(.2);assertSame(a,RecognitionSignal.prepare(a))}
    @Test fun quietAndDcBiasedInputRetainsPitchAndZeroCrossingPattern(){
        val a=sine(.001,.12);val b=RecognitionSignal.prepare(a)
        assertTrue(abs(b.average())<1e-5);assertTrue(b.max()>.03f)
        for(i in 1 until a.size)assertEquals(a[i]>a[i-1],b[i]>b[i-1])
    }
    @Test fun inputIsNeverMutated(){val a=sine(.001,.1);val copy=a.copyOf();RecognitionSignal.prepare(a);assertArrayEquals(copy,a,0f)}
    @Test fun gainIsBoundedAndSilenceIsNotTurnedIntoMusic(){
        val a=sine(.00001);val b=RecognitionSignal.prepare(a);assertTrue(b.max()<=a.max()*32.01)
        try{RecognitionSignal.prepare(FloatArray(16000){.2f});fail("constant DC accepted")}catch(_:IllegalArgumentException){}
    }
    @Test fun cancellationAndInvalidSamplesFailPromptly(){
        try{RecognitionSignal.prepare(sine(.2),{true});fail("cancel ignored")}catch(_:InterruptedException){}
        try{RecognitionSignal.prepare(sine(.2).also{it[100]=Float.NaN});fail("NaN accepted")}catch(_:IllegalArgumentException){}
    }
}
