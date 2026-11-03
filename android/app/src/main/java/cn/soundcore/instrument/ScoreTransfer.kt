package cn.soundcore.instrument

data class UploadedScoreState(val flags: Int, val error: Int, val count: Int,
    val step: Int, val pad: Int, val bank: Int, val timbre: Int, val crc: Int, val token: Int,
    val noteIndex:Int?=null,val schema:Int=1) {
    val ready get() = flags and 1 != 0
    val receiving get() = flags and 2 != 0
    val playing get() = flags and 4 != 0
    val paused get() = flags and 8 != 0
    val guiding get() = flags and 16 != 0
    val finished get() = flags and 32 != 0
    companion object {
        fun from(bytes: ByteArray): UploadedScoreState? {
            if (bytes.size != 14) return null
            val b = bytes.map { it.toInt() and 255 }
            if (b[0] !in 1..2 || b[1] > 63 || b[2] > 8 || b[7] > 7 ||
                (if(b[0]==1)b[8]>4 else b[8] !in 0..71 && b[8]!=127) || b[9] > 1) return null
            val count = b[3] or (b[4] shl 8); val step = b[5] or (b[6] shl 8)
            if (count > 1023 || step > 1023) return null
            return UploadedScoreState(b[1],b[2],count,step,b[7],if(b[0]==1)b[8] else PitchLayout.bank(b[8]),b[9],
                b[10] or (b[11] shl 8),b[12] or (b[13] shl 8),if(b[0]==2 && b[8]!=127)b[8] else null,b[0])
        }
    }
}

/** Stop-and-wait score transaction. Advance only after matching FPGA ACKs. */
class ScoreTransfer(events: List<ScoreEvent>, private val timbre: Int, val token: Int,
    private val key:Int=PitchLayout.estimateKey(events)) {
    val count = events.size
    private val bytes = MelodyWire.bytes(events)
    val crc = MelodyWire.crc16(bytes)
    private var sent = 0
    var confirmed = 0; private set
    private var phase = 0
    var done = false; private set
    init { require(count in 1..1023 && timbre in 0..1 && token in 1..65535 && key in 0..11)
        require(events.sumOf { it.durationMs } <= 180000)
        require(events.all{it.note==null || it.durationMs>=20}){"音符时值不能短于20毫秒"} }
    private fun le(value: Int) = byteArrayOf(value.toByte(),(value ushr 8).toByte())
    fun next(): QueuedCommand? = when (phase) {
        0 -> QueuedCommand(Protocol.SCORE_ABSOLUTE_BEGIN, le(token) + le(count) + le(crc) + byteArrayOf(timbre.toByte(),key.toByte()))
        1 -> {
            sent = minOf(3,count - confirmed)
            QueuedCommand(Protocol.SCORE_DATA, le(token) + le(confirmed) +
                bytes.copyOfRange(confirmed * 3, (confirmed + sent) * 3))
        }
        2 -> QueuedCommand(Protocol.SCORE_COMMIT, le(token))
        else -> null
    }
    fun acknowledge(type: Int, state: UploadedScoreState) {
        require(state.error == 0 && state.token == token && state.schema==2) { "设备拒绝传谱或音高版本不匹配" }
        when (phase) {
            0 -> { require(type == Protocol.SCORE_ABSOLUTE_BEGIN && state.receiving && state.count == 0); phase = 1 }
            1 -> { require(type == Protocol.SCORE_DATA && state.receiving && state.count == confirmed + sent)
                confirmed += sent; if (confirmed == count) phase = 2 }
            2 -> { require(type == Protocol.SCORE_COMMIT && state.ready && !state.receiving &&
                    state.count == count && state.crc == crc)
                done = true; phase = 3 }
            else -> error("曲谱事务已结束")
        }
    }
}
