package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test

class ProtocolTest {
    @Test fun nativePlaybackDoesNotMasqueradeAsGuidance() {
        val guide = DeviceState(0, 1, 6, false, 2, 0, 0, 0, true,
            songExtended = true)
        assertEquals(2, guide.guideUiState)
        assertTrue(guide.isPerformanceActive)
        assertEquals(3, guide.copy(uiState = 3).guideUiState)
        assertFalse(guide.copy(uiState = 3).isPerformanceActive)
        for (playback in 1..3) {
            val demo = guide.copy(uiState = if (playback == 2) 3 else 2,
                playbackState = playback)
            assertEquals(0, demo.guideUiState)
            assertEquals(playback in 1..2, demo.isPerformanceActive)
        }
        val nativeFrame = byteArrayOf(0, 1, 6, 0, 2, 0, 0, 0,
            0x81.toByte(), 4, 128.toByte(), 0x20, 127, 0)
        val decoded = DeviceState.from(nativeFrame)!!
        assertEquals(2, decoded.uiState)
        assertEquals(1, decoded.playbackState)
        assertEquals(0, decoded.guideUiState)
        assertTrue(decoded.isPerformanceActive)
    }

    @Test fun matchesFpgaCrcVector() {
        assertArrayEquals(
            byteArrayOf(0xA5.toByte(), 1, 1, 0x2A, 0, 0x51),
            Protocol.encode(Protocol.GET_STATE, 0x2A)
        )
    }

    @Test fun fragmentedAndGluedFrames() {
        val stream = FrameStream()
        val a = Protocol.encode(Protocol.GET_STATE, 4)
        val b = Protocol.encode(Protocol.SET_VOLUME, 5, byteArrayOf(25))
        assertTrue(stream.push(a.copyOfRange(0, 2)).isEmpty())
        val result = stream.push(a.copyOfRange(2, a.size) + b)
        assertEquals(2, result.size)
        assertEquals(4, result[0].sequence)
        assertEquals(25, result[1].payload[0].toInt())
    }

    @Test fun damagedFrameIsSkipped() {
        val stream = FrameStream()
        val bad = Protocol.encode(Protocol.GET_STATE, 1).also { it[it.lastIndex] = 0 }
        val good = Protocol.encode(Protocol.GET_STATE, 2)
        val result = stream.push(bad + good)
        assertEquals(1, result.size)
        assertEquals(2, result[0].sequence)
    }

    @Test fun decodesAuthoritativeState() {
        val state = DeviceState.from(byteArrayOf(4, 1, 25, 1, 2, 0, 3, 6, 1))!!
        assertEquals(4, state.bank)
        assertTrue(state.writeAllowed)
        assertNull(DeviceState.from(byteArrayOf(5, 1, 25, 1, 2, 0, 3, 6, 1)))
        assertNull(DeviceState.from(byteArrayOf(4, 1, 25, 1, 2, 0, 3, 6, 2)))
        assertNull(DeviceState.from(byteArrayOf(4, 1, 25, 1, 2, 2, 3, 6, 1)))
        assertNotNull(DeviceState.from(byteArrayOf(4, 1, 25, 1, 2, 0, 7, 6, 1)))
        assertNotNull(DeviceState.from(byteArrayOf(4, 1, 25, 1, 2, 1, 8, 6, 1)))
        assertNull(DeviceState.from(byteArrayOf(4, 1, 25, 1, 2, 0, 8, 6, 1)))
    }

    @Test fun decodesFpgaStateVectorIncludingAuthorization() {
        val frame = byteArrayOf(0xA5.toByte(), 1, 0x80.toByte(), 0x21, 9,
            0, 1, 16, 0, 0, 0, 0, 0, 1, 0xCE.toByte())
        val result = FrameStream().push(frame)
        assertEquals(1, result.size)
        assertEquals(0x21, result[0].sequence)
        assertTrue(DeviceState.from(result[0].payload)!!.writeAllowed)
    }

