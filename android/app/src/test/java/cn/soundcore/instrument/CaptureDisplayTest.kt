package cn.soundcore.instrument
import org.junit.Assert.*
import org.junit.Test

class CaptureDisplayTest {
    @Test fun progressIsCoalescedAndLeaseRefreshedWithoutFlooding() {
        val q=CaptureDisplayQueue();q.offer(CaptureDisplay(stage=3,progress=10))
        assertEquals(10,q.take(0)!!.progress)
        repeat(100){q.offer(CaptureDisplay(stage=3,progress=it))}
        assertNull(q.take(499));assertEquals(99,q.take(500)!!.progress)
        assertNull(q.take(1500));assertNotNull(q.take(2000))
        q.offer(CaptureDisplay());assertEquals(0,q.take(2500)!!.stage);assertNull(q.take(10000))
    }
    @Test fun packetCarriesSourcePositionAndNoAudio() {
        val p=CaptureDisplay(7,100,1200,1800,512,94,255).payload()
        assertEquals(11,p.size);assertEquals(17,Protocol.encodeCommand(Protocol.CAPTURE_DISPLAY,1,p).size)
        assertTrue(runCatching{Protocol.encodeCommand(Protocol.CAPTURE_DISPLAY,1,p.copyOf().also{it[1]=9})}.isFailure)
    }
    @Test fun invisibleScreenCannotHoldOverlay() {
        val v=MelodyView(recording=true,seconds=12,level=60)
        assertEquals(0,CaptureDisplay.from(v,false).stage)
        assertEquals(120,CaptureDisplay.from(v,true).position)
    }
    @Test fun displayIsLowerPriorityThanNoteAndScoreTransaction() {
        val q=CommandQueue()
        q.offer(QueuedCommand(Protocol.CAPTURE_DISPLAY,CaptureDisplay(stage=1).payload()))
        q.offer(QueuedCommand(Protocol.SCORE_DATA,byteArrayOf()))
        q.offer(QueuedCommand(Protocol.NOTE_OFF,byteArrayOf(1)))
        assertEquals(Protocol.NOTE_OFF,q.take()!!.type)
        assertEquals(Protocol.SCORE_DATA,q.take()!!.type)
        assertEquals(Protocol.CAPTURE_DISPLAY,q.take()!!.type)
    }
    @Test fun resamplerBoundsNativeRateMemoryAndFiniteValues() {
        var count=0;val r=PcmResampler(48000){assertTrue(it.isFinite());count++}
        repeat(48000){r.push(kotlin.math.sin(it*.03).toFloat())}
        r.finish()
        assertEquals(16000,count)
        assertTrue(runCatching{r.push(Float.NaN)}.isFailure)
    }
}
