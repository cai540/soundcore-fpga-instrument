package cn.soundcore.instrument

import android.content.Context
import android.content.Intent
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper
import androidx.core.content.FileProvider
import java.io.File

/** One offset-addressed transaction at a time. Retries never create extra notes. */
class ProductToolsController(private val context:Context,private val ble:BleController,private val changed:(ProductToolsView)->Unit) {
    private val main=Handler(Looper.getMainLooper())
    private val prefs=context.getSharedPreferences("soundcore_tools",Context.MODE_PRIVATE)
    var view=ProductToolsView();private set
    private var visible=false;private var serial=0;private var token=System.currentTimeMillis().toInt()and 65535
    private var player:MediaPlayer?=null
    private val liveScope=LiveAudioScope(context,{frame->receiveScope(frame)},
        {message->update(view.copy(liveMic=false,message=message))})
    private val exports=java.util.concurrent.Executors.newSingleThreadExecutor()
    private var lastControl=0L
    private var singleArmedNs=0L
    private fun receiveScope(frame:LiveAudioFrame){
        if(!visible || !view.liveMic || view.scope.state in listOf(1,3))return
        if(view.scope.state==2){
            val window=ScopeMath.window(frame,view.scope)
            if(!window.triggered || ScopeMath.triggerTimeNs(frame,window)<singleArmedNs)return
        }
        val setting=if(view.scope.state==2)view.scope.copy(state=3)else view.scope
        update(view.copy(liveFrame=frame,scope=setting))
        if(setting.state==3)liveScope.configure(setting.highResolution,true)
    }
    private val voiceNotes=IntArray(32){24+it}
    private val voiceGates=BooleanArray(32)
    private var pendingAction:(()->Unit)?=null
    private var plotVisible=true;private var lastPlot=0L;private var monitorEnabled=true
    private fun songActive()=ble.view.state?.let{it.uiState in 2..3 || it.playbackState!=0}==true ||
        ble.view.uploadedScore?.let{(it.playing || it.guiding) && !it.finished}==true
    init { val saved=prefs.getString("map",null)?.split(',')?.mapNotNull{it.toIntOrNull()}
        if(saved?.size==7 && saved.sorted()==(0..6).toList())view=view.copy(mapping=saved) }
    private fun update(v:ProductToolsView){view=v;changed(v)}
    private fun nextToken():Int {token=token%65535+1;return token}
    private fun request(type:Int,data:ByteArray=byteArrayOf(),retry:Int=2,ok:(ByteArray)->Unit) {
        fun failed(error:Throwable){
            if(type==ToolWire.SNAPSHOT && retry>0 && visible && error.message?.contains("正在准备音频分析")==true){
                main.postDelayed({if(visible)request(type,data,retry-1,ok)},50);return
            }
            val unsupported=error.message?.let{it.contains("不支持本次演奏工具") || it.contains("请安装配套固件")}==true
            pendingAction=null // A failed transaction must not replay an old control on the next refresh.
            update(view.copy(busy=false,refreshing=false,reading=false,supported=if(unsupported)false else view.supported,message=error.message?:"连接中断，请重试"))
        }
        ble.requestTool(type,data){result->result.onSuccess{b->runCatching{ok(b)}.onFailure(::failed)}.onFailure(::failed)}
    }
    fun section(value:Int){plotVisible=value==0;if(!plotVisible)microphone(false);if(plotVisible && visible)poll()}
    fun microphone(enabled:Boolean){
        if(enabled==view.liveMic)return
        if(enabled){stopPreview();update(view.copy(liveMic=true,liveFrame=null,scope=view.scope.copy(state=0),message="现场收音中 · 来自手机麦克风"));liveScope.start();liveScope.configure(view.scope.highResolution,false)}
        else {liveScope.stop();update(view.copy(liveMic=false));if(visible && plotVisible)poll()}
    }
    fun microphoneDenied(){update(view.copy(message="未授予麦克风权限；可使用设备输出快照"))}
    fun scope(settings:ScopeSettings){
        if(settings.state==2)singleArmedNs=System.nanoTime()
        update(view.copy(scope=settings));liveScope.configure(settings.highResolution,settings.state in listOf(1,3))
    }
    fun autoScope(){view.liveFrame?.let{scope(ScopeMath.auto(it,view.scope))}}
    fun exportScope(){
        val frame=view.liveFrame?:return;if(view.scopeExporting)return
        update(view.copy(scopeExporting=true))
        exports.execute{
            val result=runCatching{
                val file=File(context.cacheDir,"soundcore-scope-${frame.capturedNs}-${frame.number}.csv")
                file.bufferedWriter().use{out->
                    out.appendLine("# source=phone_microphone; rate_hz=${frame.sampleRate}; fft_size=${frame.fftSize}; frame=${frame.number}; end_monotonic_ns=${frame.capturedNs}; timestamp_reliable=${frame.timestampReliable}; amplitude_unit=FS; spectrum_unit=dBFS; window=Hann")
                    out.appendLine("sample_time_s,amplitude_fs,frequency_hz,spectrum_dbfs")
                    frame.samples.forEachIndexed{i,v->out.appendLine("${(i-frame.samples.lastIndex).toDouble()/frame.sampleRate},$v,"+if(i<frame.spectrum.size)"${i.toDouble()*frame.sampleRate/frame.fftSize},${frame.spectrum[i]}" else ",")}
                };file
            }
            main.post{if(visible){update(view.copy(scopeExporting=false,message=if(result.isSuccess)"已导出当前真实采样与FFT，包含来源和采样率"else "导出失败：${result.exceptionOrNull()?.message}"))
                result.onSuccess{file->val uri=FileProvider.getUriForFile(context,context.packageName+".files",file)
                    context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/csv").putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION),"保存声音数据"))}}}
        }
    }
    fun open(){if(visible)return;visible=true;ble.setToolsVisible(true);lastPlot=0;monitorEnabled=true;update(view.copy(supported=null));poll()}
    fun leave(){liveScope.stop();if(!visible){stopPreview();return};visible=false;ble.setToolsVisible(false);pendingAction=null;serial++;main.removeCallbacksAndMessages(null);stopPreview()
        // In-flight reads finish before the safe exit commands enter the same FIFO.
        if(ble.view.connected){ble.commandBytes(ToolWire.DIAGNOSE,byteArrayOf(0));ble.commandBytes(ToolWire.DISPLAY,byteArrayOf(0))}
        update(view.copy(busy=false,reading=false,liveMic=false))
    }
    private fun poll(){
        main.removeCallbacks(pollTask);if(!visible)return
        if(!view.busy && view.supported!=false && ble.view.connected && ble.view.pitchLayout!=null){
            if(android.os.SystemClock.uptimeMillis()-lastControl<600){/* Interactive commands take precedence over graphical reads. */}
            else if(plotVisible && monitorEnabled && !view.liveMic && view.scope.state !in listOf(1,3))snapshot(view.plotKind)
            else request(ToolWire.STATUS){b->val status=ToolStatus.from(b)
                update(view.copy(supported=true,status=status,mapEnabled=status.customMap))}
        }
        main.postDelayed(pollTask,if(plotVisible && !view.liveMic)220 else 900)
    }
    private val pollTask=Runnable{poll()}
    private fun defer(action:()->Unit):Boolean {
        if(view.refreshing){pendingAction=action;return true};return view.busy
    }
    fun diagnose(n:Int){if(defer{diagnose(n)})return
        if(n>0 && songActive()){update(view.copy(message="请先停止曲目，再开始复音检测"));return}
        lastControl=android.os.SystemClock.uptimeMillis();stopPreview();update(view.copy(busy=true))
        request(ToolWire.DIAGNOSE,byteArrayOf(n.toByte())){
            repeat(32){voiceNotes[it]=24+it;voiceGates[it]=it<n}
            update(view.copy(busy=false,voiceNote=voiceNotes[view.selectedVoice],voiceOn=voiceGates[view.selectedVoice],message=if(n==0)"已退出复音检测" else "已请求 $n 个独立声部，实际数量由设备回报"))}}
    fun selectVoice(slot:Int){val i=slot.coerceIn(0,31);update(view.copy(selectedVoice=i,voiceNote=voiceNotes[i],voiceOn=voiceGates[i]))}
    fun voice(note:Int,on:Boolean,slot:Int=view.selectedVoice){if(defer{voice(note,on,slot)})return
        val target=slot.coerceIn(0,31);val pitch=note.coerceIn(0,71);lastControl=android.os.SystemClock.uptimeMillis();update(view.copy(busy=true))
        request(ToolWire.VOICE,byteArrayOf(target.toByte(),pitch.toByte(),if(on)1 else 0)){
            voiceNotes[target]=pitch;voiceGates[target]=on
            update(view.copy(busy=false,voiceNote=if(view.selectedVoice==target)pitch else view.voiceNote,voiceOn=if(view.selectedVoice==target)on else view.voiceOn,message="声部 ${target+1} 已更新；其他声部保持独立"))}}
    fun editMap(pad:Int,note:Int){if(view.busy || pad !in 0..6 || note !in 0..6)return
        val next=view.mapping.toMutableList();val other=next.indexOf(note)
        if(other>=0)next[other]=next[pad];next[pad]=note;update(view.copy(mapping=next))}
    fun applyMap(enabled:Boolean){if(view.busy)return
        if(songActive()){update(view.copy(message="请先停止曲目，再应用琴键设置"));return}
        update(view.copy(busy=true))
        request(ToolWire.SET_MAP,ToolWire.mapPayload(enabled,view.mapping)){
            request(ToolWire.GET_MAP){b->val notes=(4..10).map{(b[it].toInt()and 255)-120}
                if(enabled && notes.sorted()!=(0..6).toList()){update(view.copy(busy=false,message="琴键设置回读异常"));return@request}
                val order=if(enabled)notes else (0..6).toList()
                prefs.edit().putString("map",order.joinToString(",")).apply();ble.setPadOrder(order)
                update(view.copy(busy=false,mapEnabled=b[3].toInt()==1,mapping=if(enabled)notes else (0..6).toList(),message=if(enabled)"七键排列已保存，音区加减与调号仍共同生效" else "已恢复随音区切换的七个自然音"))}}
    }
    fun snapshot(kind:Int){
        if(view.liveMic){update(view.copy(plotKind=kind));return}
        if(view.busy)return;val run=serial;val began=android.os.SystemClock.uptimeMillis()
        update(view.copy(busy=true,refreshing=true,plotKind=kind));lastPlot=began;monitorEnabled=true
        request(ToolWire.LIVE_SNAPSHOT,byteArrayOf(kind.toByte())){b->
            if(run!=serial)return@request
            val length=b[6].toInt()and 255;require(length==if(kind==1)32 else 64)
            val status=view.status?.copy(active=b[7].toInt()and 255,requested=b[8].toInt()and 255,display=kind+1,flags=b[9].toInt()and 255)
                ?:ToolStatus(b[8].toInt()and 255,b[7].toInt()and 255,kind+1,b[9].toInt()and 255,0,0,0)
            update(view.copy(supported=true,busy=false,refreshing=false,status=status,plot=b.copyOfRange(10,10+length),scope=if(view.scope.state==2)view.scope.copy(state=3)else view.scope,
                plotFrame=ToolWire.u16(b,3),refreshMs=(android.os.SystemClock.uptimeMillis()-began).toInt(),message="设备音频已同步"))
            val action=pendingAction;pendingAction=null;action?.invoke()
        }
    }
    fun record(){if(view.busy)return;stopPreview();val id=nextToken();update(view.copy(busy=true))
        request(ToolWire.RECORD,ToolWire.le(id)){update(view.copy(busy=false,recordingFile=null,message="设备录音已开始，最长8秒；现在可以敲击或播放曲目"))}}
    fun stopRecord(){if(view.busy)return;update(view.copy(busy=true));request(ToolWire.STOP_RECORD){update(view.copy(busy=false,message="已停止录音，等待设备冻结后即可回传"))}}
    fun download(){if(view.busy)return;stopPreview();val run=++serial;update(view.copy(busy=true,reading=true,transferPercent=0))
        request(ToolWire.RECORD_STATUS){b->val status=ToolStatus.from(b)
            if(!status.ready || status.samples==0){update(view.copy(busy=false,reading=false,message="请先完成一段设备录音"));return@request}
            val bytes=ByteArray((status.samples+1)/2)
            fun read(offset:Int){if(run!=serial)return
                request(ToolWire.READ_RECORD_BULK,ToolWire.le(status.token)+ToolWire.le(offset)){r->
                    if(run!=serial)return@request
                    if(ToolWire.u16(r,3)!=offset){update(view.copy(busy=false,reading=false,message="录音偏移校验失败，请重新回传"));return@request}
                    val count=minOf(123,bytes.size-offset);r.copyInto(bytes,offset,5,5+count)
                    update(view.copy(transferPercent=(offset+count)*100/bytes.size))
                    if(offset+count<bytes.size)read(offset+count) else {
                        if(ToolWire.crc16(bytes)!=status.crc){update(view.copy(busy=false,reading=false,message="整段录音校验失败，请重新回传"));return@request}
                        runCatching{val wav=DeviceAudioCodec.wav(DeviceAudioCodec.decode(bytes,status.samples))
                            File(context.cacheDir,"soundcore-device-${status.token}.wav").also{it.writeBytes(wav)}}
                            .onSuccess{update(view.copy(busy=false,reading=false,recordingFile=it.absolutePath,message="设备录音已校验保存 · ${status.samples/8000f}秒"))}
                            .onFailure{update(view.copy(busy=false,reading=false,message="录音保存失败：${it.message}"))}
                    }
                }
            };read(0)
        }
    }
    fun cancelRead(){serial++;update(view.copy(busy=false,reading=false,message="已取消回传；设备录音保留，可重新读取"))}
    fun stopPreview(){player?.release();player=null;if(view.previewing)update(view.copy(previewing=false))}
    fun preview(){if(view.previewing){stopPreview();return};val path=view.recordingFile?:return
        runCatching{MediaPlayer().also{p->player=p;p.setDataSource(path);p.setOnCompletionListener{stopPreview()};p.prepare();p.start()}}
            .onSuccess{update(view.copy(previewing=true))}.onFailure{stopPreview();update(view.copy(message="无法回听：${it.message}"))}}
    fun share(){val file=view.recordingFile?.let(::File)?:return;val uri=FileProvider.getUriForFile(context,context.packageName+".files",file)
        context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("audio/wav").putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION),"保存或分享设备录音"))}
    fun close(){liveScope.close();exports.shutdown();visible=false;ble.setToolsVisible(false);pendingAction=null;serial++;main.removeCallbacksAndMessages(null);stopPreview()}
}
