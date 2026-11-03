package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test

class InstrumentSceneTest {
    @Test fun scenesEncodeAndMatchAuthoritativeState() {
        InstrumentScene.presets.forEach { scene ->
            val bytes = scene.payload()
            assertEquals(7, bytes.size)
            Protocol.encodeCommand(Protocol.SET_SCENE, 3, bytes)
            val state = DeviceState.from(byteArrayOf(scene.bank.toByte(), scene.timbre.toByte(),
                scene.volume.toByte(), (if (scene.vibrato) 1 else 0).toByte(),
                0, 0, 0, 0, 1, scene.depth.toByte(), 128.toByte(),
                scene.ledMode.toByte(), scene.contrast.toByte(), 0))!!
            assertTrue(scene.matches(state))
            assertFalse(scene.matches(state.copy(volume = scene.volume - 1)))
        }
    }

    @Test fun telemetryRequiresSevenPadsAndSlider() {
        assertNull(DeviceTelemetry.from(byteArrayOf(1, 2)))
        val reading = DeviceTelemetry.from(byteArrayOf(1, 2, 3, 4, 5, 6, 7,
            255.toByte(), 0x55))!!
        assertEquals(7, reading.pads[6])
        assertEquals(255, reading.slider)
        assertEquals(0x55, reading.padMask)
    }

    @Test fun customSceneStorageIsValidated() {
        val scene = InstrumentScene.presets.first()
        assertEquals(scene, InstrumentScene.fromStored(scene.name, scene.storedValue()))
        assertNull(InstrumentScene.fromStored("bad", "0,1,32,0,1,0,127"))
        assertNull(InstrumentScene.fromStored("bad", "0,1,16,0,1,0"))
    }
}
