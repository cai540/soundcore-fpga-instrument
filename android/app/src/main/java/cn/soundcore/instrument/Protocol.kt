package cn.soundcore.instrument

data class DeviceState(
    val bank: Int,
    val timbre: Int,
    val volume: Int,
    val vibrato: Boolean,
    val uiState: Int,
    val song: Int,
    val step: Int,
    val target: Int,
    val writeAllowed: Boolean,
    val vibratoDepth: Int? = null,
    val bend: Int? = null,
    val ledMode: Int? = null,
    val oledContrast: Int? = null,
    val padMask: Int? = null,
    val effectMask: Int? = null,
    val songExtended: Boolean = false,
    val guideTargetBank: Int = 0,
    val playbackState: Int = 0,
    val realtimeNotes: Boolean = false
) {
    // Native K5 and the App share a transport. Autoplay status takes precedence
    // over the panel's generic run/pause UI bits when identifying guide mode.
    val guideUiState: Int get() = if (playbackState == 0) uiState else 0
    val isPerformanceActive: Boolean get() = guideUiState == 2 || playbackState in 1..2

    companion object {
        fun from(payload: ByteArray): DeviceState? {
            if (payload.size != 9 && payload.size != 14) return null
            val v = payload.map { it.toInt() and 0xff }
            val extendedSong = (v[8] and 0x80) != 0
            val fullStep = v[6] + (if (extendedSong) (v[8] shr 1 and 7) * 256 else 0)
            val targetBank = if (extendedSong) v[8] shr 4 and 7 else 0
            // During song changes the FPGA may report the previous progress once;
            // target 7 means that there is no playable pad at a rest/end marker.
            if (v[0] > 4 || v[1] > 3 || v[2] > 31 || v[3] > 1 || v[4] > 3 ||
                v[5] > 1 || fullStep > (if (extendedSong) 667
                    else (if (v[5] == 0) 7 else 8)) || v[7] > 7 ||
                (!extendedSong && v[8] > 1) || targetBank > 4) return null
            if (v.size == 14 && (v[9] > 15 ||
                v[11] > (if (extendedSong) 0xff else 0x1f) || v[13] > 0x7f)) return null
            return DeviceState(v[0], v[1], v[2], v[3] == 1, v[4], v[5], fullStep,
                v[7], (v[8] and 1) == 1,
                v.getOrNull(9), v.getOrNull(10), v.getOrNull(11)?.and(3),
                v.getOrNull(12), v.getOrNull(13), v.getOrNull(11)?.ushr(2)?.and(7),
                extendedSong, targetBank, if (extendedSong) (v.getOrNull(11) ?: 0) shr 5 and 3 else 0,
                extendedSong && ((v.getOrNull(11) ?: 0) and 0x80) != 0)
        }
    }
}

data class WireFrame(val type: Int, val sequence: Int, val payload: ByteArray)

data class DeviceTelemetry(val pads: List<Int>, val slider: Int, val padMask: Int) {
    companion object {
        fun from(payload: ByteArray): DeviceTelemetry? = if (payload.size == 9 &&
            (payload[8].toInt() and 0x80) == 0)
            DeviceTelemetry(payload.take(7).map { it.toInt() and 0xff },
                payload[7].toInt() and 0xff, payload[8].toInt() and 0x7f) else null
    }
}

