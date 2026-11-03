package cn.soundcore.instrument
import kotlin.math.*
import org.junit.Test
import org.junit.Assert.*

class VocalContourProjectionTest {
    private data class Example(val notes:List<MelodyNote>,val track:StablePitchTracker.Track,
        val onset:DoubleArray,val novelty:DoubleArray)
    private fun project(e:Example)=VocalContourProjection.apply(e.notes,e.track,e.onset,e.novelty)
    private fun context():List<MelodyNote> = listOf(60,62,64,65,67,69,70,72).mapIndexed { i,n->
        MelodyNote(i*800,650,n,.9f) }
    private fun example(tail:List<MelodyNote>,pitch:(Int)->Double):Example {
        val notes=context()+tail
        val size=(notes.last().startMs+notes.last().durationMs)/10+1
        val p=DoubleArray(size){Double.NaN}
        for(n in notes)for(i in n.startMs/10 until (n.startMs+n.durationMs)/10)p[i]=n.midi.toDouble()
        for(i in 640 until size)p[i]=pitch(i-640)
        return Example(notes,StablePitchTracker.Track(p,DoubleArray(size){.9},DoubleArray(size){.2}),
            DoubleArray(size),DoubleArray(size))
    }
    private fun descending(shape:(Int)->Double={76.6+.9*sin(it*.77)+.4*sin(it*.31)}):Example {
        val e=example(listOf(MelodyNote(6400,400,77,.7f),MelodyNote(6800,500,77,.5f),MelodyNote(7300,600,74,.9f))) {
            when {it<40->77.0;it<90->shape(it-40);else->74.0} }
        e.onset[680]=.4;return e
    }
    private fun scoop():Example=example(listOf(MelodyNote(6400,300,62,.8f),MelodyNote(6700,600,64,.8f))) {
        if(it<30)60+it*.1 else 64.0 }
    private fun arch():Example {
        val e=example(listOf(MelodyNote(6400,400,65,.7f),MelodyNote(6800,1000,65,.9f))) {
            when {it<18->63.4+it*.18;it<25->66.6;it<40->66.6-(it-25)*.13;else->65.0} }
        e.onset[680]=.5;return e
    }
    @Test fun ambiguousIrregularFallingRepeatUsesInferredIntermediateScaleStep() {
        val e=descending();assertEquals(76,project(e)[e.notes.lastIndex-1].midi)
    }
    @Test fun accuratelyCentredWideRepeatedVibratoIsProtected() {
        val e=descending{77+1.1*sin(2*PI*5*it*.01)};assertEquals(e.notes,project(e))
    }
    @Test fun regularSlightlyDetunedRepeatedVibratoIsProtected() {
        val e=descending{76.65+.9*sin(2*PI*6*it*.01)};assertEquals(e.notes,project(e))
    }
    @Test fun stableDetunedRepeatedPlateauIsProtected() {
        val e=descending{76.65};assertEquals(e.notes,project(e))
    }
    @Test fun real140msCoreWinsOverFallingContext() {
        val e=descending{if(it in 8..21)77.0 else 76.25+sin(it*.77)*.7};assertEquals(e.notes,project(e))
    }
    @Test fun missingEvidenceDoesNotInventIntermediateNote() {
        val e=descending{if(it%2==0)Double.NaN else 76.3};assertEquals(e.notes,project(e))
    }
    @Test fun independentArticulationIsRequiredForFallingRepeat() {
        val e=descending();e.onset.fill(0.0);assertEquals(e.notes,project(e))
    }
    @Test fun monotonicUnarticulatedAttackDoesNotBecomeExtraLowNote() {
        val e=scoop();val out=project(e);assertEquals(e.notes.size-1,out.size)
        assertEquals(MelodyNote(6400,900,64,.8f),out.last())
    }
    @Test fun actualRestBeforeHighNoteIsNeverFilled() {
        val e=scoop();val ns=e.notes.toMutableList();ns[ns.lastIndex]=ns.last().copy(startMs=6710,durationMs=590)
        val a=e.copy(notes=ns);assertEquals(a.notes,project(a))
    }
    @Test fun independentConsonantProtectsTwoLegatoNotes() {
        val e=scoop();e.novelty[670]=.12;assertEquals(e.notes,project(e))
    }
    @Test fun independentAttackProtectsTwoLegatoNotes() {
        val e=scoop();e.onset[670]=.5;assertEquals(e.notes,project(e))
    }
    @Test fun genuineStableShortNoteIsNeverSwallowed() {
        val e=scoop();for(i in 650..665)e.track.pitch[i]=62.0
        assertEquals(e.notes,project(e))
    }
    @Test fun articulatedShortArchUsesObservedUpperTurn() {
        val e=arch();assertEquals(67,project(e)[e.notes.lastIndex-1].midi)
    }
    @Test fun stableArchCentreProtectsAnIntentionalOvershoot() {
        val e=arch();for(i in 640..654)e.track.pitch[i]=65.0
        assertEquals(e.notes,project(e))
    }
    @Test fun noIndependentNextOnsetMeansNoArchProjection() {
        val e=arch();e.onset.fill(0.0);assertEquals(e.notes,project(e))
    }
    @Test fun cancelledProjectionStopsWithoutMutatingInput() {
        val e=arch();try {VocalContourProjection.apply(e.notes,e.track,e.onset,e.novelty){true};fail()} catch(_:InterruptedException){}
    }
    @Test fun contourDecisionsAreEquivariantAcrossEveryChromaticTransposition() {
        for(e in listOf(descending(),arch(),scoop()))for(shift in -6..6) {
            val moved=e.copy(notes=e.notes.map{it.copy(midi=it.midi+shift)},
                track=e.track.copy(pitch=DoubleArray(e.track.pitch.size){e.track.pitch[it]+shift}))
            assertEquals("shift=$shift",project(e).map{it.copy(midi=it.midi+shift)},project(moved))
        }
    }
    @Test fun movingIdenticalPcmEvidenceOnTheClockDoesNotChangeDecision() {
        for(e in listOf(descending(),arch(),scoop())) {
            val pad=83
            fun move(x:DoubleArray,missing:Double)=DoubleArray(x.size+pad){if(it<pad)missing else x[it-pad]}
            val moved=e.copy(notes=e.notes.map{it.copy(startMs=it.startMs+pad*10)},
                track=StablePitchTracker.Track(move(e.track.pitch,Double.NaN),move(e.track.probability,0.0),move(e.track.rms,0.0)),
                onset=move(e.onset,0.0),novelty=move(e.novelty,0.0))
            assertEquals(project(e).map{it.copy(startMs=it.startMs+pad*10)},project(moved))
        }
    }
}
