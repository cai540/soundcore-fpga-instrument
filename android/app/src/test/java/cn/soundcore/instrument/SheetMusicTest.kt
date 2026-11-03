package cn.soundcore.instrument

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.io.ByteArrayOutputStream

class SheetMusicTest {
    private val root=File("../../..").canonicalFile
    private fun cases()=JSONArray(File(root,"tests/fixtures/sheet_music_cases.json").readText())
    @Test fun independentSharedVectorsMatchPitchRhythmRestsAndTieSemantics() {
        val cases=cases()
        for(i in 0 until cases.length()) {
            val case=cases.getJSONObject(i);val music=SheetMusic(case.getJSONObject("score"));val events=music.compile().first
            val expected=case.getJSONArray("expected");assertEquals(case.getString("id"),expected.length(),events.size)
            events.forEachIndexed{k,e->val n=expected.getJSONArray(k)
                assertEquals(n.getInt(0),e.startMs);assertEquals(n.getInt(1),e.durationMs)
                assertEquals(if(n.isNull(2))null else n.getInt(2),e.midi)}
            val part=music.parts().single();val score=part.score
            assertTrue(score.keepScoreRests)
            assertEquals(events.sumOf{it.durationMs},score.events(score.suggestedTranspose!!).sumOf{it.durationMs})
        }
    }
    @Test fun longPartsPreserveEveryNoteAndTheWholeDuration() {
        val raw=JSONObject(cases().getJSONObject(0).getJSONObject("score").toString()).put("bpm",120)
        val measures=JSONArray();val order=JSONArray()
        repeat(24){i->measures.put(JSONObject().put("id",i+1).put("events",JSONArray(listOf(
            JSONObject().put("degree",1).put("ticks",96),JSONObject().put("degree",2).put("ticks",96),
            JSONObject().put("degree",3).put("ticks",96),JSONObject().put("degree",4).put("ticks",96)))));order.put(i+1)}
        raw.put("measures",measures).put("play_order",order)
        val music=SheetMusic(raw);val parts=music.parts()
        assertEquals(1,parts.size);assertEquals(48000,parts.sumOf{it.score.durationMs})
        assertEquals(96,parts.sumOf{it.score.notes.size});assertTrue(parts.all{it.score.durationMs<=180000})
    }
    @Test fun invalidPitchOrderAndFractionalDurationAreRejectedInsteadOfBecomingAPlayableGuess() {
        val original=cases().getJSONObject(0).getJSONObject("score")
        val fractional=JSONObject(original.toString()).also{it.getJSONArray("measures").getJSONObject(0).getJSONArray("events").getJSONObject(0).put("ticks",48.5)}
        val overflow=JSONObject(original.toString()).put("play_order",JSONArray(listOf(4294967297L)))
        val unknownPitch=JSONObject(original.toString()).put("notation","staff")
        listOf(fractional,overflow,unknownPitch).forEach{assertTrue(runCatching{SheetMusic(it).compile()}.isFailure)}
    }
    @Test fun sourceRecordingPersistsWithoutAnyScoreAndLegacyScoresRemainReadable() {
        val recording=MelodyView(sourceDurationMs=5000,sourceName="手机录音",range=MelodyRange(0,5000))
        val json=MelodySessionJson.encode(recording)
        assertFalse(json.getBoolean("has_score"));assertEquals(5000,json.getInt("duration"));assertNull(MelodySessionJson.score(JSONObject(json.toString())))
        val old=JSONObject().put("version",2).put("notes",JSONArray().put(JSONArray(listOf(0,1000,60,1.0)))).put("duration",1000)
        assertFalse(MelodySessionJson.score(old)!!.keepScoreRests)
        val score=SheetMusic(cases().getJSONObject(1).getJSONObject("score")).parts().single().score
        val restored=MelodySessionJson.score(MelodySessionJson.encode(MelodyView(score=score,range=MelodyRange(0,4000),scoreRange=MelodyRange(0,4000))))!!
        assertTrue(restored.keepScoreRests);assertEquals(4000,restored.events(0).sumOf{it.durationMs})
    }
    @Test fun printedSheetFixtureUsesTheRealAndroidUploadProtocol() {
        // This is a known symbol fixture, not a fabricated successful vision response.
        val music=SheetMusic(cases().getJSONObject(1).getJSONObject("score"));val score=music.parts().single().score
        writeUploadFixture(score,"android_fixture")
    }
    @Test fun observedRealCloudResultMatchesVisibleSheetAndUsesAndroidUploadProtocol() {
        val observed=JSONObject(File(root,"tests/fixtures/sheet_vision_observed.json").readText())
        assertEquals("observed_real_cloud_result",observed.getJSONObject("provenance").getString("kind"))
        val music=SheetMusic(observed.getJSONObject("result").getJSONObject("score"));val events=music.compile().first
        val expected=observed.getJSONArray("expected_events");assertEquals(expected.length(),events.size)
        events.forEachIndexed{i,e->val n=expected.getJSONArray(i);assertEquals(n.getInt(0),e.startMs)
            assertEquals(n.getInt(1),e.durationMs);assertEquals(if(n.isNull(2))null else n.getInt(2),e.midi)}
        val part=music.parts().single();assertEquals(12000,part.score.durationMs)
        writeUploadFixture(part.score,"real_android_fixture")
    }
    private fun writeUploadFixture(score:MelodyScore,directory:String) {
        val events=score.events(score.suggestedTranspose!!);val transfer=ScoreTransfer(events,1,0x3456)
        val bytes=ByteArrayOutputStream();var sequence=5
        while(!transfer.done){val cmd=transfer.next()!!;bytes.write(Protocol.encodeCommand(cmd.type,sequence++,cmd.payload))
            val state=when(cmd.type){Protocol.SCORE_ABSOLUTE_BEGIN->UploadedScoreState(2,0,0,0,7,0,1,0,transfer.token,schema=2)
                Protocol.SCORE_DATA->UploadedScoreState(2,0,transfer.confirmed+(cmd.payload.size-4)/3,0,7,0,1,0,transfer.token,schema=2)
                else->UploadedScoreState(1,0,transfer.count,0,7,0,1,transfer.crc,transfer.token,schema=2)};transfer.acknowledge(cmd.type,state)}
        bytes.write(Protocol.encodeCommand(Protocol.SCORE_ACTION,sequence,byteArrayOf(1)))
        val out=File(root,"build/sheet_score_20261030/$directory").apply{mkdirs()};val data=bytes.toByteArray()
        File(out,"android_upload.hex").writeText(data.joinToString("\n"){"%02x".format(it.toInt() and 255)})
        File(out,"android_upload_meta.vh").writeText("`define FIXTURE_BYTES ${data.size}\n`define FIXTURE_EVENTS ${events.size}\n`define FIXTURE_NOTES ${score.notes.size}\n`define FIXTURE_CRC 16'h${transfer.crc.toString(16)}\n`define FIXTURE_MS ${events.sumOf{it.durationMs}}\n")
    }
}
