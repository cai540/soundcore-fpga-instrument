package cn.soundcore.instrument

import org.junit.Test
import org.junit.Assume.assumeTrue
import org.json.JSONObject
import org.json.JSONArray
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Opt-in training export: only generated clips with known oscillator labels.
 * Production has no fixture/path/song lookup and no training capability.
 */
class NoteSupportDatasetTest {
    private val root=File("../../..").canonicalFile
    private fun pcm(file:File):FloatArray {
        val b=ByteBuffer.wrap(file.readBytes()).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(b.remaining()).also{b.get(it)}
    }
    @Test fun exportGeneratedTrainingEvidence(){
        assumeTrue(System.getenv("SOUNDCORE_SUPPORT_DATASET")=="1")
        val folder=File(root,"build/independent_note_support_20261101/data")
        val manifest=JSONObject(File(folder,"manifest.json").readText())
        val clips=manifest.getJSONArray("clips")
        CrepePitchObserver{File(root,"app/android/app/src/main/assets/models/crepe_tiny.onnx").readBytes()}.use{model->
            File(folder,"features.jsonl").bufferedWriter().use{out->
                for(i in 0 until clips.length()){
                    val clip=clips.getJSONObject(i);val audio=RecognitionSignal.prepare(pcm(File(folder,clip.getString("file"))))
                    val raw=StablePitchTracker.track(audio,{}, {false},exactWindow=true)
                    val periodic=HarmonicRegisterRefinement.refine(audio,raw)
                    val neural=model.observe(audio)
                    val evidence=NoteSupportEvidence(BuiltinMelodyRecognition.fuse(periodic,neural),neural)
                    val windows=clip.getJSONArray("windows")
                    for(j in 0 until windows.length()){
                        val w=windows.getJSONObject(j);val target=w.getInt("midi")
                        val note=MelodyNote(w.getInt("start_ms"),w.getInt("duration_ms"),maxOf(24,target),1f)
                        val candidates=if(target<0)(45..89 step 4).toList() else
                            listOf(target,target-12,target+12,target-2,target-1,target+1,target+2).filter{it in 24..95}
                        for(candidate in candidates){
                            val v=evidence.candidate(note,candidate)
                            out.write(JSONObject().put("clip",clip.getString("id")).put("split",clip.getString("split"))
                                .put("window",j).put("candidate",candidate).put("target",target)
                                .put("x",JSONArray(v.values.toList())).put("y",if(candidate==target)1 else 0).toString())
                            out.newLine()
                        }
                    }
                    if(i%10==0)println("support dataset ${i+1}/${clips.length()}")
                }
            }
            check(model.loads==1)
        }
    }
}
