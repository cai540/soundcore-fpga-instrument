package cn.soundcore.instrument

import org.json.JSONArray
import org.json.JSONObject

/** A recording can be saved before any recognition result exists. */
object MelodySessionJson {
    fun encode(v:MelodyView):JSONObject {
        val s=v.score;val range=v.scoreRange?:v.range?:error("缺少片段范围")
        val notes=JSONArray();s?.notes?.forEach{notes.put(JSONArray(listOf(it.startMs,it.durationMs,it.midi,it.confidence)))}
        return JSONObject().put("version",3).put("has_score",s!=null).put("duration",s?.sourceDurationMs?:v.sourceDurationMs)
            .put("notes",notes).put("keep_score_rests",s?.keepScoreRests?:false).put("transpose",v.transpose).put("timbre",v.timbre)
            .put("tonic_key",s?.tonicKey?:JSONObject.NULL)
            .put("input_mode",v.inputMode.name).put("algorithm_version",v.algorithmVersion).put("score_origin",v.scoreOrigin)
            .put("score_algorithm",v.scoreAlgorithm).put("recognition_engine",v.engine.name)
            .put("range_start",range.startMs).put("range_end",range.endMs).put("source_name",v.sourceName).put("edited",v.edited)
    }
    fun score(j:JSONObject):MelodyScore? {
        require(j.getInt("version") in 1..3)
        if(j.getInt("version")==3 && !j.getBoolean("has_score"))return null
        val a=j.getJSONArray("notes");require(a.length() in 1..1023)
        val notes=(0 until a.length()).map{val n=a.getJSONArray(it);MelodyNote(n.getInt(0),n.getInt(1),n.getInt(2),n.getDouble(3).toFloat())}
        return MelodyWorkspace.validated(MelodyScore(notes,j.getInt("duration"),j.optBoolean("keep_score_rests",false),
            if(j.isNull("tonic_key"))null else j.getInt("tonic_key").also{require(it in 0..11)}))
    }
}
