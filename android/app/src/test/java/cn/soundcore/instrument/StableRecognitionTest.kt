package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class StableRecognitionTest {
    private fun sound(ms:Int,pitch:(Int)->Double,amp:(Int)->Double={.25}):FloatArray {
        var phase=0.0
        return FloatArray(ms*16){ i ->
            val t=i/16;phase+=2*PI*440*2.0.pow((pitch(t)-69)/12)/16000
            (sin(phase)*amp(t)).toFloat()
        }
    }
    @Test fun repeatedSyllableWithoutCompleteSilenceGetsTwoAttacks() {
        val pcm=sound(1100,{67.0},{t->if(t in 480..550).07 else .25})
        val score=MelodyRecognition.recognize(pcm,16000)
        assertEquals(listOf(67,67),score.notes.map{it.midi})
        assertTrue(score.notes[1].startMs in 450..590)
    }
    @Test fun halfSemitoneVocalFlutterIsNotANewNote() {
        val pcm=sound(1500,{t->if(t in 500..690)60.64 else 60.0})
        assertEquals(listOf(60),MelodyRecognition.recognize(pcm,16000).notes.map{it.midi})
    }
    @Test fun actualChromaticNotesAreRetained() {
        val pcm=sound(1050,{t->when {t<350->60.0;t<700->61.0;else->62.0}})
        assertEquals(listOf(60,61,62),MelodyRecognition.recognize(pcm,16000).notes.map{it.midi})
    }
    @Test fun phraseRestIsNotFilledAcrossSamePitch() {
        val pcm=sound(600,{64.0})+FloatArray(2400)+sound(650,{64.0})
        val notes=MelodyRecognition.recognize(pcm,16000).notes
        assertEquals(listOf(64,64),notes.map{it.midi})
        assertTrue(notes[1].startMs-notes[0].startMs-notes[0].durationMs>=100)
    }
    @Test fun cancellationStopsThePitchWorker() {
        var calls=0
        try {
            MelodyRecognition.recognize(sound(3000,{67.0}),16000,cancelled={++calls>3})
            fail("cancelled recognition completed")
        } catch (_:InterruptedException) { assertTrue(calls<=5) }
    }
    @Test fun instrumentModeKeepsTheHighChromaticRange() {
        val score=MelodyRecognition.recognize(sound(750,{94.0}),16000,mode=MelodyInput.INSTRUMENT)
        assertEquals(listOf(94),score.notes.map{it.midi})
        assertTrue(score.notes[0].durationMs>650)
    }
}
