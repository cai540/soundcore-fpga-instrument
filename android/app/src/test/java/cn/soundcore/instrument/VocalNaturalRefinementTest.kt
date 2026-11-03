package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class VocalNaturalRefinementTest {
    @Test fun restoredPitchAndBoundaryOutrankAnInferredKey() {
        val seeds=listOf(MelodyNote(0,800,69,.9f))
        val restored=listOf(MelodyNote(0,410,70,.8f),MelodyNote(410,390,69,.9f))
        val (notes,boundaries)=VocalNaturalRefinement.protections(seeds,restored)
        assertArrayEquals(booleanArrayOf(true,false),notes)
        assertArrayEquals(booleanArrayOf(false,true),boundaries)
    }
    @Test fun parentMappingPreservesRealGapsAndExistingRepeats() {
        val seeds=listOf(MelodyNote(3,800,79,.9f),MelodyNote(953,500,79,.8f))
        val restored=listOf(MelodyNote(3,407,79,.9f),MelodyNote(410,393,77,.8f),seeds[1])
        val (notes,boundaries)=VocalNaturalRefinement.protections(seeds,restored)
        assertArrayEquals(booleanArrayOf(false,true,false),notes)
        assertArrayEquals(booleanArrayOf(false,true,false),boundaries)
        assertEquals(150,restored[2].startMs-restored[1].startMs-restored[1].durationMs)
    }
    @Test fun existingShortChromaticNotesAreNeverMarkedAsInvented() {
        val seeds=listOf(MelodyNote(0,150,60,.9f),MelodyNote(150,150,61,.9f),MelodyNote(300,150,62,.9f))
        val (notes,boundaries)=VocalNaturalRefinement.protections(seeds,seeds)
        assertFalse(notes.any{it});assertFalse(boundaries.any{it})
    }
    @Test fun articulatedHumanRangeSemitoneWithVibratoStaysTwoNotes() {
        var phase=0.0
        val pcm=FloatArray(1600*16){i->
            val ms=i/16;val n=if(ms<800)70.0 else 69.0
            val pitch=n+.8*sin(2*PI*5.3*ms/1000+.7)
            phase+=2*PI*440*2.0.pow((pitch-69)/12)/16000
            val amp=if(ms in 770..820).035 else .25
            (sin(phase)*amp).toFloat()
        }
        assertEquals(listOf(70,69),MelodyRecognition.recognize(pcm,16000).notes.map{it.midi})
    }
}
