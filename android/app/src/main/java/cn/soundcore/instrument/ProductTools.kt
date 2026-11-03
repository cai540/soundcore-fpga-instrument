package cn.soundcore.instrument

import java.io.ByteArrayOutputStream

/** A queued request acquires a wire sequence only when that exact item starts. */
class ToolReplyOwner {
    private var command:QueuedCommand?=null
    private var sequence:Int?=null
    fun begin(value:QueuedCommand){check(command==null);command=value;sequence=null}
    fun owns(value:QueuedCommand)=command===value
    fun started(value:QueuedCommand,seq:Int){if(owns(value))sequence=seq}
    fun matches(seq:Int?)=sequence!=null && sequence==seq
    fun clear(){command=null;sequence=null}
}

object ToolWire {
    const val STATUS=0x40;const val DIAGNOSE=0x41;const val VOICE=0x42;const val DISPLAY=0x43
    const val SNAPSHOT=0x44;const val READ_SNAPSHOT=0x45;const val SET_MAP=0x46;const val GET_MAP=0x47
    const val RECORD=0x50;const val STOP_RECORD=0x51;const val RECORD_STATUS=0x52;const val READ_RECORD=0x53;const val CANCEL=0x54;const val READ_RECORD_BULK=0x55
    const val LIVE_SNAPSHOT=0x48
    const val RESPONSE=0x85
    fun contains(type:Int?)=type!=null && type in STATUS..READ_RECORD_BULK
    fun le(value:Int)=byteArrayOf(value.toByte(),(value ushr 8).toByte())
    fun u16(b:ByteArray,at:Int)=(b[at].toInt()and 255)or((b[at+1].toInt()and 255)shl 8)
    fun checked(frame:WireFrame,request:Int):ByteArray {
        if(frame.type==Protocol.ERROR && frame.payload.size==1 && (frame.payload[0].toInt()and 255)!=2)
            error("设备未完成工具请求，请重试（${frame.payload[0].toInt()and 255}）")
        require((frame.type==RESPONSE && frame.payload.size==14) || ((request==READ_RECORD_BULK && frame.payload.size==128 || request==LIVE_SNAPSHOT && frame.payload.size==80) && frame.type==0x86)){"设备不支持本次演奏工具，请安装配套固件"}
        val b=frame.payload;require(b[0].toInt()==1 && (b[1].toInt()and 255)==request){"工具回复版本不匹配"}
        val error=b[2].toInt()and 255
        if(request==LIVE_SNAPSHOT && error==2)error("设备不支持批量图形，请安装配套固件")
        require(error==0){when(error){2->"设备正在执行其他任务";3->"参数超出范围";6->"录音或快照已变化，请重新读取";7->"正在准备音频分析，请稍候";else->"设备未接受操作：$error"}}
        return b
    }
    fun mapPayload(enabled:Boolean,notes:List<Int>):ByteArray {
        require(notes.size==7 && notes.sorted()==(0..6).toList()){"请选择1—7各一次，所有琴键随音区联动"}
        return byteArrayOf(if(enabled)2 else 0)+notes.map{it.toByte()}.toByteArray()
    }
    fun crc16(bytes:ByteArray):Int {
        var crc=65535
        bytes.forEach{v->crc=crc xor((v.toInt()and 255)shl 8);repeat(8){crc=if(crc and 32768!=0)(crc shl 1 xor 0x1021)and 65535 else(crc shl 1)and 65535}}
        return crc
    }
}

data class ToolStatus(val requested:Int,val active:Int,val display:Int,val flags:Int,val samples:Int,val token:Int,val crc:Int) {
    val recording get()=flags and 1!=0
    val ready get()=flags and 2!=0
    val customMap get()=flags and 8!=0
    val analysisReady get()=flags and 32!=0
    val deadlineFault get()=flags and 64!=0
    companion object {
        fun from(b:ByteArray):ToolStatus {
            require(b.size==14)
            val samples=ToolWire.u16(b,7)or((b[9].toInt()and 255)shl 16)
            return ToolStatus(b[3].toInt()and 255,b[4].toInt()and 255,b[5].toInt()and 255,b[6].toInt()and 255,samples,ToolWire.u16(b,10),ToolWire.u16(b,12)).also {
                require(it.requested<=32 && it.active<=32 && it.display<=3 && it.samples<=64000)
            }
        }
    }
}

/** Independent IMA decoder: low nibble first; predictor/index start0/0. */
object DeviceAudioCodec {
    private val steps=intArrayOf(7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,29794,32767)
    private val adjust=intArrayOf(-1,-1,-1,-1,2,4,6,8)
    fun decode(data:ByteArray,samples:Int):ShortArray {
        require(samples in 0..64000 && data.size==(samples+1)/2)
        var predictor=0;var index=0
        return ShortArray(samples){i->
            val code=(data[i/2].toInt() ushr(if(i%2==0)0 else 4))and 15;val step=steps[index]
            var delta=step ushr 3
            if(code and 4!=0)delta+=step;if(code and 2!=0)delta+=step ushr 1;if(code and 1!=0)delta+=step ushr 2
            predictor=(predictor+if(code and 8!=0)-delta else delta).coerceIn(-32768,32767)
            index=(index+adjust[code and 7]).coerceIn(0,88);predictor.toShort()
        }
    }
    fun wav(pcm:ShortArray):ByteArray {
        val out=ByteArrayOutputStream(44+pcm.size*2)
        fun ascii(s:String)=out.write(s.toByteArray(Charsets.US_ASCII))
        fun le(v:Int,n:Int){repeat(n){out.write(v ushr(it*8)and 255)}}
        ascii("RIFF");le(36+pcm.size*2,4);ascii("WAVEfmt ");le(16,4);le(1,2);le(1,2);le(8000,4);le(16000,4);le(2,2);le(16,2)
        ascii("data");le(pcm.size*2,4);pcm.forEach{le(it.toInt(),2)};return out.toByteArray()
    }
}

data class ProductToolsView(
    val supported:Boolean?=null,val busy:Boolean=false,val message:String="连接声芯后，可以查看声音、设置琴键并回听设备录音",
    val status:ToolStatus?=null,val mapping:List<Int> = (0..6).toList(),val mapEnabled:Boolean=false,
    val selectedVoice:Int=0,val voiceNote:Int=24,val voiceOn:Boolean=true,
    val plotKind:Int=0,val plot:ByteArray=byteArrayOf(),val plotFrame:Int=0,
    val refreshing:Boolean=false,val refreshMs:Int=0,
    val liveMic:Boolean=false,val liveFrame:LiveAudioFrame?=null,val scope:ScopeSettings=ScopeSettings(),val scopeExporting:Boolean=false,
    val reading:Boolean=false,val transferPercent:Int=0,val recordingFile:String?=null,val previewing:Boolean=false
)
