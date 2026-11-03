package cn.soundcore.instrument

data class InstrumentScene(
    val name: String, val bank: Int, val timbre: Int, val volume: Int,
    val vibrato: Boolean, val depth: Int, val ledMode: Int, val contrast: Int,val key:Int=0
) {
    fun payload(): ByteArray {
        val values = listOf(bank, timbre, volume, if (vibrato) 1 else 0,
            depth, ledMode, contrast)
        require(values[0] in 0..4 && values[1] in 0..3 && values[2] in 0..31 &&
            values[4] in 0..15 && values[5] in 0..3 && values[6] in 0..255 && key in 0..11)
        return values.map { it.toByte() }.toByteArray()
    }

    fun matches(state: DeviceState) = state.bank == bank && state.timbre == timbre &&
        state.volume == volume && state.vibrato == vibrato &&
        state.vibratoDepth == depth && state.ledMode == ledMode &&
        state.oledContrast == contrast

    fun storedValue() = "v2,"+listOf(bank, timbre, volume, if (vibrato) 1 else 0,
        depth, ledMode, contrast,key).joinToString(",")

    companion object {
        fun fromState(name: String, state: DeviceState,key:Int=0): InstrumentScene? {
            val depth = state.vibratoDepth ?: return null
            val led = state.ledMode ?: return null
            val contrast = state.oledContrast ?: return null
            return InstrumentScene(name, state.bank, state.timbre, state.volume,
                state.vibrato, depth, led, contrast,key)
        }

        fun fromStored(name: String, text: String?): InstrumentScene? {
            val modern=text?.startsWith("v2,")==true
            val fields=if(modern)text!!.removePrefix("v2,") else text?:return null
            val values=fields.split(',').map{it.toIntOrNull()?:return null}
            if (values.size != (if(modern)8 else 7) || values[0] !in 0..4 || values[3] !in 0..1) return null
            return try {
                InstrumentScene(name,if(modern)values[0] else ((24+values[0]*7)/12).coerceIn(0,4),values[1], values[2], values[3] == 1,
                    values[4], values[5], values[6],if(modern)values[7] else 0).also { it.payload() }
            } catch (_: IllegalArgumentException) { null }
        }

        val presets = listOf(
            InstrumentScene("清亮旋律", 2, 1, 20, false, 4, 0, 180),
            InstrumentScene("温柔长音", 1, 0, 18, true, 5, 3, 120),
            InstrumentScene("舞台演奏", 3, 1, 25, true, 8, 2, 220),
            InstrumentScene("空灵手碟", 1, 2, 16, false, 4, 0, 160),
            InstrumentScene("金属律动", 1, 3, 16, false, 8, 0, 180)
        )
    }
}
