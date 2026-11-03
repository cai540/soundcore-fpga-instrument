package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test

class ScoreTransferTest {
    private fun state(flags: Int,count: Int,crc: Int = 0,token: Int = 123) =
        UploadedScoreState(flags,0,count,0,7,0,1,crc,token,schema=2)
    @Test fun transactionRequiresEveryAckAndFinalCrc() {
        val transfer = ScoreTransfer(List(8) { ScoreEvent(200,it) },1,123)
        assertEquals(Protocol.SCORE_ABSOLUTE_BEGIN,transfer.next()!!.type)
        transfer.acknowledge(Protocol.SCORE_ABSOLUTE_BEGIN,state(2,0))
        for (n in listOf(3,6,8)) {
            val packet = transfer.next()!!
            assertEquals(Protocol.SCORE_DATA,packet.type)
            Protocol.encodeCommand(packet.type,12,packet.payload)
            transfer.acknowledge(packet.type,state(2,n))
            assertEquals(n,transfer.confirmed)
        }
        assertEquals(Protocol.SCORE_COMMIT,transfer.next()!!.type)
        try { transfer.acknowledge(Protocol.SCORE_COMMIT,state(1,8,transfer.crc xor 1)); fail("bad CRC accepted") }
        catch (_: IllegalArgumentException) { }
        transfer.acknowledge(Protocol.SCORE_COMMIT,state(1,8,transfer.crc))
        assertTrue(transfer.done); assertNull(transfer.next())
    }
    @Test fun mismatchedTokenAndOutOfOrderAckRejected() {
        val t = ScoreTransfer(listOf(ScoreEvent(300,0)),0,123)
        t.next()
        try { t.acknowledge(Protocol.SCORE_ABSOLUTE_BEGIN,state(2,0,token = 456)); fail() }
        catch (_: IllegalArgumentException) { }
        t.acknowledge(Protocol.SCORE_ABSOLUTE_BEGIN,state(2,0))
        t.next()
        try { t.acknowledge(Protocol.SCORE_DATA,state(2,0)); fail() }
        catch (_: IllegalArgumentException) { }
        assertEquals(0,t.confirmed)
    }
    @Test fun scoreStatusDoesNotContaminateLegacyState() {
        val b = byteArrayOf(1,17,0,0,2,0,1,6,4,1,0x34,0x12,0x78,0x56)
        val s = UploadedScoreState.from(b)!!
        assertTrue(s.guiding); assertEquals(512,s.count);assertEquals(256,s.step)
        assertEquals(0x1234,s.crc); assertEquals(0x5678,s.token)
        assertNull(DeviceState.from(b)); assertNull(UploadedScoreState.from(b.copyOf(13)))
    }
}
