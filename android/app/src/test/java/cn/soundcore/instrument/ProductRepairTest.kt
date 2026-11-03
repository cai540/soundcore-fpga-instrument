package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import kotlin.math.*

class ProductRepairTest {
    @Test fun microphoneAnalysisKeepsTheFundamentalAndLevelWithoutBluetooth(){
        val frame=ScopeAnalysis.frame(FloatArray(1024){(.25*sin(2*PI*1000*it/16000)).toFloat()},7)
        assertEquals(64,frame.spectrum.indices.maxBy{frame.spectrum[it]})
        assertEquals(-15.05f,frame.rmsDb,.05f);assertEquals(-12.04f,frame.spectrum[64],.1f)
        assertEquals(7L,frame.number);assertTrue(frame.spectrum.all{it.isFinite()})
        val quiet=ScopeAnalysis.frame(FloatArray(1024),8)
        assertTrue(quiet.rmsDb<=-100);assertTrue(quiet.spectrum.all{it<=-100})
    }
    @Test fun realBundledModelKeepsASustainedNoteAcrossTheLongRecordingWindow(){
        val pcm=FloatArray(32000*16){i->(.2*sin(2*PI*261.625565*i/16000)).toFloat()}
        CrepePitchObserver{File("src/main/assets/models/crepe_tiny.onnx").readBytes()}.use{model->
            val progress=mutableListOf<Int>()
            val score=BuiltinMelodyRecognition.recognize(pcm,model,MelodyInput.INSTRUMENT,{p,_->progress+=p})
            assertEquals(1,model.loads);assertEquals(32000,score.sourceDurationMs)
            assertTrue(score.notes.all{it.midi==60})
            assertTrue(score.notes.any{it.startMs<28000 && it.startMs+it.durationMs>28000})
            assertTrue(progress.zipWithNext().all{(a,b)->b>=a});assertEquals(100,progress.last())
        }
    }
    @Test fun nearestListIsBoundedAndLateJdyDisplacesOtherDevices(){
        val noisy=(0..40).map{FoundDevice("Other $it","address$it")}
        val selected=orderedDevices(noisy+FoundDevice("JDY-23","instrument"))
        assertEquals(5,selected.size);assertEquals("instrument",selected.first().address)
        assertEquals(1,orderedDevices(List(12){FoundDevice("JDY","same")}).size)
    }
    @Test fun bulkPlotSurvivesEveryNotificationSplitAndCorruption(){
        val payload=ByteArray(80){it.toByte()};payload[0]=1;payload[1]=0x48;payload[2]=0
        val body=byteArrayOf(1,0x86.toByte(),21,80)+payload
        val frame=byteArrayOf(0xa5.toByte())+body+byteArrayOf(Protocol.crc8(body).toByte())
        for(split in frame.indices){val stream=FrameStream()
            val replies=stream.push(frame.copyOfRange(0,split))+stream.push(frame.copyOfRange(split,frame.size))
            assertArrayEquals(payload,ToolWire.checked(replies.single(),ToolWire.LIVE_SNAPSHOT))}
        val bad=frame.copyOf();bad[37]=(bad[37].toInt()xor 8).toByte();assertTrue(FrameStream().push(bad).isEmpty())
    }
    @Test fun fullLengthScoreAndLargerTransferKeepRestsAndTheSourceClock(){
        val notes=(0..179).map{MelodyNote(it*650,500,60+it%7,1f)}
        val score=MelodyWorkspace.validated(MelodyScore(notes,120000,true,0))
        assertEquals(120000,score.events(0).sumOf{it.durationMs})
        val transfer=ScoreTransfer(score.events(0),1,123)
        assertTrue(transfer.count>256);assertTrue(transfer.count<=1023)
        assertEquals(180000,MelodyRange(0,180000).durationMs)
        assertThrows(IllegalArgumentException::class.java){MelodyRange(0,180001)}
        assertThrows(IllegalArgumentException::class.java){ScoreTransfer(List(1024){ScoreEvent(20,24)},1,123)}
    }
    @Test fun oledSummaryAcceptsLongRecordingAndManyNotes(){
        val summary=CaptureDisplay.from(MelodyView(recording=true,seconds=160),true)
        assertEquals(1800,summary.duration);assertEquals(1600,summary.position)
        val payload=CaptureDisplay(stage=4,notes=900).payload()
        assertEquals(17,Protocol.encodeCommand(Protocol.CAPTURE_DISPLAY,1,payload).size)
    }
    @Test fun thirtyWholeArrangementsHaveDistinctSourcesAndPlayableCapacity(){
        val files=File("src/main/assets/scores").listFiles()!!.filter{it.extension=="json"}
        assertEquals(30,files.size)
        val scores=files.map{StructuredScore.parse(it.readText())}
        assertEquals(30,scores.map{it.id}.distinct().size)
        scores.forEach{s->assertEquals(1,s.parts.size);assertTrue(s.durationMs in 60000..120000)
            assertTrue(s.parts.single().events(0).size<=1023);assertTrue(s.parts.single().keepScoreRests)}
    }
}
