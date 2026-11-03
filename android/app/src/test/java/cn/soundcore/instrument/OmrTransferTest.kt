package cn.soundcore.instrument
import org.junit.Test
import org.junit.Assert.*

class OmrTransferTest {
    private fun reply(id:Int,status:Int,count:Int,crc:Long=OmrTransfer.MODEL_CRC):WireFrame {
        val p=ByteArray(14);p[0]=id.toByte();p[1]=(id shr 8).toByte();p[2]=status.toByte();p[3]=6;p[8]=count.toByte();p[9]=1
        repeat(4){p[10+it]=(crc shr (8*it)).toByte()};return WireFrame(Protocol.ERROR,0,p)
    }
    @Test fun fiveCommandsMatchTheActualRtlContract(){
        val t=OmrTransfer(0x1234,ByteArray(32){it.toByte()});val kinds=mutableListOf<Int>();val counts=listOf(0,11,22,32,32)
        repeat(5){i->val c=t.next()!!;kinds+=c.type;Protocol.encodeCommand(c.type,i,c.payload)
            if(c.type==Protocol.OMR_DATA){assertEquals(if(i==1)0 else if(i==2)11 else 22,c.payload[2].toInt())}
            t.acknowledge(reply(0x1234,if(i==4)1 else 0,counts[i]))}
        assertEquals(listOf(96,97,97,97,98),kinds);assertEquals(6,t.result!!.symbolClass);assertNull(t.next())
    }
    @Test fun staleIdOldFirmwareWrongVersionAndUnexpectedCountReject(){
        listOf(reply(2,0,0),reply(1,0,0,1),reply(1,0,11),WireFrame(224,0,byteArrayOf(2))).forEach{r->
            assertTrue(runCatching{OmrTransfer(1,ByteArray(32)).acknowledge(r)}.isFailure)}
        assertTrue(runCatching{Protocol.encodeCommand(97,1,byteArrayOf(1,0,31,0,0))}.isFailure)
    }
    @Test fun cancelRemovesOnlyOmrTransfersFromTheQueue(){
        val q=CommandQueue();q.offer(QueuedCommand(96,byteArrayOf(1,0)));q.offer(QueuedCommand(Protocol.NOTE_OFF,byteArrayOf(1)));q.removeOmrTransfers()
        assertEquals(Protocol.NOTE_OFF,q.take()!!.type);assertNull(q.take())
    }
}
