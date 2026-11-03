package cn.soundcore.instrument

/** Wire IDs 0/1 retain their original meaning; 2/3 are handpan articulations. */
object InstrumentTone {
    fun isHandpan(id:Int?)=id==2 || id==3
    fun isMetal(id:Int?)=id==3
    fun name(id:Int)=when(id){0->"二胡";1->"口琴";2->"空灵手碟";3->"金属电音";else->"未知音色"}
    fun style(id:Int)=when(id){2->"空灵";3->"金属";else->name(id)}
    private val intervals=intArrayOf(0,2,4,7,9,12,14)
    fun handpanIndex(bank:Int,pad:Int,key:Int=0):Int {
        require(bank in 0..4 && pad in 0..6 && key in 0..11)
        val root=bank*12+key
        return (if(root>57)root-12 else root)+intervals[pad]
    }
    fun handpanLabels(bank:Int,key:Int)=(0..6).map{PitchLayout.name(36+handpanIndex(bank,it,key))}
}
