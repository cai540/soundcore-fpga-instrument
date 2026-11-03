package cn.soundcore.instrument

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class SheetDocumentsTest {
    private fun page(note:Int,staff:Boolean=false)=SheetMusic(JSONObject().put("notation",if(staff)"staff" else "jianpu")
        .put("title","测试谱").put("bpm",80).put("numerator",4).put("denominator",4)
        .apply{if(!staff)put("tonic_midi",60)}
        .put("measures",JSONArray().put(JSONObject().put("id",1).put("events",JSONArray().put(
            JSONObject().put(if(staff)"midi" else "degree",note).put("ticks",96)))))
        .put("play_order",JSONArray(listOf(1,1))).put("review_unresolved",JSONArray(listOf("请核对八度点"))))
    @Test fun pageConcatenationPreservesRepeatsAndReviewNotesWithRemappedIds(){
        val merged=SheetDocuments.merge(listOf(page(1),page(2)))
        assertEquals(listOf(60,60,62,62),merged.compile().first.map{it.midi})
        assertEquals("[1,1,2,2]",merged.raw.getJSONArray("play_order").toString())
        assertEquals(2,merged.raw.getJSONArray("review_unresolved").length())
    }
    @Test fun staffPagesDoNotRequireJianpuTonic(){
        assertEquals(listOf(67,67,69,69),SheetDocuments.merge(listOf(page(67,true),page(69,true))).compile().first.map{it.midi})
    }
    @Test fun mismatchedKeysFailInsteadOfSilentlyTransposingAnotherPage(){
        val other=page(2).raw.put("tonic_midi",62)
        assertTrue(runCatching{SheetDocuments.merge(listOf(page(1),SheetMusic(other)))}.isFailure)
    }
}
