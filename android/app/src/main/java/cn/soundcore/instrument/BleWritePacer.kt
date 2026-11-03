package cn.soundcore.instrument

/** One transport budget for notes, settings and retries through the BLE/UART bridge.
 * A GATT callback is not proof that the module has drained its 9600-baud UART.
 * This keeps only a deadline; the note mailbox keeps the latest finger state.
 */
class BleWritePacer(private val baud: Int = 9600, private val guardMs: Long = 2) {
    private var readyAt = 0L
    private var wireTimeMs = 0L
    private var lastTouch = Long.MIN_VALUE

    init { require(baud > 0 && guardMs >= 0) }

    fun delayMs(now: Long) = (readyAt - now).coerceAtLeast(0)

    fun started(bytes: Int, now: Long) {
        require(bytes > 0)
        // 8N1 = ten bits per byte, rounded UP. Never round a long frame down.
        wireTimeMs = (bytes * 10000L + baud - 1) / baud + guardMs
        readyAt = now + wireTimeMs
    }

    fun completed(now: Long) {
        // UART time is reserved at start. Do not reserve the whole frame twice.
        readyAt = maxOf(readyAt, now + guardMs)
    }

    fun touched(now: Long) { lastTouch = now }
    fun backgroundDelayMs(now: Long, held: Boolean): Long = when {
        held -> 120L
        lastTouch == Long.MIN_VALUE -> 0L
        else -> (lastTouch + 120 - now).coerceAtLeast(0)
    }

    fun reset() { readyAt = 0; wireTimeMs = 0; lastTouch = Long.MIN_VALUE }
}
