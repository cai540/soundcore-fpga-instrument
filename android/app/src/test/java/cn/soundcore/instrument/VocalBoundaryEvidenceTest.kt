package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class VocalBoundaryEvidenceTest {
    private fun modulated()=FloatArray(40000){i->
        ((.18+.08*cos(2*PI*4.5*i/16000))*sin(2*PI*392*i/16000)).toFloat()
    }
    @Test fun overallGainDoesNotBecomePhoneticChange() {
        val x=modulated();val a=VocalBoundaryEvidence.analyze(x).novelty
        val b=VocalBoundaryEvidence.analyze(FloatArray(x.size){x[it]*.25f}).novelty
        assertTrue(a.indices.maxOf{abs(a[it]-b[it])}<.002)
    }
    @Test fun pureAmplitudeTremoloDoesNotSuggestRepeatedVowels() {
        val a=VocalBoundaryEvidence.analyze(modulated()).novelty
        assertTrue(a.sliceArray(40..210).max()<.04)
    }
    @Test fun vowelColourCanChangeWithoutAnEnergyValley() {
        val old=doubleArrayOf(1.0,.2,.1,.05);val next=doubleArrayOf(.15,.6,1.0,.35)
        val normA=sqrt(old.sumOf{it*it});val normB=sqrt(next.sumOf{it*it})
        val pcm=FloatArray(32000){i->
            val a=if(i<16000)old else next;val n=if(i<16000)normA else normB
            (.22*a.indices.sumOf{h->a[h]*sin((h+1)*2*PI*220*i/16000+h*.1)}/n).toFloat()
        }
        val e=VocalBoundaryEvidence.analyze(pcm)
        assertTrue(e.candidates.any{it in 90..110})
        assertTrue(e.novelty.sliceArray(90..110).max()>.04)
    }
    @Test fun longTrueSilenceHasNoBoundaryStrengthInside() {
        val pcm=FloatArray(32000){i->if(i in 8000..23999)0f else (.22*sin(2*PI*392*i/16000)).toFloat()}
        val e=VocalBoundaryEvidence.analyze(pcm)
        assertTrue(e.strength.sliceArray(75..125).all{it==0.0})
    }
    @Test fun workerCanBeCancelled() {
        var calls=0
        try {VocalBoundaryEvidence.analyze(modulated(),null,{++calls>2});fail("ignored cancellation")}
        catch(_:InterruptedException){assertTrue(calls<=3)}
    }
}
