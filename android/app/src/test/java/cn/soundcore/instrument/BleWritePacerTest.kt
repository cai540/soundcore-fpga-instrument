package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test

class BleWritePacerTest {
    @Test fun nineByteNaturalFrameUsesTwelveMsAndExactFrameUsesNineteen() {
        val p=BleWritePacer()
        p.started(9,100);assertEquals(12L,p.delayMs(100));assertEquals(1L,p.delayMs(111))
        assertEquals(0L,p.delayMs(112))
        p.started(16,112);assertEquals(19L,p.delayMs(112));assertEquals(0L,p.delayMs(131))
    }

    @Test fun lateGattCallbackDoesNotReserveTheSameUartFrameTwice() {
        val p=BleWritePacer();p.started(9,0);p.completed(30)
        assertEquals(2L,p.delayMs(30));assertEquals(0L,p.delayMs(32))
    }

    @Test fun allFrameLengthsRoundUpAndNeverUnderrunSerialTime() {
        for(size in 6..20){
            val p=BleWritePacer();p.started(size,0)
            assertTrue(p.delayMs(0)>=size*10000.0/9600+2)
            assertTrue(p.delayMs(0)<size*10000.0/9600+3)
        }
    }

    @Test fun backgroundWaitsForFingerReleaseAndShortQuietWindow() {
        val p=BleWritePacer();assertEquals(0L,p.backgroundDelayMs(0,false))
        p.touched(10);assertEquals(120L,p.backgroundDelayMs(10,false))
        assertEquals(1L,p.backgroundDelayMs(129,false));assertEquals(0L,p.backgroundDelayMs(130,false))
        assertEquals(120L,p.backgroundDelayMs(10000,true))
    }

    @Test fun reconnectClearsOldSerialAndTouchDeadlines() {
        val p=BleWritePacer();p.started(20,100);p.touched(100);p.reset()
        assertEquals(0L,p.delayMs(0));assertEquals(0L,p.backgroundDelayMs(0,false))
    }

    @Test fun freshNoteDoesNotWaitForAnAdditionalSixteenMsTimer() {
        val m=RealtimeNotes(intervalMs=0);val p=BleWritePacer()
        m.down(0,180);val first=m.peek(0)!!;m.sent(first,0);p.started(9,0);p.completed(0)
        m.down(2,180)
        assertEquals(0L,p.delayMs(12));assertEquals(5,m.peek(12)!!.held)
    }

    @Test fun shortUnsentTapDisappearsWhileSerialIsBusy() {
        val m=RealtimeNotes(intervalMs=0);val p=BleWritePacer()
        m.down(0,180);m.sent(m.peek(0)!!,0);p.started(9,0)
        m.down(1,180);m.up(1);m.up(0)
        val release=m.peek(12)!!
        assertEquals(0L,p.delayMs(12));assertEquals(0,release.held);assertEquals(0,release.attacks)
    }

    @Test fun exactHeldOwnersAndReleaseRemainOneCurrentSnapshot() {
        val m=RealtimeNotes(intervalMs=0)
        repeat(7){m.downAbsolute(24+it,180)}
        val chord=m.peek(0)!!;assertEquals(127,chord.held);assertEquals(16,Protocol.encodeCommand(chord.type,1,chord.payload()).size)
        m.sent(chord,0);m.upAbsolute(27)
        val release=m.peek(19)!!;assertEquals(119,release.held);assertEquals(0,release.attacks)
    }

    @Test fun finalExactReleaseUsesNineBytesAndNextExactChordKeepsItsPitch() {
        val m=RealtimeNotes(intervalMs=0);m.downAbsolute(70,180)
        m.sent(m.peek(0)!!,0);m.upAbsolute(70)
        val release=m.peek(19)!!
        val frame=Protocol.encodeCommand(release.type,2,release.payload())
        assertEquals(Protocol.REALTIME_NOTES,release.type);assertEquals(9,frame.size)
        assertEquals(0,FrameStream().push(frame).single().payload[0].toInt())
        m.sent(release,19);m.downAbsolute(71,180)
        val next=m.peek(31)!!
        assertEquals(Protocol.REALTIME_ABSOLUTE,next.type);assertEquals(71,next.pitches!![0])
        assertEquals(1,next.attacks)
    }

    @Test fun thousandRapidTapsCannotBecomeAQueuedSongInEitherLayout() {
        for(exact in listOf(false,true)){
            val m=RealtimeNotes(intervalMs=0);val p=BleWritePacer()
            var busyUntil=-1L;var previousEnd=-1L;var frames=0;var finalRelease=-1L
            for(now in 0L..1060L){
                if(now<1000){
                    val key=(now%7).toInt()
                    if(exact){m.downAbsolute(24+key,180);m.upAbsolute(24+key)}
                    else {m.down(key,180);m.up(key)}
                }
                if(now==1000L)m.release()
                if(busyUntil==now){p.completed(now);busyUntil=-1}
                if(busyUntil<0 && p.delayMs(now)==0L){
                    m.peek(now)?.let { packet ->
                        assertEquals(0,packet.attacks)
                        assertEquals(0,packet.held)
                        val bytes=Protocol.encodeCommand(packet.type,frames and 255,packet.payload()).size
                        assertTrue(now>=previousEnd)
                        previousEnd=now+(bytes*10000L+9599)/9600
                        p.started(bytes,now);m.sent(packet,now);busyUntil=now+3;frames++
                        if(now>=1000)finalRelease=now
                    }
                }
            }
            assertTrue(frames<90);assertTrue(finalRelease in 1000L..1022L)
            assertNull(m.peek(2000))
        }
    }

    @Test fun backgroundCannotDisplaceUrgentGuidanceAndReturnsAfterQuietWindow() {
        val q=CommandQueue();val p=BleWritePacer();p.touched(0)
        q.offer(QueuedCommand(Protocol.GET_STATE,background=true))
        q.offer(QueuedCommand(Protocol.GET_STATE))
        q.offer(QueuedCommand(Protocol.GET_STATE,background=true))
        q.offer(QueuedCommand(Protocol.GET_TELEMETRY,background=true))
        q.offer(QueuedCommand(Protocol.SET_VOLUME,byteArrayOf(18)))
        assertEquals(Protocol.SET_VOLUME,q.take(false)!!.type)
        assertEquals(Protocol.GET_STATE,q.take(false)!!.type)
        assertNull(q.take(false));assertFalse(q.isEmpty())
        assertEquals(0L,p.backgroundDelayMs(120,false))
        assertEquals(Protocol.GET_TELEMETRY,q.take(true)!!.type);assertTrue(q.isEmpty())
    }

    @Test fun repeatedBackgroundTelemetryIsBounded() {
        val q=CommandQueue()
        repeat(1000){q.offer(QueuedCommand(Protocol.GET_TELEMETRY,background=true))}
        assertEquals(Protocol.GET_TELEMETRY,q.take()!!.type);assertTrue(q.isEmpty())
    }
}
