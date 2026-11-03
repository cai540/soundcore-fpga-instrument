package cn.soundcore.instrument

import org.junit.Assert.assertEquals
import org.junit.Test

class DeviceOrderTest {
    @Test fun jdyRadiosComeFirstAndOtherDevicesRemainDeterministic() {
        val devices = listOf(
            FoundDevice("耳机", "C"), FoundDevice("jdy-23", "B"),
            FoundDevice("温湿度计", "D"), FoundDevice("JDY-08", "A")
        )
        assertEquals(listOf("B", "A", "C", "D"),
            orderedDevices(devices).map { it.address })
    }
}
