package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class MelodyRecognitionTest {
    private fun tone(midi: Int, ms: Int, vibrato: Boolean = false, rich: Boolean = false): FloatArray {
        var phase = 0.0
        return FloatArray(ms * 16) { i ->
            val hz = 440 * 2.0.pow((midi - 69) / 12.0) *
                if (vibrato) 2.0.pow(.18 * sin(i * 2 * PI * 5 / 16000) / 12) else 1.0
            phase += 2 * PI * hz / 16000
            val envelope = min(1.0, min(i / 50.0, (ms * 16 - i - 1) / 70.0))
            ((sin(phase) * .25 + if (rich) .35 * sin(phase * 2) + .1 * sin(phase * 3) else 0.0) * envelope).toFloat()
        }
    }
    @Test fun chromaticAndHarmonicPitch() {
        for (n in listOf(48,60,61,67,72,84,94)) {
            val score = MelodyRecognition.recognize(tone(n, 600, rich = true), 16000)
            assertEquals("pitch $n", listOf(n), score.notes.map { it.midi })
        }
    }
    @Test fun vibratoIsOneLongNote() {
        val score = MelodyRecognition.recognize(tone(72, 2300, vibrato = true), 16000)
        assertEquals(1, score.notes.size); assertTrue(score.notes[0].durationMs > 2150)
    }
    @Test fun restsAndRepeatedNotesSurvive() {
        val pcm = FloatArray(1600) + tone(64, 500) + FloatArray(2880) + tone(64, 450) +
            FloatArray(4000) + tone(67, 700) + FloatArray(1600)
        val score = MelodyRecognition.recognize(pcm, 16000)
        assertEquals(listOf(64,64,67), score.notes.map { it.midi })
        val events = score.events(0)
        assertEquals(2, events.count { it.note == null })
        assertTrue(events.filter { it.note == null }.all { it.durationMs in 130..300 })
    }
    @Test fun silenceAndNoiseRejected() {
        val random = java.util.Random(4)
        for (pcm in listOf(FloatArray(8000), FloatArray(8000) { (random.nextGaussian() * .03).toFloat() })) {
            try { MelodyRecognition.recognize(pcm, 16000); fail("unvoiced accepted") }
            catch (_: IllegalArgumentException) { }
        }
    }
    @Test fun transposeIsExplicitAndNoPitchFolding() {
        val score = MelodyScore(listOf(MelodyNote(0,500,48,1f), MelodyNote(600,500,65,1f)),1100)
        assertEquals(0, score.suggestedTranspose)
        assertEquals(listOf(12,null,29),score.events(0).map{it.note})
        assertEquals(listOf(24,null,41), score.events(12).map { it.note })
        assertNull(score.copy(notes = score.notes + MelodyNote(1200,500,121,1f)).suggestedTranspose)
    }
    @Test fun eventPackingAndCrc() {
        assertEquals(0x29b1, MelodyWire.crc16("123456789".toByteArray()))
        val events = listOf(ScoreEvent(200,34), ScoreEvent(100,null))
        val bytes = MelodyWire.bytes(events)
        assertEquals(6,bytes.size); assertEquals((200 shl 7) or 34, events[0].word())
        assertEquals(4800, MelodyWire.preview(events).size)
        assertTrue(MelodyWire.midi(events).take(4).toByteArray().contentEquals("MThd".toByteArray()))
    }
    @Test fun resamplingKeepsPitch() {
        val pcm = FloatArray(44100) { (.3 * sin(2 * PI * 440 * it / 44100)).toFloat() }
        assertEquals(listOf(69), MelodyRecognition.recognize(pcm,44100).notes.map { it.midi })
    }
}
