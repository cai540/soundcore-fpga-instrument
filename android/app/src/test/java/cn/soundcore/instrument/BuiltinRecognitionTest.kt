package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.json.JSONObject
import org.json.JSONArray
import kotlin.math.*

class BuiltinRecognitionTest {
    private val root=File("../../..").canonicalFile
    private fun observer()=CrepePitchObserver{File(root,"app/android/app/src/main/assets/models/crepe_tiny.onnx").readBytes()}
    private fun tone(midi:Double,ms:Int):FloatArray {
        var phase=0.0
        return FloatArray(ms*16){i->
            phase+=2*PI*440*2.0.pow((midi-69)/12)/16000
            val gate=min(1.0,min(i/180.0,(ms*16-1-i)/220.0)).coerceAtLeast(0.0)
            (gate*(.2*sin(phase)+.11*sin(2*phase)+.05*sin(3*phase))).toFloat()
        }
    }
    @Test fun bundledModelIsReusedAndRealSemitoneAndOctaveNotesSurvive(){
        observer().use{model->
            val pitches=listOf(60,61,62,74,67,67)
            val pcm=pitches.map{tone(it.toDouble(),420)+FloatArray(1600)}.reduce{a,b->a+b}
            val score=BuiltinMelodyRecognition.recognize(pcm,model,MelodyInput.INSTRUMENT)
            assertEquals(pitches,score.notes.map{it.midi})
            assertTrue(score.notes.zipWithNext().all{(a,b)->b.startMs-a.startMs-a.durationMs>=50})
            model.observe(tone(60.0,500));assertEquals(1,model.loads)
        }
    }
    @Test fun silenceAndCancellationNeverProduceGhostNotes(){
        observer().use{model->
            try{BuiltinMelodyRecognition.recognize(FloatArray(16000),model,MelodyInput.VOCAL);fail("silence became notes")}
            catch(_:IllegalArgumentException){}
            try{model.observe(tone(60.0,500),cancelled={true});fail("cancel ignored")}
            catch(_:InterruptedException){}
        }
    }
    @Test fun genuineShortVocalNoteIsNotLostForReducingFragments(){
        observer().use{model->
            val pcm=tone(60.0,450)+tone(64.0,100)+tone(67.0,500)+tone(65.0,350)
            val score=BuiltinMelodyRecognition.recognize(pcm,model,MelodyInput.VOCAL)
            assertEquals(listOf(60,64,67,65),score.notes.map{it.midi})
        }
    }
    @Test fun quietDcBiasedMelodyUsesTheSamePitchesAndPhraseSilence(){
        observer().use{model->
            val a=tone(60.0,500)+FloatArray(2000)+tone(64.0,500)+FloatArray(2000)+tone(67.0,500)
            val quiet=FloatArray(a.size){a[it]*.004f+.11f}
            val normal=BuiltinMelodyRecognition.recognize(a,model,MelodyInput.VOCAL)
            val decoded=BuiltinMelodyRecognition.recognize(quiet,model,MelodyInput.VOCAL)
            assertEquals(normal.notes.map{it.midi},decoded.notes.map{it.midi})
            assertEquals(listOf(60,64,67),decoded.notes.map{it.midi})
            assertTrue(decoded.notes.zipWithNext().all{(a,b)->b.startMs-a.startMs-a.durationMs>=60})
            assertEquals(1,model.loads)
        }
    }
    @Test fun quietNoiseWithDcDoesNotBecomeAMelody(){
        val random=java.util.Random(123)
        val pcm=FloatArray(16000){.1f+((random.nextDouble()-.5)*.0001).toFloat()}
        observer().use{model->
            try{BuiltinMelodyRecognition.recognize(pcm,model,MelodyInput.VOCAL);fail("white noise became a melody")}
            catch(_:IllegalArgumentException){}
        }
    }
    @Test fun neuralOctaveEvidenceDoesNotFlattenARealOctaveLeap(){
        val count=160;val p=DoubleArray(count){if(it<80)60.0 else 72.0}
        val track=StablePitchTracker.Track(p,DoubleArray(count){.9},DoubleArray(count){.2})
        val nn=Array(81){f->FloatArray(360){bin->
            val midi=69+12*log2(10.0/440)+(1997.3794084376191+bin*20)/100
            exp(-.5*((midi-(if(f<40)60 else 72))/.25).pow(2)).toFloat()
        }}
        val fused=BuiltinMelodyRecognition.fuse(track,nn)
        assertEquals(60.0,fused.pitch[30],.15);assertEquals(72.0,fused.pitch[130],.15)
    }
    @Test fun uncertainPeriodicNoiseIsRejectedWithoutOverwritingSupportedPitch(){
        val count=100;val p=DoubleArray(count){72.0};val confidence=DoubleArray(count){.9}
        for(i in 30..39)confidence[i]=.01
        val nn=Array(51){FloatArray(360)}
        val fused=BuiltinMelodyRecognition.fuse(StablePitchTracker.Track(p,confidence,DoubleArray(count){.2}),nn)
        assertEquals(72.0,fused.pitch[20],0.0)
        assertTrue((30..39).all{!fused.pitch[it].isFinite()})
    }
    @Test fun realRecordingsExportTheActualProductionPipeline(){
        org.junit.Assume.assumeTrue(System.getenv("SOUNDCORE_OFFLINE_REAL_AUDIO")=="1")
        val output=File(root,"build/builtin_recognition_20261101/audio").also{it.mkdirs()}
        val report=JSONArray()
        observer().use{model->for(id in listOf("zuguo","qiansixi","chilege")){
            val bytes=File(root,"build/builtin_recognition_20261101/$id.f32").readBytes()
            val buffer=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
            val pcm=FloatArray(buffer.remaining()).also{buffer.get(it)}
            val start=System.nanoTime()
            val score=BuiltinMelodyRecognition.recognize(pcm,model,MelodyInput.VOCAL)
            val elapsed=(System.nanoTime()-start)/1_000_000
            val baseline=MelodyRecognition.recognize(pcm,16000)
            val legacy=JSONArray();baseline.notes.forEach{n->legacy.put(JSONObject().put("start_ms",n.startMs).put("duration_ms",n.durationMs).put("midi",n.midi))}
            File(output,"${id}_legacy_notes.json").writeText(JSONObject().put("notes",legacy).toString(2))
            val notes=JSONArray();score.notes.forEach{n->notes.put(JSONObject().put("start_ms",n.startMs).put("duration_ms",n.durationMs).put("midi",n.midi))}
            File(output,"${id}_notes.json").writeText(JSONObject().put("source_duration_ms",score.sourceDurationMs).put("notes",notes).toString(2))
            val transpose=score.suggestedTranspose?:0
            if(score.suggestedTranspose!=null)File(output,"$id.mid").writeBytes(MelodyWire.midi(score.events(transpose)))
            report.put(JSONObject().put("case",id).put("notes",score.notes.size).put("desktop_ms",elapsed)
                .put("short_under120ms",score.notes.count{it.durationMs<120}).put("rests_over100ms",score.notes.zipWithNext().count{(a,b)->b.startMs-a.startMs-a.durationMs>=100})
                .put("model_loads",model.loads).put("network_calls",0).put("phone_performance_measured",false))
        }}
        File(output,"report.json").writeText(report.toString(2))
    }
}
