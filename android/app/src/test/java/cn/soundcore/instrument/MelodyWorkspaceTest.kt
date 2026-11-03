package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test

class MelodyWorkspaceTest {
    private fun n(s: Int, d: Int, p: Int = 60) = MelodyNote(s, d, p, .9f)
    @Test fun sourceCoordinatesSurviveTrimAndPreview() {
        val local = MelodyScore(listOf(n(100, 300), n(600, 200, 64)), 1000)
        val score = MelodyWorkspace.absolute(local, 25000, 90000)
        assertEquals(25100, score.firstMs)
        assertEquals(16000, MelodyWorkspace.preview(score, 0, MelodyRange(25000, 26000)).size)
        val wave = MelodyWorkspace.preview(score, 0, MelodyRange(25000, 26000))
        assertTrue(wave.take(1600).all { it == 0.toShort() })
        assertTrue(wave.drop(12800).all { it == 0.toShort() })
    }
    @Test fun cropUsesExactSourceSamples() {
        val pcm = FloatArray(32000) { it.toFloat() }
        val cut = MelodyRange(500, 1500).samples(pcm, 16000)
        assertEquals(16000, cut.size); assertEquals(8000f, cut.first()); assertEquals(23999f, cut.last())
    }
    @Test fun localReplacementPreservesBothCrossBoundaryTailsAndRest() {
        val score = MelodyScore(listOf(n(100, 1200), n(1500, 500, 64)), 2500)
        val local = MelodyScore(listOf(n(100, 200, 67)), 500)
        val next = MelodyWorkspace.replace(score, MelodyRange(500, 1000), local)
        assertEquals(listOf(n(100,400), n(600,200,67), n(1000,300), n(1500,500,64)), next.notes)
        assertEquals(score.notes.last(), next.notes.last())
    }
    @Test fun editRejectsOverlapAndOutOfBoundsWithoutMutatingOriginal() {
        val s = MelodyScore(listOf(n(0,300), n(400,200,62)), 1000)
        assertTrue(runCatching { MelodyWorkspace.edit(s,0,durationDelta=150) }.isFailure)
        assertEquals(300,s.notes[0].durationMs)
        assertEquals(250,MelodyWorkspace.edit(s,0,durationDelta=-50).notes[0].durationMs)
        assertTrue(runCatching { MelodyWorkspace.edit(s,0,onsetDelta=-50) }.isFailure)
    }
    @Test fun repeatedNoteCanBeSplitAndUndoneByImmutableRevision() {
        val s = MelodyScore(listOf(n(0,800)),1000)
        val split = MelodyWorkspace.split(s,0,400)
        assertEquals(2,split.notes.size); assertEquals(1,s.notes.size)
        assertEquals(s,MelodyWorkspace.merge(split,0))
    }
    @Test fun localReplacementRejectsMoreThanDeviceDuration() {
        val s = MelodyScore(listOf(n(0,100),n(179900,100,64)),190000)
        assertTrue(runCatching { MelodyWorkspace.replace(s,MelodyRange(180000,181000),
            MelodyScore(listOf(n(500,200,67)),1000)) }.isFailure)
    }
    @Test fun nearestNoteWorksInsideSilenceAndMidiNamesUseChromaticPitch() {
        val s = MelodyScore(listOf(n(0,100),n(600,100,61)),1000)
        assertEquals(1,MelodyWorkspace.nearest(s,580))
        assertEquals("C♯4",MelodyWorkspace.noteName(61))
    }
    @Test fun deleteSpuriousNotePreservesRestAndCannotDeleteOnlyRemainingNote() {
        val s=MelodyScore(listOf(n(0,100,59),n(100,300),n(600,100,64)),1000)
        val next=MelodyWorkspace.delete(s,0)
        assertEquals(100,next.firstMs);assertEquals(3,s.notes.size)
        assertTrue(runCatching{MelodyWorkspace.delete(MelodyScore(listOf(n(0,100)),1000),0)}.isFailure)
    }
    @Test fun cropEdgesDoNotTurnSustainedNoteIntoThreeAttacks() {
        val s=MelodyScore(listOf(n(100,1200)),1500)
        val same=MelodyWorkspace.replace(s,MelodyRange(500,1000),MelodyScore(listOf(n(0,500)),500))
        assertEquals(s.notes,same.notes)
        val repeated=MelodyWorkspace.replace(s,MelodyRange(500,1000),MelodyScore(listOf(n(0,250),n(250,250)),500))
        assertEquals(2,repeated.notes.size)
        assertEquals(750,repeated.notes[1].startMs)
    }
}
