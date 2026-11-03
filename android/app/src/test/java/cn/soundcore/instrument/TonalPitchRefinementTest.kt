package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class TonalPitchRefinementTest {
    private fun context(last:Int,lastMs:Int=800,transpose:Int=0,contour:(Int)->Double={last.toDouble()}):Pair<List<MelodyNote>,StablePitchTracker.Track> {
        val notes=mutableListOf<MelodyNote>();val pitch=mutableListOf<Double>();var start=0
        for((n,ms) in listOf(65 to 3000,69 to 3000,72 to 3000,74 to 3000,67 to 1500,70 to 400,76 to 1100)) {
            notes+=MelodyNote(start,ms,n+transpose,.95f);repeat(ms/10){pitch+=(n+transpose).toDouble()};start+=ms
        }
        notes+=MelodyNote(start,lastMs,last+transpose,.2f)
        repeat(lastMs/10){pitch+=contour(it*10)+transpose}
        return notes to StablePitchTracker.Track(pitch.toDoubleArray(),DoubleArray(pitch.size){.9},DoubleArray(pitch.size){.2})
    }
    @Test fun insufficientPitchClassesDoNotForceAKey() {
        val n=(0..11).map{MelodyNote(it*500,500,60+it%4,.9f)}
        assertNull(TonalPitchRefinement.infer(n))
    }
    @Test fun shortPhraseDoesNotForceAKey() {
        assertNull(TonalPitchRefinement.infer((0..6).map{MelodyNote(it*300,300,60+it,.9f)}))
    }
    @Test fun clearlyCentredChromaticNoteIsRetained() {
        val(n,t)=context(75,1000,contour={75+.4*sin(2*PI*5*it/1000)})
        assertEquals(75,TonalPitchRefinement.apply(n,t).last().midi)
    }
    @Test fun flatButClearLowChromaticIntonationIsRetained() {
        val(n,t)=context(75,600,contour={74.68})
        assertEquals(75,TonalPitchRefinement.apply(n,t).last().midi)
    }
    @Test fun sharpButClearChromaticIntonationIsRetained() {
        val(n,t)=context(75,600,contour={75.32})
        assertEquals(75,TonalPitchRefinement.apply(n,t).last().midi)
    }
    @Test fun periodicWideLowChromaticVibratoIsRetained() {
        val(n,t)=context(75,1200,contour={74.68+.9*sin(2*PI*5*it/1000)})
        assertEquals(75,TonalPitchRefinement.apply(n,t).last().midi)
    }
    @Test fun periodicWideHighChromaticVibratoIsRetained() {
        val(n,t)=context(75,1200,contour={75.32+.9*sin(2*PI*5*it/1000)})
        assertEquals(75,TonalPitchRefinement.apply(n,t).last().midi)
    }
    @Test fun slowWideLowChromaticVibratoIsRetained() {
        val(n,t)=context(75,1400,contour={74.68+.9*sin(2*PI*2*it/1000)})
        assertEquals(75,TonalPitchRefinement.apply(n,t).last().midi)
    }
    @Test fun slowWideHighChromaticVibratoIsRetained() {
        val(n,t)=context(75,1400,contour={75.32+.9*sin(2*PI*2*it/1000)})
        assertEquals(75,TonalPitchRefinement.apply(n,t).last().midi)
    }
    @Test fun missingVibratoPhaseDoesNotCompressTheTimeline() {
        for(range in listOf(450 until 750,350 until 650)) {
            val(n,t)=context(75,1200,contour={if(it in range)Double.NaN else 75.32+.9*sin(2*PI*5*it/1000)})
            assertEquals("missing $range",75,TonalPitchRefinement.apply(n,t).last().midi)
        }
    }
    @Test fun sparseMissingFramesKeepOriginalVibratoPhase() {
        for(center in listOf(74.68,75.32)) {
            val(n,t)=context(75,1200,contour={if((it/10)%8==0)Double.NaN else center+.9*sin(2*PI*5*it/1000)})
            assertEquals("center $center",75,TonalPitchRefinement.apply(n,t).last().midi)
        }
    }
    @Test fun phaseBiasedMissingFramesDoNotChangeTheFittedPitchCentre() {
        val(n,t)=context(75,1200,contour={if((it/10)%20 in 2..4)Double.NaN else 75.32+.9*sin(2*PI*5*it/1000)})
        assertEquals(75,TonalPitchRefinement.apply(n,t).last().midi)
    }
    @Test fun missingSamplesDoNotJoinTwoShortStableCores() {
        val p=DoubleArray(25){if(it in 10..14)Double.NaN else 75.32}
        assertTrue(TonalPitchRefinement.core(p,75).first<140)
    }
    @Test fun whollyMissingContourIsRetained() {
        val(n,t)=context(75,1200,contour={Double.NaN})
        assertEquals(75,TonalPitchRefinement.apply(n,t).last().midi)
    }
    @Test fun realSilenceInsideAnAmbiguousEventPreventsRetuning() {
        val(n,t)=context(75,510,contour={74.57+.9*sin(2*PI*5*it/1000)+.35*sin(2*PI*1.7*it/1000)})
        val rms=t.rms.copyOf();rms[(n.last().startMs+200)/10]=0.0
        assertEquals(75,TonalPitchRefinement.apply(n,t.copy(rms=rms)).last().midi)
    }
    @Test fun missingAmplitudeInsideAnAmbiguousEventPreventsRetuning() {
        val(n,t)=context(75,510,contour={74.57+.9*sin(2*PI*5*it/1000)+.35*sin(2*PI*1.7*it/1000)})
        val rms=t.rms.copyOf();rms[(n.last().startMs+200)/10]=Double.NaN
        assertEquals(75,TonalPitchRefinement.apply(n,t.copy(rms=rms)).last().midi)
    }
    @Test fun realFastChromaticNoteIsRetained() {
        val(n,t)=context(75,150,contour={75.12})
        assertEquals(75,TonalPitchRefinement.apply(n,t).last().midi)
    }
    @Test fun ambiguousRareDegreeCanUseRecordingInferredPrior() {
        val(n,t)=context(75,510,contour={74.57+.9*sin(2*PI*5*it/1000)+.35*sin(2*PI*1.7*it/1000)})
        assertNotNull(TonalPitchRefinement.infer(n))
        assertEquals(74,TonalPitchRefinement.apply(n,t).last().midi)
    }
    @Test fun algorithmIsTranspositionEquivariant() {
        val a=context(75,510,contour={74.57+.9*sin(2*PI*5*it/1000)+.35*sin(2*PI*1.7*it/1000)})
        val b=context(75,510,transpose=2,contour={74.57+.9*sin(2*PI*5*it/1000)+.35*sin(2*PI*1.7*it/1000)})
        val x=TonalPitchRefinement.apply(a.first,a.second);val y=TonalPitchRefinement.apply(b.first,b.second)
        assertEquals(x.map{it.midi+2},y.map{it.midi})
    }
    @Test fun eventCountAndTimeRemainExactlyTheSame() {
        val(n,t)=context(75,510,contour={74.57+.9*sin(2*PI*5*it/1000)+.35*sin(2*PI*1.7*it/1000)})
        val result=TonalPitchRefinement.apply(n,t)
        assertEquals(n.size,result.size)
        assertEquals(n.map{it.startMs to it.durationMs},result.map{it.startMs to it.durationMs})
    }
    @Test fun cancellationIsRespectedBeforeKeyInference() {
        val(n,t)=context(75)
        try {TonalPitchRefinement.apply(n,t,{true});fail("ignored cancellation")}
        catch(_:InterruptedException) { }
    }
    @Test fun independentStrongRecoveredChildCanBeProtected() {
        val(n,t)=context(75,510,contour={74.57+.9*sin(2*PI*5*it/1000)+.35*sin(2*PI*1.7*it/1000)})
        val mask=BooleanArray(n.size);mask[mask.lastIndex]=true
        assertEquals(75,TonalPitchRefinement.apply(n,t,mask,{false}).last().midi)
    }
    @Test(expected=IllegalArgumentException::class) fun protectionMaskMustMatchTheActualEventList() {
        val(n,t)=context(75)
        TonalPitchRefinement.apply(n,t,BooleanArray(1),{false})
    }
}
