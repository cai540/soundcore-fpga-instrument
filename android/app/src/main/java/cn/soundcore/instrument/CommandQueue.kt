package cn.soundcore.instrument

data class QueuedCommand(val type: Int, val payload: ByteArray = byteArrayOf(),
    val background: Boolean = false)

/** Priority is needed so an audio release cannot sit behind a visual setting. */
class CommandQueue {
    private val items = mutableListOf<QueuedCommand>()

    fun clear() = items.clear()
    fun isEmpty() = items.isEmpty()
    fun contains(type: Int) = items.any { it.type == type }
    fun removeScoreTransfers() = items.removeAll { Protocol.isScoreTransfer(it.type) }
    fun removeOmrTransfers() = items.removeAll { it.type in Protocol.OMR_BEGIN..Protocol.OMR_ABORT }
    fun removeCaptureDisplays() = items.removeAll { it.type==Protocol.CAPTURE_DISPLAY || it.type==Protocol.CAPTURE_STATUS }

    fun offer(command: QueuedCommand) {
        // A periodic poll must not replace an explicit/guide-triggered query.
        if (command.background && items.any { it.type == command.type && !it.background }) return
        when (command.type) {
            Protocol.ALL_NOTES_OFF -> items.removeAll { it.type == Protocol.NOTE_ON ||
                it.type == Protocol.NOTE_OFF || it.type == Protocol.NOTE_LEASE ||
                it.type == Protocol.ALL_NOTES_OFF }
            Protocol.GET_STATE, Protocol.GET_TELEMETRY, Protocol.GET_LAYOUT, Protocol.SET_KEY, Protocol.HEARTBEAT, Protocol.NOTE_LEASE, Protocol.SCORE_STATUS,
            Protocol.CAPTURE_STATUS, Protocol.CAPTURE_DISPLAY ->
                items.removeAll { it.type == command.type }
            // Legacy firmware fallback: release cancels an obsolete unsent
            // attack. A live instrument must not replay a recording of taps.
            Protocol.NOTE_OFF -> items.removeAll { it.type == Protocol.NOTE_LEASE ||
                ((it.type == Protocol.NOTE_ON || it.type == Protocol.NOTE_OFF) &&
                 it.payload.firstOrNull() == command.payload.firstOrNull()) }
            Protocol.NOTE_ON -> items.removeAll { it.type == Protocol.NOTE_ON &&
                it.payload.firstOrNull() == command.payload.firstOrNull() }
            Protocol.RELEASE_BEND -> items.removeAll { it.type == Protocol.SET_BEND }
            Protocol.SET_SCENE -> items.removeAll { it.type in Protocol.SET_VOLUME..Protocol.SET_VIBRATO ||
                it.type == Protocol.SET_VIB_DEPTH || it.type == Protocol.SET_LED_MODE ||
                it.type == Protocol.SET_OLED_CONTRAST || it.type == Protocol.SET_SCENE }
            Protocol.SET_VOLUME, Protocol.SET_TIMBRE,
            Protocol.SET_VIBRATO, Protocol.SET_VIB_DEPTH, Protocol.SET_BEND,
            Protocol.SET_LED_MODE, Protocol.SET_OLED_CONTRAST ->
                items.removeAll { it.type == command.type }
        }
        items += command
    }

    fun take(allowBackground: Boolean = true): QueuedCommand? {
        val index = items.indices.filter { allowBackground || !items[it].background }
            .minByOrNull { priority(items[it].type) } ?: return null
        return items.removeAt(index)
    }

    private fun priority(type: Int) = when (type) {
        Protocol.ALL_NOTES_OFF -> 0
        Protocol.NOTE_OFF -> 1
        Protocol.RELEASE_BEND -> 1
        Protocol.NOTE_LEASE -> 2
        Protocol.HEARTBEAT -> 3
        // Keep a bank change in FIFO order with the notes around it; giving
        // it higher priority retuned earlier queued attacks by mistake.
        Protocol.SET_BANK -> 4
        // Kotlin minByOrNull returns the first matching item, preserving
        // NOTE_ON / NOTE_OFF order across rapidly touched pads.
        Protocol.NOTE_ON -> 4
        Protocol.GET_TELEMETRY -> 6
        Protocol.GET_STATE -> 7
        Protocol.CAPTURE_STATUS, Protocol.CAPTURE_DISPLAY -> 8
        else -> 5
    }
}
