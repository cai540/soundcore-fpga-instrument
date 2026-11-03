package cn.soundcore.instrument
import kotlin.math.*
import org.junit.Test
import org.junit.Assert.*

class ReleaseContourProjectionTest {
    private fun example(pitch:(Int)->Double={61.45+.55*sin(2*PI*5*it*.01)}):Triple<List<MelodyNote>,StablePitchTracker.Track,DoubleArray> {
        val n=listOf(MelodyNote(0,600,60,.8f),MelodyNote(600,350,62,.2f))
        val p=DoubleArray(95){if(it<60)60.0 else pitch(it-60)}
        val rms=DoubleArray(95){if(it<60).2 else .1*exp(-4*(it-60)*.01)}
        return Triple(n,StablePitchTracker.Track(p,DoubleArray(95){.2},rms),DoubleArray(95){.1})
    }
    @Test fun uncertainDecayMayBeProjectedToExistingMainNote() {
        val(n,t,o)=example();val out=ReleaseContourProjection.apply(n,t,o)
        assertEquals(listOf(MelodyNote(0,950,60,.8f)),out)
    }
    @Test fun quietButStableRealEndingNoteIsRetained() {
        val(n,t,o)=example{62.0};assertEquals(n,ReleaseContourProjection.apply(n,t,o))
    }
    @Test fun genuine140msCoreSurvivesDespiteGlidesAtBothEdges() {
        val(n,t,o)=example{if(it in 8..21)62.0 else 60.9}
        assertEquals(n,ReleaseContourProjection.apply(n,t,o))
    }
    @Test fun genuine150msCoreSurvivesDespiteGlidesAtBothEdges() {
        val(n,t,o)=example{if(it in 8..22)62.0 else 60.9}
        assertEquals(n,ReleaseContourProjection.apply(n,t,o))
    }
    @Test fun quietButCentredWideVibratoEndingNoteIsRetained() {
        val(n,t,o)=example{62+.9*sin(2*PI*5*it*.01)};assertEquals(n,ReleaseContourProjection.apply(n,t,o))
    }
    @Test fun lowButClearlyCentredEndingNoteIsRetained() {
        val(n,t,o)=example{61.7};assertEquals(n,ReleaseContourProjection.apply(n,t,o))
    }
    @Test fun independentAttackProtectsRealFastEndingNote() {
        val(n,t,o)=example();o[60]=.7;assertEquals(n,ReleaseContourProjection.apply(n,t,o))
    }
    @Test fun realSilenceBetweenNotesIsNeverFilled() {
        val(n,t,o)=example();val detached=listOf(n[0].copy(durationMs=590),n[1]);assertEquals(detached,ReleaseContourProjection.apply(detached,t,o))
    }
    @Test fun OngoingMelodyDoesNotLoseAnIntermediateQuickNote() {
        val(n,t,o)=example();val melody=n+MelodyNote(1000,500,64,.8f)
        assertEquals(melody,ReleaseContourProjection.apply(melody,t,o))
    }
    @Test fun strongVoicingEvidencePreservesAmbiguousEndingNote() {
        val(n,t,o)=example();assertEquals(n,ReleaseContourProjection.apply(n,t.copy(probability=DoubleArray(95){.9}),o))
    }
    @Test fun MissingPitchEvidencePreventsProjection() {
        val(n,t,o)=example{Double.NaN};assertEquals(n,ReleaseContourProjection.apply(n,t,o))
    }
    @Test fun cancellationIsRespected() {
        val(n,t,o)=example()
        try {ReleaseContourProjection.apply(n,t,o,{true});fail("ignored cancellation")} catch(_:InterruptedException) { }
    }
}
