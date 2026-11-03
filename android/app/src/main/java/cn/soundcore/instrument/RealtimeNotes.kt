package cn.soundcore.instrument

data class RealtimeNotePacket(val held: Int, val attacks: Int, val velocity: Int, val revision: Long,
    val pitches:List<Int>?=null) {
    // A zero held mask releases every remote owner in either layout. Send the
    // existing short frame instead of seven unused pitches (9 vs 16 bytes).
    val type get()=if(pitches==null || held==0)Protocol.REALTIME_NOTES else Protocol.REALTIME_ABSOLUTE
    fun payload() = byteArrayOf(held.toByte(), attacks.toByte(), velocity.toByte()) +
        (if(type==Protocol.REALTIME_ABSOLUTE)pitches!!.map{it.toByte()}.toByteArray() else byteArrayOf())
}

/** A bounded current-state mailbox. Released, unsent taps never become a later song. */
class RealtimeNotes(private val intervalMs: Long = 16) {
    var held = 0
        private set
    private var attacks = 0
    private var velocity = 176
    private var dirty = false
    private var revision = 0L
    private var lastSent = -10000L
    private var absolute=false
    private val pitches=IntArray(7)

    fun down(pad: Int, level: Int) {
        require(pad in 0..6)
        if(absolute){release();absolute=false}
        val bit = 1 shl pad
        if (held and bit != 0) return
        held = held or bit; attacks = attacks or bit
        velocity = level.coerceIn(1, 255); dirty = true; revision++
    }
    fun up(pad: Int) {
        require(pad in 0..6)
        if(absolute)return
        val bit = 1 shl pad
        held = held and bit.inv(); attacks = attacks and bit.inv()
        dirty = true; revision++
    }
    fun downAbsolute(index:Int,level:Int) {
        require(index in 0..71)
        if(!absolute){release();absolute=true}
        if((0..6).any{held and (1 shl it)!=0 && pitches[it]==index})return
        val slot=(0..6).firstOrNull{held and (1 shl it)==0}?:return
        pitches[slot]=index;held=held or (1 shl slot);attacks=attacks or (1 shl slot)
        velocity=level.coerceIn(1,255);dirty=true;revision++
    }
    fun upAbsolute(index:Int) {
        if(!absolute)return
        (0..6).filter{held and (1 shl it)!=0 && pitches[it]==index}.forEach {
            held=held and (1 shl it).inv();attacks=attacks and (1 shl it).inv()
        }
        dirty=true;revision++
    }
    fun release() { held = 0; attacks = 0; dirty = true; revision++ }
    fun refresh() { dirty = true; revision++ }
    fun clear() { held = 0; attacks = 0; dirty = false; absolute=false; lastSent = -10000; revision++ }
    fun delayMs(now: Long) = if (dirty) (lastSent + intervalMs - now).coerceAtLeast(0) else null
    fun peek(now: Long): RealtimeNotePacket? =
        if (delayMs(now) == 0L) RealtimeNotePacket(held, attacks and held, velocity, revision,
            if(absolute)pitches.toList() else null) else null
    fun sent(packet: RealtimeNotePacket, now: Long) {
        lastSent = now
        if (packet.revision == revision) { attacks = 0; dirty = false }
    }
}
