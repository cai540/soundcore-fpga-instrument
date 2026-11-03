package cn.soundcore.instrument

import org.junit.Test
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.json.JSONObject
import org.json.JSONArray
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

class NoteSupportRegressionTest {
    private val root=File("../../..").canonicalFile
    private fun floats(path:File):FloatArray{
        val b=ByteBuffer.wrap(path.readBytes()).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(b.remaining()).also{b.get(it)}
    }
    @Test fun realRecordingsPreserveAcceptedNotesAndTiming(){
        assumeTrue(System.getenv("SOUNDCORE_SUPPORT_REGRESSION")=="1")
        val folder=File(root,"build/independent_note_support_20261101")
        val out=File(folder,"real").also{it.mkdirs()}
        CrepePitchObserver{File(root,"app/android/app/src/main/assets/models/crepe_tiny.onnx").readBytes()}.use{model->
            for(id in listOf("zuguo","qiansixi","chilege","demo_voice","demo_twinkle")){
                val demo=id.startsWith("demo_")
                val audio=floats(File(root,if(demo)"build/recognition_quality_20261101/heldout/$id.f32" else "build/builtin_recognition_20261101/$id.f32"))
                val before=JSONObject(File(folder,"baseline/"+(if(demo)"heldout" else "real")+"/$id.json").readText())
                    .getJSONArray(if(demo)"after" else "production")
                val score=BuiltinMelodyRecognition.recognize(audio,model,MelodyInput.VOCAL)
                val notes=JSONArray(score.notes.map{n->JSONObject().put("start_ms",n.startMs).put("duration_ms",n.durationMs)
                    .put("midi",n.midi).put("confidence",n.confidence)})
                File(out,"$id.json").writeText(JSONObject().put("notes",notes).put("model_sha256",NoteSupportModel.WEIGHTS_SHA).toString(2))
                assertEquals("$id note count",before.length(),score.notes.size)
                for(i in score.notes.indices){val b=before.getJSONObject(i);val n=score.notes[i]
                    assertEquals("$id note $i pitch",b.getInt("midi"),n.midi)
                    assertEquals("$id note $i onset",b.getInt("start_ms"),n.startMs)
                    assertEquals("$id note $i duration",b.getInt("duration_ms"),n.durationMs)
                    assertTrue(n.confidence.isFinite() && n.confidence in 0f..1f)
                }
            }
            assertEquals(1,model.loads)
        }
    }
}
