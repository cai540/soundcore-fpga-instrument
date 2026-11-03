package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import org.json.JSONObject

class ProductToolsTest {
    @Test fun transientDeviceErrorsAreNotMisclassifiedAsOldFirmware(){
        val failure=assertThrows(IllegalStateException::class.java){ToolWire.checked(WireFrame(Protocol.ERROR,1,byteArrayOf(5)),ToolWire.STATUS)}
        assertFalse(failure.message!!.contains("不支持"))
    }
    @Test fun queuedExitRepliesCannotStealANewRequest(){
        val owner=ToolReplyOwner();val stop=QueuedCommand(ToolWire.DIAGNOSE,byteArrayOf(0));val start=QueuedCommand(ToolWire.DIAGNOSE,byteArrayOf(32))
        owner.begin(start);owner.started(stop,8);assertFalse(owner.matches(8));owner.started(start,9)
        assertFalse(owner.matches(8));assertTrue(owner.matches(9));owner.clear();assertFalse(owner.matches(9))
    }
    @Test fun bulkFramesSurviveEveryFragmentBoundary(){
        val payload=ByteArray(128){(it*13).toByte()};payload[0]=1;payload[1]=0x55;payload[2]=0
        val body=byteArrayOf(1,0x86.toByte(),7,128.toByte())+payload
        val frame=byteArrayOf(0xa5.toByte())+body+byteArrayOf(Protocol.crc8(body).toByte())
        for(split in 0..frame.size){val stream=FrameStream();val replies=stream.push(frame.copyOfRange(0,split))+stream.push(frame.copyOfRange(split,frame.size))
            assertEquals(1,replies.size);assertArrayEquals(payload,ToolWire.checked(replies.single(),0x55))}
        val stream=FrameStream();val corrupt=frame.copyOf();corrupt[32]=(corrupt[32].toInt()xor 4).toByte()
        assertTrue(stream.push(corrupt).isEmpty());assertEquals(1,stream.push(frame).size)
    }
    @Test fun rtlRecordingDecodesIdenticallyAndWavHasCorrectRate(){
        val root=File("../../..").canonicalFile
        val file=File(root,"build/acceptance_20261102/record_bytes.txt")
        val bytes=file.readText().trim().split(Regex("\\s+")).map{it.toInt(16).toByte()}.toByteArray()
        val pcm=DeviceAudioCodec.decode(bytes,1024)
        assertEquals(1024,pcm.size);assertEquals(File(root,"build/acceptance_20261102/record_crc.txt").readText().trim().toInt(16),ToolWire.crc16(bytes))
        val wav=DeviceAudioCodec.wav(pcm);assertEquals(2092,wav.size);assertEquals("RIFF",String(wav.copyOfRange(0,4)));assertEquals(8000,ToolWire.u16(wav,24))
        assertTrue(pcm.any{it.toInt()!=0})
        val expected=File(root,"build/acceptance_20261102/record_decoded.txt").readLines().map{it.toShort()}.toShortArray()
        assertArrayEquals(expected,pcm)
    }
    @Test fun mappingsRejectWholeInvalidUpdate(){
        assertEquals(8,ToolWire.mapPayload(true,listOf(0,1,2,3,4,5,6)).size)
        assertThrows(IllegalArgumentException::class.java){ToolWire.mapPayload(true,listOf(0,1,2,3,4,5,5))}
    }
    @Test fun scoreCatalogPreservesRestsAndSplitsBoundedParts(){
        val root=File("src/main/assets/scores");assertEquals(30,root.listFiles()!!.size)
        root.listFiles()!!.forEach{file->val score=StructuredScore.parse(file.readText());assertTrue(score.parts.isNotEmpty())
            score.parts.forEach{part->assertTrue(part.durationMs in 60000..120000);assertTrue(part.keepScoreRests);assertTrue(part.events(0).any{it.note==null})}}
        val template=JSONObject(root.listFiles()!!.first().readText());template.put("bpm",0)
        assertThrows(IllegalArgumentException::class.java){StructuredScore.parse(template.toString())}
    }
}
