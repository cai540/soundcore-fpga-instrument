package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class AcousticNoteConsensusTest {
    private fun sameEvents(a:List<MelodyNote>,b:List<MelodyNote>){
        assertEquals(a.map{Triple(it.startMs,it.durationMs,it.midi)},b.map{Triple(it.startMs,it.durationMs,it.midi)})
        assertTrue(b.all{it.confidence.isFinite() && it.confidence in 0f..1f})
    }
    private fun track(pitch:Double)=StablePitchTracker.Track(DoubleArray(100){pitch},DoubleArray(100){.9},DoubleArray(100){.2})
    private fun neural(pitch:Double)=Array(51){FloatArray(360){bin->
        val midi=69+12*log2(10.0/440)+(1997.3794084376191+bin*20)/100
        (.95*exp(-.5*((midi-pitch)/.22).pow(2))).toFloat()
    }}
    @Test fun conflictingDecoderLabelIsCorrectedOnlyByBothIndependentSources(){
        val a=listOf(MelodyNote(0,800,60,.8f));val b=AcousticNoteConsensus.resolve(a,track(62.0),neural(62.0))
        assertEquals(62,b.single().midi);assertEquals(0,b.single().startMs);assertEquals(800,b.single().durationMs)
    }
    @Test fun neuralOctaveErrorCannotMoveAConfidentPhysicalFundamental(){
        val a=listOf(MelodyNote(0,800,60,.9f));sameEvents(a,AcousticNoteConsensus.resolve(a,track(60.0),neural(72.0)))
    }
    @Test fun uncertainBriefEvidenceDoesNotOverwriteTheWholeNote(){
        val t=track(60.0);for(i in 40..49)t.pitch[i]=62.0
        val a=listOf(MelodyNote(0,800,60,.9f));sameEvents(a,AcousticNoteConsensus.resolve(a,t,neural(62.0)))
    }
    @Test fun validShortNotesAndPhraseRestsKeepTheirTiming(){
        val a=listOf(MelodyNote(0,100,60,.9f),MelodyNote(300,600,72,.9f))
        val t=track(72.0);val b=AcousticNoteConsensus.resolve(a,t,neural(72.0))
        sameEvents(a,b);assertEquals(a.first(),b.first())
    }
    @Test fun weakModelAndCancellationDoNotInventCorrections(){
        val a=listOf(MelodyNote(0,800,60,.9f));sameEvents(a,AcousticNoteConsensus.resolve(a,track(62.0),Array(51){FloatArray(360){.01f}}))
        try{AcousticNoteConsensus.resolve(a,track(60.0),neural(60.0),{true});fail("cancel ignored")}catch(_:InterruptedException){}
    }
    @Test fun restoredShortLabelWithNoAcousticOrNeuralSupportIsRejected(){
        val t=track(60.0);t.probability.fill(.01)
        val a=listOf(MelodyNote(0,150,63,.01f))
        assertTrue(AcousticNoteConsensus.resolve(a,t,neural(60.0)).isEmpty())
        t.probability.fill(.8)
        val supported=AcousticNoteConsensus.resolve(a,t,neural(60.0)).single()
        assertEquals(60,supported.midi);assertEquals(150,supported.durationMs)
    }
}
