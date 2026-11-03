package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class VocalOnsetEvidenceTest {
    @Test fun steadyToneAmplitudeTremoloHasLittleEnvelopeNovelty() {
        val pcm=FloatArray(40000){i->((.18+.09*cos(2*PI*5*i/16000))*sin(2*PI*392*i/16000)).toFloat()}
        val onset=VocalOnsetEvidence.onsetEvidence(pcm)
        assertTrue(onset.sliceArray(30 until 220).max()<.30)
    }
    @Test fun consonantLikeBroadbandBurstHasNoveltyEvenWhenQuiet() {
        val random=java.util.Random(13)
        val pcm=FloatArray(32000){i->
            if(i in 15000..16599)(random.nextGaussian()*.025).toFloat()
            else (.25*sin(2*PI*392*i/16000)).toFloat()
        }
        val onset=VocalOnsetEvidence.onsetEvidence(pcm)
        assertTrue(onset.sliceArray(90..110).max()>.30)
    }
    @Test fun spectralWorkerSupportsCancellation() {
        var calls=0
        try {
            VocalOnsetEvidence.onsetEvidence(FloatArray(40000),{++calls>2})
            fail("spectral worker ignored cancellation")
        } catch(_:InterruptedException) { assertTrue(calls<=3) }
    }
}
