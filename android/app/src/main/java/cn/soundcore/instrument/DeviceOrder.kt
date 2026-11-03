package cn.soundcore.instrument

/** Prefer the instrument's JDY radio over unrelated nearby BLE devices. */
internal fun orderedDevices(devices: List<FoundDevice>): List<FoundDevice> =
    devices.distinctBy { it.address }.sortedByDescending {
        it.name.trim().startsWith("JDY", ignoreCase = true)
    }.take(5)
