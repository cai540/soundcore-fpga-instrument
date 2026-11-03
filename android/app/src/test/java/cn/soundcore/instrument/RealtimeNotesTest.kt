package cn.soundcore.instrument
import org.junit.Assert.*
import org.junit.Test

class RealtimeNotesTest {
    @Test fun rapidReleasedNotesNeverReplayAfterFingerUp() {
        val mailbox=RealtimeNotes()
        mailbox.down(0,180);mailbox.sent(mailbox.peek(0)!!,0)
        repeat(1000) { val p=it%7; mailbox.down(p,120);mailbox.up(p) }
        mailbox.release()
        val last=mailbox.peek(16)!!
        assertEquals(0,last.held);assertEquals(0,last.attacks)
        mailbox.sent(last,16);assertNull(mailbox.peek(32))
    }
    @Test fun overlappingKeysAndReleaseKeepOnlyTheCurrentChord() {
        val m=RealtimeNotes();m.down(1,200);m.down(4,200);m.up(1)
        val p=m.peek(0)!!;assertEquals(16,p.held);assertEquals(16,p.attacks)
        m.sent(p,0);m.up(4)
        assertNull(m.peek(15));assertEquals(0,m.peek(16)!!.held)
    }
    @Test fun rateLimitAndLeaseNeverRetriggerAHeldNote() {
        val m=RealtimeNotes();m.down(2,220);val a=m.peek(0)!!;m.sent(a,0)
        m.refresh();assertNull(m.peek(5));val b=m.peek(16)!!
        assertEquals(4,b.held);assertEquals(0,b.attacks)
    }
    @Test fun packetCapabilityAndRoundTrip() {
        val payload=byteArrayOf(2,1,16,0,0,0,0,0,0x81.toByte(),4,128.toByte(),0x80.toByte(),127,0)
        assertTrue(DeviceState.from(payload)!!.realtimeNotes)
        val packet=RealtimeNotePacket(0x45,0x40,190,1)
        val frame=FrameStream().push(Protocol.encodeCommand(Protocol.REALTIME_NOTES,250,packet.payload())).single()
        assertEquals(0x24,frame.type);assertArrayEquals(packet.payload(),frame.payload)
    }
}