    @Test fun acceptsOnlyOldOrExtendedStateLength() {
        val old = byteArrayOf(0, 1, 16, 0, 0, 0, 0, 0, 1)
        assertNotNull(DeviceState.from(old))
        for (extra in 1..4) assertNull(DeviceState.from(old + ByteArray(extra)))
        val extended = old + byteArrayOf(7, 128.toByte(), 2, 200.toByte(), 0x55)
        val state = DeviceState.from(extended)!!
        assertEquals(7, state.vibratoDepth)
        assertEquals(128, state.bend)
        assertEquals(2, state.ledMode)
        assertEquals(0, state.effectMask)
        assertEquals(200, state.oledContrast)
        assertEquals(0x55, state.padMask)
        assertEquals(5, DeviceState.from(old + byteArrayOf(7, 128.toByte(), 22,
            200.toByte(), 0x55))!!.effectMask)
        assertNull(DeviceState.from(old + byteArrayOf(16, 0, 0, 0, 0)))
        assertNull(DeviceState.from(old + byteArrayOf(0, 0, 32, 0, 0)))
        assertNull(DeviceState.from(old + byteArrayOf(0, 0, 0, 0, 128.toByte())))
    }

    @Test fun longSongStateCarriesBankProgressAndPlayback() {
        // song 0, step 300, target bank 2/pad 4, playback active.
        val payload = byteArrayOf(0, 1, 16, 0, 2, 0, 44, 4,
            0xA3.toByte(), 4, 128.toByte(), 0x20, 127, 0)
        val state = DeviceState.from(payload)!!
        assertEquals(300, state.step)
        assertEquals(2, state.guideTargetBank)
        assertEquals(1, state.playbackState)
        assertEquals(true, state.songExtended)
        assertEquals(true, state.writeAllowed)
    }

    @Test fun acceptsRestMarkerAndTransientProgressDuringSongSwitch() {
        val rest = byteArrayOf(0, 1, 16, 0, 2, 1, 44, 7,
            0x83.toByte(), 4, 128.toByte(), 0, 127, 0)
        assertEquals(300, DeviceState.from(rest)?.step)
        assertEquals(7, DeviceState.from(rest)?.target)
        val endQian = byteArrayOf(0, 1, 16, 0, 2, 1, 155.toByte(), 7,
            0x84.toByte(), 4, 128.toByte(), 0, 127, 0)
        assertEquals(667, DeviceState.from(endQian)?.step)
        val switchingToLanting = endQian.copyOf().also { it[5] = 0 }
        assertEquals(667, DeviceState.from(switchingToLanting)?.step)
        val beyondEnd = endQian.copyOf().also { it[6] = 156.toByte() }
        assertNull(DeviceState.from(beyondEnd))
    }

    @Test fun newCommandsValidatePayloadBeforeEncoding() {
        assertEquals(0x22, Protocol.SET_EFFECTS)
        assertArrayEquals(byteArrayOf(7), FrameStream().push(
            Protocol.encodeCommand(Protocol.SET_EFFECTS, 1, byteArrayOf(7)))[0].payload)
        assertThrows(IllegalArgumentException::class.java) {
            Protocol.encodeCommand(Protocol.SET_EFFECTS, 1, byteArrayOf(8))
        }
        assertEquals(0x16, Protocol.NOTE_ON)
        assertEquals(0x20, Protocol.GET_TELEMETRY)
        assertEquals(0x81, Protocol.TELEMETRY)
        assertArrayEquals(byteArrayOf(6, 255.toByte()),
            FrameStream().push(Protocol.encodeCommand(Protocol.NOTE_ON, 3, byteArrayOf(6, 255.toByte())))[0].payload)
        assertThrows(IllegalArgumentException::class.java) {
            Protocol.encodeCommand(Protocol.NOTE_ON, 3, byteArrayOf(7, 127.toByte()))
        }
        assertThrows(IllegalArgumentException::class.java) {
            Protocol.encodeCommand(Protocol.NOTE_ON, 3, byteArrayOf(0, 0))
        }
        assertThrows(IllegalArgumentException::class.java) {
            Protocol.encodeCommand(Protocol.SET_SCENE, 3, byteArrayOf(0, 1, 32, 0, 7, 0, 128.toByte()))
        }
        assertThrows(IllegalArgumentException::class.java) {
            Protocol.encodeCommand(Protocol.NOTE_OFF, 3, byteArrayOf())
        }
    }
}
