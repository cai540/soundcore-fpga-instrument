package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class VocalSyllableSegmentationTest {
    private fun track(ms:Int,pitch:(Int)->Double,energy:(Int)->Double={.25},prob:(Int)->Double={.9}) =
        StablePitchTracker.Track(DoubleArray(ms/10){pitch(it*10)},DoubleArray(ms/10){prob(it*10)},DoubleArray(ms/10){energy(it*10)})
    private fun notes(t:StablePitchTracker.Track)=VocalNoteSegmentation.segment(t,t.pitch.size*10,MelodyInput.VOCAL).notes
    @Test fun broadVocalVibratoDoesNotBecomeAlternatingSemitones() {
        val n=notes(track(1800,{60+1.1*sin(2*PI*3*it/1000)}))
        assertEquals(listOf(60),n.map{it.midi})
        assertTrue(n[0].durationMs>=1700)
    }
    @Test fun amplitudeTremoloDoesNotCreateRepeatedSyllables() {
        val n=notes(track(1800,{64.0},{.2+.1*cos(2*PI*5*it/1000)}))
        assertEquals(listOf(64),n.map{it.midi})
    }
    @Test fun actualHundredMillisecondBreathStaysSilent() {
        val n=notes(track(1400,{if(it in 600..690)Double.NaN else 64.0},{if(it in 600..690)0.0 else .25}))
        assertEquals(listOf(64,64),n.map{it.midi})
        assertTrue(n[1].startMs-n[0].startMs-n[0].durationMs>=90)
    }
    @Test fun clearRapidMainNotesRemainDistinct() {
        val n=notes(track(600,{when{it<150->60.0;it<300->62.0;it<450->64.0;else->65.0}}))
        assertEquals(listOf(60,62,64,65),n.map{it.midi})
    }
    @Test fun realOctaveLeapIsNotFoldedBack() {
        val n=notes(track(1400,{if(it in 500..849)60.0 else 72.0}))
        assertEquals(listOf(72,60,72),n.map{it.midi})
    }
    @Test fun periodicButFlatFastNotesAreNotMistakenForVibrato() {
        val n=notes(track(1200,{if(it/150%2==0)60.0 else 64.0}))
        assertEquals(List(8){if(it%2==0)60 else 64},n.map{it.midi})
    }
    @Test fun mainNoteWorkerCanBeCancelled() {
        var calls=0
        try {
            VocalMainNoteSegmentation.segment(track(3000,{64.0}),3000,{++calls>2})
            fail("segmentation ignored cancellation")
        } catch(_:InterruptedException) { assertTrue(calls<=4) }
    }
    @Test fun lowConfidenceShortOctaveGlitchBetweenSamePlateauIsSuppressed() {
        val n=notes(track(1600,{if(it in 600..839)60.0 else 72.0},prob={if(it in 600..839).1 else .9}))
        assertEquals(listOf(72),n.map{it.midi})
    }
    @Test fun narrowConsonantDipRetainsSamePitchReattack() {
        val n=notes(track(1200,{67.0},{if(it in 540..599).05 else .25}))
        assertEquals(listOf(67,67),n.map{it.midi})
        assertTrue(n[1].startMs in 500..650)
    }
    @Test fun broadConsonantWithoutFastPeriodicityRetainsRepeatedSyllable() {
        val n=notes(track(1500,{67.0},{if(it in 550..699).05 else .25}))
        assertEquals(listOf(67,67),n.map{it.midi})
        assertTrue(n[1].startMs in 500..750)
    }
    @Test fun LateVolumeNotchDoesNotCreateATinyPhantomTailNote() {
        val n=notes(track(700,{67.0},{if(it in 550..599).05 else .25}))
        assertEquals(listOf(67),n.map{it.midi})
    }
    @Test fun clearLongConsonantDipIsNotLostToAWidthCutoff() {
        val n=notes(track(1700,{67.0},{if(it in 600..979).04 else .25}))
        assertEquals(listOf(67,67),n.map{it.midi})
    }
}
