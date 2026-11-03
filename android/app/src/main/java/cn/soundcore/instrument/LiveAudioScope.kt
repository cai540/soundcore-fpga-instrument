package cn.soundcore.instrument

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.*
import android.media.audiofx.*
import android.os.Handler
import android.os.Looper
import android.os.Process
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.max

/** Acquisition, FFT and UI use separate bounded stages. No queue of stale audio frames. */
internal class LiveAudioScope(private val context:Context,private val result:(LiveAudioFrame)->Unit,private val error:(String)->Unit) {
    private val capture=Executors.newSingleThreadExecutor()
    private val analysis=Executors.newSingleThreadExecutor()
    private val analyzing=AtomicBoolean(false)
    private val main=Handler(Looper.getMainLooper())
    @Volatile private var generation=0
    @Volatile private var recorder:AudioRecord?=null
    @Volatile private var highResolution=false
    @Volatile private var paused=false
    private var mailbox:Pair<Int,LiveAudioFrame>?=null
    private var deliveryPending=false
    fun configure(high:Boolean,pause:Boolean){highResolution=high;paused=pause}
    private fun deliver(frame:LiveAudioFrame,token:Int){synchronized(this){
        if(token!=generation)return
        mailbox=token to frame;if(deliveryPending)return;deliveryPending=true
        main.post{val latest=synchronized(this){deliveryPending=false;mailbox.also{mailbox=null}}
            if(latest!=null && latest.first==generation && !paused)result(latest.second)}
    }}
    @Suppress("MissingPermission")
    fun start(){stop();paused=false;val token=generation
        if(context.checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){error("请允许麦克风权限，再开启现场收音");return}
        capture.execute{
            var audio:AudioRecord?=null;val effects=mutableListOf<AudioEffect>()
            try{
                runCatching{Process.setThreadPriority(Process.THREAD_PRIORITY_AUDIO)}
                val manager=context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
                val source=if(manager.getProperty(AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED)=="true")MediaRecorder.AudioSource.UNPROCESSED else MediaRecorder.AudioSource.VOICE_RECOGNITION
                for(rate in listOf(48000,44100,16000)){
                    val minimum=AudioRecord.getMinBufferSize(rate,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT)
                    if(minimum<=0)continue
                    val candidate=runCatching{AudioRecord(source,rate,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,max(minimum,rate/5))}.getOrNull()?:continue
                    if(candidate.state==AudioRecord.STATE_INITIALIZED){audio=candidate;break}else candidate.release()
                }
                val inputAudio=checkNotNull(audio){"无法初始化现场收音"}
                if(token!=generation)return@execute
                recorder=inputAudio
                runCatching{if(AutomaticGainControl.isAvailable())AutomaticGainControl.create(inputAudio.audioSessionId)?.let{it.enabled=false;effects+=it}}
                runCatching{if(NoiseSuppressor.isAvailable())NoiseSuppressor.create(inputAudio.audioSessionId)?.let{it.enabled=false;effects+=it}}
                runCatching{if(AcousticEchoCanceler.isAvailable())AcousticEchoCanceler.create(inputAudio.audioSessionId)?.let{it.enabled=false;effects+=it}}
                inputAudio.startRecording()
                val rate=inputAudio.sampleRate;val input=ShortArray(rate/100)
                val ring=FloatArray(16384);var cursor=0;var filled=0;var frames=0L;var number=0L;var last=0L
                while(token==generation){
                    val count=inputAudio.read(input,0,input.size,AudioRecord.READ_BLOCKING)
                    check(count>0){"现场收音已中断"}
                    repeat(count){ring[cursor]=input[it]/32768f;cursor=(cursor+1)%ring.size};filled=(filled+count).coerceAtMost(ring.size);frames+=count
                    val now=System.nanoTime();val fft=if(highResolution)16384 else 4096
                    if(!paused && filled>=fft && now-last>=33_000_000L && analyzing.compareAndSet(false,true)){
                        last=now;val copy=FloatArray(filled){ring[(cursor-filled+it+ring.size)%ring.size]}
                        val stamp=AudioTimestamp()
                        val reliable=inputAudio.getTimestamp(stamp,AudioTimestamp.TIMEBASE_MONOTONIC)==AudioRecord.SUCCESS
                        val endNs=if(reliable)stamp.nanoTime+((frames-stamp.framePosition)*1_000_000_000L/rate)else now
                        val n=++number
                        analysis.execute{try{if(token==generation && !paused)deliver(ScopeAnalysis.frame(copy,n,rate,endNs,reliable,fft),token)}finally{analyzing.set(false)}}
                    }
                }
            }catch(e:Exception){if(token==generation)main.post{if(token==generation)error(e.message?:"现场收音未能启动")}}
            finally{if(recorder===audio)recorder=null;effects.forEach{it.release()};runCatching{audio?.stop()};audio?.release()}
        }
    }
    fun stop(){generation++;synchronized(this){mailbox=null};runCatching{recorder?.stop()}}
    fun close(){stop();capture.shutdown();analysis.shutdown()}
}
