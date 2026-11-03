package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test

class CommandQueueTest {
    @Test fun releaseBeatsSettingsAndPolls() {
        val q = CommandQueue()
        q.offer(QueuedCommand(Protocol.GET_STATE))
        q.offer(QueuedCommand(Protocol.SET_VOLUME, byteArrayOf(20)))
        q.offer(QueuedCommand(Protocol.NOTE_OFF, byteArrayOf(2)))
        assertEquals(Protocol.NOTE_OFF, q.take()!!.type)
        assertEquals(Protocol.SET_VOLUME, q.take()!!.type)
    }

    @Test fun emergencyStopDiscardsQueuedAttacksAndLeases() {
        val q = CommandQueue()
        q.offer(QueuedCommand(Protocol.NOTE_ON, byteArrayOf(0, 80)))
        q.offer(QueuedCommand(Protocol.NOTE_LEASE, byteArrayOf(1)))
        q.offer(QueuedCommand(Protocol.ALL_NOTES_OFF))
        assertEquals(Protocol.ALL_NOTES_OFF, q.take()!!.type)
        assertTrue(q.isEmpty())
    }

    @Test fun redundantKeepAliveIsCoalesced() {
        val q = CommandQueue()
        q.offer(QueuedCommand(Protocol.NOTE_LEASE, byteArrayOf(1)))
        q.offer(QueuedCommand(Protocol.NOTE_LEASE, byteArrayOf(3)))
        assertArrayEquals(byteArrayOf(3), q.take()!!.payload)
        assertTrue(q.isEmpty())
    }

    @Test fun releasedUnsentTapCannotPlayLater() {
        val q = CommandQueue()
        q.offer(QueuedCommand(Protocol.NOTE_ON, byteArrayOf(4, 100)))
        q.offer(QueuedCommand(Protocol.NOTE_OFF, byteArrayOf(4)))
        assertEquals(Protocol.NOTE_OFF, q.take()!!.type)
        assertTrue(q.isEmpty())
    }

    @Test fun releasesCancelHistoricalUnsentAttacks() {
        val q = CommandQueue()
        q.offer(QueuedCommand(Protocol.NOTE_ON, byteArrayOf(0, 120)))
        q.offer(QueuedCommand(Protocol.NOTE_ON, byteArrayOf(1, 120)))
        q.offer(QueuedCommand(Protocol.NOTE_OFF, byteArrayOf(0)))
        q.offer(QueuedCommand(Protocol.NOTE_OFF, byteArrayOf(1)))
        assertEquals(0, q.take()!!.payload[0].toInt())
        assertEquals(1, q.take()!!.payload[0].toInt())
        assertTrue(q.isEmpty())
    }

    @Test fun guidedBankChangesStayWithTheirNotes() {
        val q = CommandQueue()
        q.offer(QueuedCommand(Protocol.SET_BANK, byteArrayOf(1)))
        q.offer(QueuedCommand(Protocol.NOTE_ON, byteArrayOf(2, 100)))
        q.offer(QueuedCommand(Protocol.NOTE_OFF, byteArrayOf(2)))
        q.offer(QueuedCommand(Protocol.SET_BANK, byteArrayOf(3)))
        q.offer(QueuedCommand(Protocol.NOTE_ON, byteArrayOf(4, 100)))
        assertEquals(2, q.take()!!.payload[0].toInt())
        assertEquals(1, q.take()!!.payload[0].toInt())
        assertEquals(3, q.take()!!.payload[0].toInt())
        assertEquals(4, q.take()!!.payload[0].toInt())
    }

    @Test fun aThousandTapsDoNotCreateAPlaybackQueue() {
        val q=CommandQueue()
        repeat(1000) { val p=(it%7).toByte()
            q.offer(QueuedCommand(Protocol.NOTE_ON,byteArrayOf(p,120)))
            q.offer(QueuedCommand(Protocol.NOTE_OFF,byteArrayOf(p)))
        }
        var count=0
        while(!q.isEmpty()) { assertEquals(Protocol.NOTE_OFF,q.take()!!.type);count++ }
        assertTrue(count<=7)
    }

    @Test fun bendReleaseDiscardsUnsentDragValues() {
        val q = CommandQueue()
        q.offer(QueuedCommand(Protocol.SET_BEND, byteArrayOf(200.toByte())))
        q.offer(QueuedCommand(Protocol.RELEASE_BEND))
        assertEquals(Protocol.RELEASE_BEND, q.take()!!.type)
        assertTrue(q.isEmpty())
    }
}
