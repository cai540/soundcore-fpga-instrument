package cn.soundcore.instrument
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class OfflineSheetPipelineTest {
    @Test fun browserCompiledRealPagesUseTheSameNativeClockAndCapacity(){
        // Integration fixture: real local OCR + integer reference classifier; not board evidence.
        val file=File("../../../build/offline_ocr_20261031/native_contract_cases.json")
        if(!file.exists())return
        val cases=JSONArray(file.readText())
        repeat(cases.length()){i->val c=cases.getJSONObject(i);val music=SheetMusic(c.getJSONObject("native"));val events=music.compile().first
            assertEquals(c.getInt("notes"),events.count{it.midi!=null});assertEquals(c.getInt("ms"),events.last().let{it.startMs+it.durationMs})
            val parts=music.parts();assertEquals(c.getInt("notes"),parts.sumOf{it.score.notes.size});assertTrue(parts.all{it.score.durationMs<=180000 && it.score.notes.size<=512})}
    }
    @Test fun latestPackagedOcrScoresCompileThroughTheRealAndroidClock(){
        val folder=File("../../../build/recognition_quality_20261101/packaged")
        org.junit.Assume.assumeTrue(folder.isDirectory)
        for(name in listOf("zuguo","chilege","lantingxu")){
            val doc=JSONObject(File(folder,"${name}_sheet.json").readText()).getJSONObject("score")
            val music=SheetMusic(doc);val events=music.compile().first
            assertTrue(events.any{it.midi!=null})
            val parts=music.parts();assertEquals(events.count{it.midi!=null},parts.sumOf{it.score.notes.size})
            assertTrue(parts.all{it.score.durationMs<=180000&&it.score.notes.size<=512})
            assertTrue(events.zipWithNext().all{(a,b)->a.startMs+a.durationMs==b.startMs})
            assertEquals("phone",doc.getString("inference_location"))
        }
    }
    @Test fun phraseGatesKeepThePrintedClockAndNeverAddAPunctuationNote(){
        val score=JSONObject("""{"notation":"jianpu","tonic_midi":60,"bpm":60,"numerator":2,"denominator":4,"natural_phrasing":true,
            "measures":[{"id":1,"events":[{"degree":1,"ticks":96,"phrase_end":true},{"degree":2,"ticks":96}]}]}""")
        val music=SheetMusic(score);assertEquals(2,music.compile().first.size)
        val part=music.parts().single();assertEquals(2000,part.score.durationMs);assertEquals(820,part.score.notes[0].durationMs)
        assertEquals(1000,part.score.notes[1].startMs)
    }
}
