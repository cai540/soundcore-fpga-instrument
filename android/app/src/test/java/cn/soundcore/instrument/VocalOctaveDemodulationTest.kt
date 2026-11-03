package cn.soundcore.instrument
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class VocalOctaveDemodulationTest {
    private fun wave(midi:Int,odd:Int=1,depth:Double=1.2,speed:Double=5.0,upperOnly:Boolean=false):FloatArray {
        val rate=16000;val f=440*2.0.pow((midi-69)/12.0);var phase=0.0
        return FloatArray(rate*2){i->
            val t=i/rate.toDouble();phase+=2*PI*f*2.0.pow(depth*sin(2*PI*speed*t)/12)/rate
            val parts=mutableListOf(2 to 1.0,4 to .6,6 to .3,8 to .2)
            if(!upperOnly)parts+=odd to .14
            parts.filter{it.first*f<rate/2*.93}.sumOf{(h,a)->a*sin(h*phase+.17*h)}.toFloat()
        }
    }
    @Test fun all36WideCommonFmMissingFundamentalFamiliesAreProtected() {
        for(midi in listOf(48,60,72,84))for(odd in listOf(3,5,7))for(speed in listOf(3.0,5.0,7.0)) {
            val note=MelodyNote(700,370,midi,.9f)
            val lock=VocalOctaveValidation.phaseLock(wave(midi,odd,speed=speed),note)!!
            assertTrue("midi=$midi odd=$odd speed=$speed coherence=${lock.coherence}",lock.coherence>=.8)
            assertTrue("unsupported odd family",lock.amplitudeRatio>=.02)
        }
    }
    @Test fun all9SharedVibratoFundamentalCasesKeepTheirLowerPeriod() {
        for(depth in listOf(.4,.8,1.2))for(speed in listOf(3.0,5.0,7.0)) {
            val note=MelodyNote(600,600,60,.9f)
            val lock=VocalOctaveValidation.phaseLock(wave(60,1,depth,speed),note)!!
            assertTrue("depth=$depth speed=$speed coherence=${lock.coherence}",lock.coherence>=.8)
        }
    }
    @Test fun unsupportedOddLeakageDoesNotVetoAGenuineUpperOctave() {
        val lock=VocalOctaveValidation.phaseLock(wave(60,upperOnly=true,depth=0.0),MelodyNote(600,600,60,.9f))!!
        assertTrue(lock.coherence<.8 || lock.amplitudeRatio<.02)
    }
    @Test fun nonfinitePcmCannotProduceAPhaseDecision() {
        val pcm=wave(60);pcm[15000]=Float.NaN
        assertNull(VocalOctaveValidation.phaseLock(pcm,MelodyNote(600,600,60,.9f)))
    }
}