object Protocol {
    const val GET_STATE = 0x01
    const val SET_VOLUME = 0x10
    const val SET_BANK = 0x11
    const val SET_TIMBRE = 0x12
    const val SET_VIBRATO = 0x13
    const val SONG_SELECT = 0x14
    const val GUIDE_ACTION = 0x15
    const val NOTE_ON = 0x16
    const val NOTE_OFF = 0x17
    const val ALL_NOTES_OFF = 0x18
    const val HEARTBEAT = 0x19
    const val SET_VIB_DEPTH = 0x1A
    const val SET_BEND = 0x1B
    const val RELEASE_BEND = 0x1C
    const val SET_LED_MODE = 0x1D
    const val SET_OLED_CONTRAST = 0x1E
    const val SET_SCENE = 0x1F
    const val GET_TELEMETRY = 0x20
    const val NOTE_LEASE = 0x21
    const val SET_EFFECTS = 0x22
    const val AUTOPLAY_ACTION = 0x23
    const val REALTIME_NOTES = 0x24
    const val REALTIME_ABSOLUTE = 0x25
    const val GET_LAYOUT = 0x26
    const val SET_KEY = 0x27
    const val SCORE_ABSOLUTE_BEGIN = 0x38
    const val LAYOUT_STATE = 0x84
    fun isScoreTransfer(type:Int?)=type in SCORE_BEGIN..SCORE_COMMIT || type==SCORE_ABSOLUTE_BEGIN
    const val SCORE_STATUS = 0x30
    const val SCORE_BEGIN = 0x31
    const val SCORE_DATA = 0x32
    const val SCORE_COMMIT = 0x33
    const val SCORE_ACTION = 0x34
    const val SCORE_ABORT = 0x35
    const val CAPTURE_STATUS = 0x36
    const val CAPTURE_DISPLAY = 0x37
    const val OMR_BEGIN=0x60
    const val OMR_DATA=0x61
    const val OMR_INFER=0x62
    const val OMR_ABORT=0x63
    const val CAPTURE_STATE = 0x83
    const val SCORE_STATE = 0x82
    const val STATE = 0x80
    const val TELEMETRY = 0x81
    const val ERROR = 0xE0

    fun encodeCommand(type: Int, sequence: Int, payload: ByteArray = byteArrayOf()): ByteArray {
        val v = payload.map { it.toInt() and 0xff }
        val valid = when (type) {
            ToolWire.STATUS,ToolWire.GET_MAP,ToolWire.STOP_RECORD,ToolWire.RECORD_STATUS,ToolWire.CANCEL -> v.isEmpty()
            ToolWire.DIAGNOSE -> v.size==1 && v[0]<=32
            ToolWire.VOICE -> v.size==3 && v[0]<=31 && v[1]<72 && v[2]<=1
            ToolWire.DISPLAY -> v.size==1 && v[0]<=3
            ToolWire.LIVE_SNAPSHOT -> v.size==1 && v[0]<=2
            ToolWire.SNAPSHOT -> v.size==3 && v[0]<=2 && (v[1] or(v[2] shl 8))!=0
            ToolWire.READ_SNAPSHOT,ToolWire.READ_RECORD,ToolWire.READ_RECORD_BULK -> v.size==4 && (v[0] or(v[1] shl 8))!=0
            ToolWire.SET_MAP -> v.size==8 && v[0]<=2 && v.drop(1).all{it<72}
            ToolWire.RECORD -> v.size==2 && (v[0] or(v[1] shl 8))!=0
            GET_STATE, GET_LAYOUT, ALL_NOTES_OFF, HEARTBEAT, RELEASE_BEND, GET_TELEMETRY -> v.isEmpty()
            SET_KEY -> v.size==1 && v[0] in 0..11
            REALTIME_ABSOLUTE -> v.size==10 && v[0]<=127 && v[1]<=127 && v[2] in 1..255 &&
                (0..6).all{v[0] and (1 shl it)==0 || v[3+it] in 0..71}
            SET_VOLUME -> v.size == 1 && v[0] <= 31
            SET_BANK -> v.size == 1 && v[0] <= 4
            SET_TIMBRE -> v.size == 1 && v[0] <= 3
            SET_VIBRATO, SONG_SELECT -> v.size == 1 && v[0] <= 1
            GUIDE_ACTION -> v.size == 1 && v[0] <= 3
            NOTE_ON -> v.size == 2 && v[0] <= 6 && v[1] in 1..255
            NOTE_OFF -> v.size == 1 && v[0] <= 6
            SET_VIB_DEPTH -> v.size == 1 && v[0] <= 15
            SET_BEND, SET_OLED_CONTRAST -> v.size == 1
            SET_LED_MODE -> v.size == 1 && v[0] <= 3
            NOTE_LEASE -> v.size == 1 && v[0] <= 0x7f
            SET_EFFECTS -> v.size == 1 && v[0] <= 7
            AUTOPLAY_ACTION -> v.size == 1 && v[0] <= 3
            REALTIME_NOTES -> v.size == 3 && v[0] <= 0x7f && v[1] <= 0x7f && v[2] in 1..255
            SCORE_STATUS -> v.isEmpty()
            CAPTURE_STATUS -> v.isEmpty()
            CAPTURE_DISPLAY -> v.size==11 && v[0]==1 && v[1]<=8 && v[2]<=100 &&
                (v[3] or (v[4] shl 8))<=1800 && (v[5] or (v[6] shl 8))<=1800 &&
                (v[7] or (v[8] shl 8))<=1023 && (v[9] in 24..108 || v[9]==255)
            SCORE_BEGIN -> v.size == 7 && (v[0] or (v[1] shl 8)) != 0 &&
                (v[2] or (v[3] shl 8)) in 1..512 && v[6] <= 1
            SCORE_ABSOLUTE_BEGIN -> v.size==8 && (v[0] or (v[1] shl 8))!=0 &&
                (v[2] or (v[3] shl 8)) in 1..512 && v[6]<=1 && v[7] in 0..11
            SCORE_DATA -> v.size in listOf(7,10,13) && (v[0] or (v[1] shl 8)) != 0 &&
                (v[2] or (v[3] shl 8)) < 512
            SCORE_COMMIT, SCORE_ABORT -> v.size == 2 && (v[0] or (v[1] shl 8)) != 0
            OMR_BEGIN, OMR_INFER, OMR_ABORT -> v.size==2 && (v[0] or (v[1] shl 8))!=0
            OMR_DATA -> v.size in 4..14 && (v[0] or (v[1] shl 8))!=0 && v[2] in 0..31 && v[2]+v.size-3<=32
            SCORE_ACTION -> v.size == 1 && v[0] <= 4
            SET_SCENE -> v.size == 7 && v[0] <= 4 && v[1] <= 3 && v[2] <= 31 &&
                v[3] <= 1 && v[4] <= 15 && v[5] <= 3
            else -> false
        }
        require(valid) { "Invalid instrument command or payload" }
        return encode(type, sequence, payload)
    }

