package cn.soundcore.instrument

/** One glyph transaction. DATA is intentionally never retried in place. */
class OmrTransfer(val id:Int,bitmap:ByteArray) {
    companion object {const val MODEL_CRC=3866258960L}
    private val identity=byteArrayOf(id.toByte(),(id shr 8).toByte())
    private val commands=listOf(QueuedCommand(Protocol.OMR_BEGIN,identity))+
        (0 until 32 step 11).map{offset->QueuedCommand(Protocol.OMR_DATA,identity+offset.toByte()+bitmap.copyOfRange(offset,minOf(32,offset+11)))}+
        QueuedCommand(Protocol.OMR_INFER,identity)
    private var at=0
    var result:OmrResult?=null;private set
    init{require(id in 1..65535 && bitmap.size==32)}
    fun next()=commands.getOrNull(at)
    fun acknowledge(frame:WireFrame){
        require(frame.type==Protocol.ERROR && frame.payload.size==14){"当前固件不支持FPGA识谱，请使用含识谱核的固件"}
        val v=frame.payload.map{it.toInt() and 255}
        fun u32(start:Int)=(0..3).fold(0L){acc,i->acc or (v[start+i].toLong() shl (i*8))}
        require(v[0]+(v[1] shl 8)==id && v[9]==1 && u32(10)==MODEL_CRC){"FPGA识谱模型或符号标识不一致"}
        val expected=if(at==4)1 else 0
        require(v[2]==expected){"FPGA拒绝识谱数据（${v[2]}），请重新识别"}
        val count=when(at){0->0;1->11;2->22;else->32}
        require(v[8]==count){"FPGA识谱字节数不一致"}
        if(at==4){require(v[3] in 0..10);result=OmrResult(v[3],u32(4))};at++
    }
}
data class OmrResult(val symbolClass:Int,val margin:Long)
