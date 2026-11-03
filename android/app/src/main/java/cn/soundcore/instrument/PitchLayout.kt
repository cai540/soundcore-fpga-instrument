package cn.soundcore.instrument

/** One pitch contract shared by natural pads, exact scores and chromatic keys. */
object PitchLayout {
    const val MIDI_MIN=36
    const val MIDI_MAX=107
    const val OCTAVES=5
    val keys=listOf("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")
    private val degrees=intArrayOf(0,2,4,5,7,9,11)
    fun index(bank:Int,pad:Int,key:Int=0):Int {
        require(bank in 0..4 && pad in 0..6 && key in 0..11)
        return bank*12+key+degrees[pad]
    }
    fun midi(bank:Int,pad:Int,key:Int=0)=MIDI_MIN+index(bank,pad,key)
    fun name(midi:Int):String="${keys[Math.floorMod(midi,12)]}${midi/12-1}"
    fun bank(index:Int,key:Int=0)=((index-key).coerceAtLeast(0)/12).coerceIn(0,4)
    fun degree(index:Int,key:Int=0):Int {
        val pc=Math.floorMod(index-key,12)
        return degrees.indexOfLast{it<=pc}
    }
    fun range(bank:Int,key:Int)= "${name(midi(bank,0,key))}—${name(midi(bank,6,key))}"
    /** Display/guidance key only. This never quantizes the source MIDI pitches. */
    fun estimateKey(events:List<ScoreEvent>):Int=(0..11).maxByOrNull { key ->
        events.filter{it.note!=null}.sumOf { e ->
            if(Math.floorMod(e.note!!-key,12) in degrees)e.durationMs.toLong() else 0L
        }
    }?:0
}

data class PitchLayoutState(val key:Int,val features:Int) {
    companion object {
        fun from(bytes:ByteArray):PitchLayoutState? {
            val b=bytes.map{it.toInt() and 255}
            return if(b.size==7 && b[0]==1 && b[1]==2 && b[2]==36 && b[3]==107 &&
                b[4]==5 && b[5] in 0..11 && b[6] and 7==7)PitchLayoutState(b[5],b[6]) else null
        }
    }
}