    fun crc8(bytes: ByteArray): Int {
        var crc = 0
        bytes.forEach { byte ->
            crc = crc xor (byte.toInt() and 0xff)
            repeat(8) { crc = if ((crc and 0x80) != 0) ((crc shl 1) xor 0x07) and 0xff else (crc shl 1) and 0xff }
        }
        return crc
    }

    fun encode(type: Int, sequence: Int, payload: ByteArray = byteArrayOf()): ByteArray {
        require(type in 0..255 && sequence in 0..255 && payload.size <= 14)
        val body = byteArrayOf(1, type.toByte(), sequence.toByte(), payload.size.toByte()) + payload
        return byteArrayOf(0xA5.toByte()) + body + byteArrayOf(crc8(body).toByte())
    }
}

/** BLE notifications are fragments of a UART byte stream, not necessarily whole frames. */
class FrameStream {
    private val pending = ArrayList<Byte>(20)

    fun reset() = pending.clear()

    fun push(fragment: ByteArray): List<WireFrame> {
        val found = mutableListOf<WireFrame>()
        fragment.forEach { pending.add(it) }
        while (pending.isNotEmpty()) {
            if ((pending[0].toInt() and 0xff) != 0xA5) { pending.removeAt(0); continue }
            if (pending.size < 5) break
            val version = pending[1].toInt() and 0xff
            val length = pending[4].toInt() and 0xff
            if (version != 1 || length > (if((pending[2].toInt() and 255)==0x86)128 else 14)) { pending.removeAt(0); continue }
            val size = 6 + length
            if (pending.size < size) break
            val body = pending.subList(1, size - 1).toByteArray()
            val expected = pending[size - 1].toInt() and 0xff
            if (Protocol.crc8(body) != expected) { pending.removeAt(0); continue }
            found += WireFrame(
                pending[2].toInt() and 0xff,
                pending[3].toInt() and 0xff,
                pending.subList(5, 5 + length).toByteArray()
            )
            repeat(size) { pending.removeAt(0) }
        }
        return found
    }
}
