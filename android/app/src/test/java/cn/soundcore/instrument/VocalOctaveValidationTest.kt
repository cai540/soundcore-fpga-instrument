package cn.soundcore.instrument
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class VocalOctaveValidationTest {
    private val f=440*2.0.pow((60-69)/12.0)
    private val seeds=listOf(MelodyNote(200,600,60,.9f),MelodyNote(800,400,60,.8f))
    private fun fixture(high:Boolean=false,lowAmplitude:Double=.2,vibrato:Double=0.0):FloatArray {
        var phase=0.0
        return FloatArray(24000){i->val t=i/16000.0;phase+=2*PI*f*2.0.pow(vibrato*sin(2*PI*5*t)/12)/16000
            val before=(1..7).sumOf{h->sin(h*phase)/h}
            val upper=sin(2*phase)+.6*sin(4*phase)+.3*sin(6*phase)+.2*sin(8*phase)
            val bass=if(high)lowAmplitude*sin(2*PI*f*.991*t+.7) else lowAmplitude*sin(phase)
            ((if(t<.8)before else upper+bass)*.18).toFloat()}
    }
    @Test fun genuineLowFundamentalSurvivesAChangeToEvenDominantTimbre() {
        for(a in listOf(.2,.3,.5))assertEquals(seeds,VocalOctaveValidation.refine(fixture(lowAmplitude=a),seeds))
    }
    @Test fun harmonicLockProtectsWideCommonVibrato() {
        for(a in listOf(.2,.7,1.2)) {
            val x=fixture(vibrato=a);val lock=VocalOctaveValidation.phaseLock(x,seeds[1])!!
            assertTrue("vibrato=$a coherence=${lock.coherence}",lock.coherence>.98)
            assertEquals(seeds,VocalOctaveValidation.refine(x,seeds))
        }
    }
    @Test fun residualIndependentLowToneDoesNotTrapTheDominantOctave() {
        val x=fixture(high=true,lowAmplitude=.12)
        assertTrue(VocalOctaveValidation.phaseLock(x,seeds[1])!!.coherence<.5)
        val out=VocalOctaveValidation.refine(x,seeds)
        assertEquals(listOf(60,72),out.map{it.midi});assertEquals(seeds.map{it.startMs to it.durationMs},out.map{it.startMs to it.durationMs})
    }
    @Test fun missingFundamentalWithOddHigherPartialsRetainsTheLowerPitch() {
        val x=FloatArray(24000){i->val p=2*PI*f*i/16000;((sin(2*p)+.7*sin(3*p)+.4*sin(5*p)+.2*sin(7*p))*.2).toFloat()}
        assertEquals(seeds,VocalOctaveValidation.refine(x,seeds))
    }
    @Test fun weakOddFamilyStillProtectsItsMissingFundamental() {
        for(odd in listOf(3,5,7)) {
            val x=FloatArray(24000){i->val p=2*PI*f*i/16000
                val before=(1..7).sumOf{h->sin(h*p)/h}
                val after=sin(2*p)+.6*sin(4*p)+.3*sin(6*p)+.2*sin(8*p)+.10*sin(odd*p)
                ((if(i<12800)before else after)*.18).toFloat()}
            val lock=VocalOctaveValidation.phaseLock(x,seeds[1])!!
            assertTrue("odd=$odd lock=${lock.coherence}",lock.coherence>.98)
            assertEquals(seeds,VocalOctaveValidation.refine(x,seeds))
        }
    }
    @Test fun noArticulationIsInventedToExplainAnOctave() {
        val x=fixture(high=true,lowAmplitude=.12);val single=listOf(MelodyNote(200,1000,60,.8f))
        assertEquals(single,VocalOctaveValidation.refine(x,single))
    }
    @Test fun clipEdgesWithoutPhaseContextArePreserved() {
        assertNull(VocalOctaveValidation.phaseLock(fixture(),MelodyNote(50,400,60,.8f)))
    }
    @Test fun cancellationIsHonoured() {
        try {VocalOctaveValidation.refine(fixture(),seeds,{true});fail("ignored cancellation")}
        catch(_:InterruptedException) { }
    }
}
