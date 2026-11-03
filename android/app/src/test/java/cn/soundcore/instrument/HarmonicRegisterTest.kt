package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class HarmonicRegisterTest {
    private fun signal(ms:Int,midi:(Int)->Double,amps:DoubleArray):FloatArray {
        var phase=0.0
        return FloatArray(ms*16){i->
            phase+=2*PI*440*2.0.pow((midi(i/16)-69)/12)/16000
            (amps.indices.sumOf{h->amps[h]*sin((h+1)*phase+h*.21)}*.1).toFloat()
        }
    }
    private fun checkRegister(actual:Int,detected:Int,amps:DoubleArray) {
        val pcm=signal(1400,{actual.toDouble()},amps)
        val track=StablePitchTracker.Track(DoubleArray(141){detected.toDouble()},DoubleArray(141){.9},DoubleArray(141){.2})
        val result=HarmonicRegisterRefinement.refine(pcm,track)
        assertTrue(result.pitch.sliceArray(20..119).all{abs(it-actual)<.1})
    }
    @Test fun realLowPureToneStaysLow()=checkRegister(47,47,doubleArrayOf(1.0))
    @Test fun realLowRichToneStaysLow()=checkRegister(47,47,doubleArrayOf(1.0,.5,.33,.25,.2,.167))
    @Test fun oddPartialsProtectAWeakFundamental()=checkRegister(47,47,doubleArrayOf(.02,.8,.7,.5,.4,.3))
    @Test fun falseHalfFrequencyIsCorrectedFromPcmEvidence()=checkRegister(71,59,doubleArrayOf(.3,1.0,.7,.5,.3,.2))
    @Test fun falseThirdFrequencyIsCorrectedFromPcmEvidence()=checkRegister(64,45,doubleArrayOf(.4,1.0,.7,.5,.3,.2))
    @Test fun realUpperRegisterRemains()=checkRegister(72,72,doubleArrayOf(1.0,.5,.33,.25,.2,.167))
    @Test fun realLowerRegisterRemains()=checkRegister(60,60,doubleArrayOf(1.0,.5,.33,.25,.2,.167))
    @Test fun genuineOctaveLeapIsNotSmoothedAway() {
        val pcm=signal(1800,{if(it<900)72.0 else 60.0},doubleArrayOf(1.0,.5,.33,.25,.2,.167))
        val track=StablePitchTracker.Track(DoubleArray(181){if(it<90)72.0 else 60.0},DoubleArray(181){.9},DoubleArray(181){.2})
        val out=HarmonicRegisterRefinement.refine(pcm,track)
        assertTrue(out.pitch.sliceArray(20..69).all{abs(it-72)<.1})
        assertTrue(out.pitch.sliceArray(110..159).all{abs(it-60)<.1})
    }
    @Test fun registerWorkerCanBeCancelled() {
        val pcm=signal(1400,{60.0},doubleArrayOf(1.0))
        val track=StablePitchTracker.Track(DoubleArray(141){60.0},DoubleArray(141){.9},DoubleArray(141){.2})
        try { HarmonicRegisterRefinement.refine(pcm,track,{true});fail("ignored cancellation") }
        catch(_:InterruptedException) { }
    }
}
