package cn.soundcore.instrument

import org.junit.Test
import org.junit.Assume.assumeTrue
import org.json.JSONObject
import org.json.JSONArray
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Research harness: fixture paths and evaluation names never enter production. */
class RecognitionQualityAuditTest {
    private val root=File("../../..").canonicalFile
    private fun floats(file:File):FloatArray {
        val b=ByteBuffer.wrap(file.readBytes()).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(b.remaining()).also{b.get(it)}
    }
    private fun track(t:StablePitchTracker.Track)=JSONObject()
        .put("pitch",JSONArray(t.pitch.map{if(it.isFinite())it else JSONObject.NULL}))
        .put("probability",JSONArray(t.probability.toList())).put("rms",JSONArray(t.rms.toList()))
    private fun notes(a:List<MelodyNote>)=JSONArray(a.map{n->JSONObject().put("start_ms",n.startMs)
        .put("duration_ms",n.durationMs).put("midi",n.midi)})
    @Test fun heldoutDemoInputsRunOldAndNewWithoutReferenceLookup(){
        assumeTrue(System.getenv("SOUNDCORE_RECOGNITION_HELDOUT")=="1")
        val output=File(root,"build/recognition_quality_20261101/heldout")
        CrepePitchObserver{File(root,"app/android/app/src/main/assets/models/crepe_tiny.onnx").readBytes()}.use{model->
            for(id in listOf("demo_voice","demo_twinkle")){
                val pcm=floats(File(output,"$id.f32"))
                val raw=StablePitchTracker.track(pcm,{}, {false},exactWindow=true)
                val periodic=HarmonicRegisterRefinement.refine(pcm,raw)
                val neural=model.observe(pcm)
                val fused=BuiltinMelodyRecognition.fuse(periodic,neural)
                val old=MelodyRecognition.decode(pcm,fused,pcm.size/16,mode=MelodyInput.VOCAL,refineHarmonics=false,minimumVocalDwell=6)
                val current=BuiltinMelodyRecognition.recognize(pcm,model,MelodyInput.VOCAL)
                File(output,"$id.json").writeText(JSONObject().put("before",notes(old.notes)).put("after",notes(current.notes)).toString())
            }
        }
    }
    @Test fun ablateJointSequenceFromCachedObservations(){
        assumeTrue(System.getenv("SOUNDCORE_RECOGNITION_ABLATE")=="1")
        val folder=File(root,"build/recognition_quality_20261101/before")
        val output=File(root,"build/recognition_quality_20261101/ablation").also{it.mkdirs()}
        for(id in listOf("zuguo","qiansixi","chilege")){
            val doc=JSONObject(File(folder,"$id.json").readText())
            val pcm=floats(File(root,"build/builtin_recognition_20261101/$id.f32"))
            fun read(name:String):StablePitchTracker.Track {
                val a=doc.getJSONObject(name)
                fun values(key:String)=a.getJSONArray(key).let{v->DoubleArray(v.length()){i->if(v.isNull(i))Double.NaN else v.getDouble(i)}}
                return StablePitchTracker.Track(values("pitch"),values("probability"),values("rms"))
            }
            val flat=floats(File(folder,"${id}_neural.f32"));val neural=Array(flat.size/360){f->flat.copyOfRange(f*360,(f+1)*360)}
            for(weight in listOf(.35,.6,.85,1.0)){
                val fused=NeuralPitchSequence.decode(read("periodic"),neural,weight)
                val score=MelodyRecognition.decode(pcm,fused,40000,mode=MelodyInput.VOCAL,refineHarmonics=false,minimumVocalDwell=6)
                File(output,"${id}_${(weight*100).toInt()}.json").writeText(JSONObject().put("notes",notes(score.notes)).put("track",track(fused)).toString())
            }
        }
    }
    @Test fun exportActualBundledObservationsAndEveryDecoderStage(){
        assumeTrue(System.getenv("SOUNDCORE_RECOGNITION_AUDIT")=="1")
        val output=File(root,"build/recognition_quality_20261101/"+(System.getenv("SOUNDCORE_AUDIT_STAGE")?:"before"))
        output.mkdirs()
        CrepePitchObserver{File(root,"app/android/app/src/main/assets/models/crepe_tiny.onnx").readBytes()}.use{model->
            for(id in listOf("zuguo","qiansixi","chilege")){
                val pcm=floats(File(root,"build/builtin_recognition_20261101/$id.f32"))
                val raw=StablePitchTracker.track(pcm,{}, {false},exactWindow=true)
                val periodic=HarmonicRegisterRefinement.refine(pcm,raw)
                val neural=model.observe(pcm)
                val fused=BuiltinMelodyRecognition.fuse(periodic,neural)
                val onset=VocalOnsetEvidence.onsetEvidence(pcm)
                val seed=VocalNoteSegmentation.segment(fused,40000,MelodyInput.VOCAL,{false},onset,6)
                val boundary=VocalBoundaryEvidence.analyze(pcm,fused.rms)
                val refined=VocalNaturalRefinement.refine(seed.notes,fused,boundary,onset)
                val alternative=VocalMainNoteSegmentation.alternative(fused,40000,{false},onset)
                val recovered=VocalAlternativeRestoration.apply(refined.notes,alternative.notes,fused,boundary.novelty)
                val release=ReleaseContourProjection.apply(recovered,fused,onset)
                val validated=VocalOctaveValidation.refine(pcm,release)
                val projected=VocalContourProjection.apply(validated,fused,onset,boundary.novelty)
                val doc=JSONObject().put("raw",track(raw)).put("periodic",track(periodic)).put("fused",track(fused))
                    .put("seed",notes(seed.notes)).put("refined",notes(refined.notes)).put("recovered",notes(recovered))
                    .put("released",notes(release)).put("validated",notes(validated)).put("projected",notes(projected))
                val production=BuiltinMelodyRecognition.recognize(pcm,model,MelodyInput.VOCAL)
                doc.put("production",notes(production.notes)).put("algorithm",BuiltinMelodyRecognition.ALGORITHM)
                File(output,"$id.json").writeText(doc.toString())
                val bytes=ByteBuffer.allocate(neural.size*360*4).order(ByteOrder.LITTLE_ENDIAN)
                neural.forEach{row->row.forEach(bytes::putFloat)}
                File(output,"${id}_neural.f32").writeBytes(bytes.array())
            }
        }
    }
}
