package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject
import kotlin.math.*

class NoteSupportModelTest {
    private fun neural(pitch:Double)=Array(51){FloatArray(360){b->
        val midi=69+12*log2(10.0/440)+(1997.3794084376191+b*20)/100
        (.95*exp(-.5*((midi-pitch)/.22).pow(2))).toFloat()
    }}
    private fun track(midi:Double)=StablePitchTracker.Track(DoubleArray(100){midi},DoubleArray(100){.9},DoubleArray(100){.2})

    @Test fun exportedRandomInitializedModelMatchesTrainingRuntime(){
        val json=JSONObject(javaClass.classLoader!!.getResourceAsStream("note_support_vectors.json")!!.bufferedReader().use{it.readText()})
        assertEquals(json.getString("weights_sha256"),NoteSupportModel.WEIGHTS_SHA)
        val vectors=json.getJSONArray("vectors")
        for(i in 0 until vectors.length()){
            val row=vectors.getJSONObject(i);val x=row.getJSONArray("x")
            assertEquals(row.getDouble("expected"),NoteSupportModel.score(DoubleArray(x.length()){x.getDouble(it)}),2e-6)
        }
    }
    @Test fun evidenceHasNoAbsoluteRegisterOrSongIdentityFeature(){
        val a=NoteSupportEvidence(track(60.0),neural(60.0)).candidate(MelodyNote(0,800,60,.8f),60)
        val b=NoteSupportEvidence(track(72.0),neural(72.0)).candidate(MelodyNote(0,800,72,.8f),72)
        assertArrayEquals(a.values,b.values,.001)
        assertEquals(NoteSupportEvidence.NAMES.size,a.values.size)
        assertTrue(a.values.all{it.isFinite() && it in 0.0..1.00001})
    }
    @Test fun agreementOutranksWrongSemitoneAndOctave(){
        val evidence=NoteSupportEvidence(track(60.0),neural(60.0));val note=MelodyNote(0,800,60,.8f)
        val correct=NoteSupportModel.score(evidence.candidate(note,60).values)
        assertTrue(correct>.8)
        for(p in listOf(48,59,61,72))assertTrue(correct>NoteSupportModel.score(evidence.candidate(note,p).values)+.5)
    }
    @Test fun missingPhysicalAndNeuralEvidenceCannotBecomeHighConfidence(){
        val track=StablePitchTracker.Track(DoubleArray(100){Double.NaN},DoubleArray(100),DoubleArray(100){.001})
        val evidence=NoteSupportEvidence(track,Array(51){FloatArray(360)})
        assertTrue(NoteSupportModel.score(evidence.candidate(MelodyNote(0,800,60,.8f),60).values)<.2)
    }
    @Test fun emptyAndClippedWindowsAreFiniteAndModelRejectsBadInputs(){
        val empty=StablePitchTracker.Track(doubleArrayOf(),doubleArrayOf(),doubleArrayOf())
        val x=NoteSupportEvidence(empty,Array(1){FloatArray(360)}).candidate(MelodyNote(5000,200,60,.1f),60).values
        assertTrue(x.all{it.isFinite() && it in 0.0..1.0})
        for(bad in listOf(DoubleArray(11),DoubleArray(12){Double.NaN},DoubleArray(12){2.0})){
            try{NoteSupportModel.score(bad);fail("invalid features accepted")}catch(_:IllegalArgumentException){}
        }
    }
}
