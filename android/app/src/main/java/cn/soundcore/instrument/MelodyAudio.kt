package cn.soundcore.instrument

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.*
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.*

data class MelodyView(val recording:Boolean=false,val busy:Boolean=false,
    val progress:Int=0,val seconds:Int=0,val previewing:Boolean=false,
    val message:String="录一段独唱或独奏，让设备接着演奏",val score:MelodyScore?=null,
    val transpose:Int=0,val timbre:Int=1,val inputMode:MelodyInput=MelodyInput.VOCAL,
    val algorithmVersion:Int=BuiltinMelodyRecognition.VERSION,val sourceDurationMs:Int=0,val sourceName:String="",
    val range:MelodyRange?=null,val scoreRange:MelodyRange?=null,
    val positionMs:Int=0,val originalPreview:Boolean=false,val level:Int=0,
    val selectedNote:Int=-1,val undoAvailable:Boolean=false,val edited:Boolean=false,
    val localRecognition:Boolean=false,val readingSource:Boolean=false,val waveform:List<Float> = emptyList(),
    val engine:RecognitionEngine=RecognitionEngine.LOCAL,val apiConfigured:Boolean=false,val apiUrl:String="",
    val apiTesting:Boolean=false,val apiReady:Boolean=false,val apiStatus:String="内置模型 · 无需联网",
    val scoreOrigin:String="local",val scoreAlgorithm:String=BuiltinMelodyRecognition.ALGORITHM) {
    val canUpload get()=score!=null && scoreRange!=null && !busy && !recording
    val hasSource get()=sourceDurationMs>0
}

/** Audio and revisions stay local. Worker results are generation-checked. */
class MelodyAudio(private val context:Context,private val storagePrefix:String="",private val onChange:(MelodyView)->Unit) {
    private val main=Handler(Looper.getMainLooper())
    private val worker=Executors.newSingleThreadExecutor()
    private val pitchObserver=CrepePitchObserver{context.assets.open("models/crepe_tiny.onnx").use{it.readBytes()}}
    private val cancelled=AtomicBoolean(false);private val stopRecording=AtomicBoolean(false)
    @Volatile private var generation=0
    @Volatile private var recorder:AudioRecord?=null
    @Volatile private var track:AudioTrack?=null
    private var source=FloatArray(0);private var savedSourceId="";private var persistedPcm:FloatArray?=null
    private var nativeSource=NativeMelodyPcm(source,16000)
    private var persistedNative:NativeMelodyPcm?=null;private var nativeSourceId=""
    private data class Take(val view:MelodyView,val pcm:FloatArray,val native:NativeMelodyPcm,val history:List<MelodyRevision>)
    private var previousTake:Take?=null
    private val history=ArrayDeque<MelodyRevision>()
    var view=MelodyView();private set
    private fun stored(name:String)=File(context.filesDir,storagePrefix+name)
    private val savedFile get()=stored("last_melody_v1.json")
    private val pcmFile get()=stored("last_melody_source_v2.f32")
    private val nativeFile get()=stored("last_melody_native_v1.f32")
    init { load() }
    private fun update(v:MelodyView){view=v;onChange(v)}
    private fun deliver(token:Int,action:()->Unit){main.post{if(generation==token && !worker.isShutdown)action()}}
    private fun isCancelled(token:Int)=cancelled.get() || generation!=token
    private val idle get()=!view.busy && !view.recording && !view.previewing
    fun setTranspose(value:Int){if(idle){update(view.copy(transpose=value));save()}}
    fun setTimbre(value:Int){if(idle && value in 0..1){update(view.copy(timbre=value));save()}}
    fun setInputMode(value:MelodyInput){if(idle){
        update(view.copy(inputMode=value,engine=RecognitionEngine.LOCAL,message="内置模型在手机识别，无需联网"))}}
    fun setRange(startMs:Int,endMs:Int){if(!idle || source.isEmpty())return
        runCatching{MelodyRange(startMs,endMs).also{require(it.endMs<=view.sourceDurationMs)}}.onSuccess{
            update(view.copy(range=it,positionMs=it.startMs,message="已选片段，可听原声或识别；局部重识别保留其余音符"))}}
    fun seek(timeMs:Int){if(!idle)return;val range=view.range?:return
        val p=timeMs.coerceIn(range.startMs,range.endMs)
        update(view.copy(positionMs=p,selectedNote=view.score?.let{MelodyWorkspace.nearest(it,p)}?:-1))}
    fun selectNote(index:Int){if(!idle)return;val n=view.score?.notes?.getOrNull(index)?:return
        update(view.copy(selectedNote=index,positionMs=n.startMs))}
    private fun revise(action:(MelodyScore)->MelodyScore){if(!idle)return;val old=view.score?:return
        try{val next=action(old);history.addLast(MelodyRevision(old,view.transpose,view.scoreRange,view.edited,view.scoreOrigin,view.scoreAlgorithm));if(history.size>20)history.removeFirst()
            update(view.copy(score=next,undoAvailable=true,edited=true,selectedNote=view.selectedNote.coerceIn(next.notes.indices),
                message="已修正 · 可对照试听，撤销可恢复上一步"));save()
        }catch(e:Exception){update(view.copy(message=e.message?:"修改超出音符范围"))}}
    fun edit(semitones:Int=0,durationDelta:Int=0,onsetDelta:Int=0)=revise{
        MelodyWorkspace.edit(it,view.selectedNote,semitones,durationDelta,onsetDelta)}
    fun split()=revise{val n=it.notes[view.selectedNote]
        val at=if(view.positionMs-n.startMs>=60 && n.startMs+n.durationMs-view.positionMs>=60)view.positionMs else n.startMs+n.durationMs/2
        MelodyWorkspace.split(it,view.selectedNote,at)}
    fun merge()=revise{MelodyWorkspace.merge(it,view.selectedNote)}
    fun delete()=revise{MelodyWorkspace.delete(it,view.selectedNote)}
    fun undo(){if(!idle || history.isEmpty())return;val revision=history.removeLast();val score=revision.score
        update(view.copy(score=score,transpose=revision.transpose,scoreRange=revision.range,
            selectedNote=view.selectedNote.coerceIn(score.notes.indices),undoAvailable=history.isNotEmpty(),
            edited=revision.edited,scoreOrigin=revision.origin,scoreAlgorithm=revision.algorithm,message="已撤销上一步"));save()}
    private fun remember(){if(view.score!=null)previousTake=Take(view.copy(previewing=false),source,nativeSource,history.toList())}
    fun cancelRecognition(){if(!view.busy)return;cancelled.set(true);generation++
        val prior=previousTake
        if(!view.localRecognition && prior!=null){source=prior.pcm;nativeSource=prior.native;history.clear();history.addAll(prior.history)
            update(prior.view.copy(busy=false,recording=false,previewing=false,apiUrl=view.apiUrl,apiConfigured=view.apiConfigured,
                apiStatus=view.apiStatus,apiReady=view.apiReady,apiTesting=view.apiTesting,engine=view.engine,message="已取消，保留上次旋律"))}
        else update(view.copy(busy=false,recording=false,localRecognition=false,readingSource=false,message="已取消识别，原旋律保留"))}
    fun record(){if(view.busy || view.recording)return
        if(context.checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){update(view.copy(message="需要麦克风权限才能录音"));return}
        stopPreview();remember();cancelled.set(false);stopRecording.set(false);val token=++generation
        val preferNative=false
        update(view.copy(recording=true,seconds=0,level=0,message="对着手机清晰独唱或哼唱，最长3分钟"))
        worker.execute{try{if(isCancelled(token))return@execute
            val rate=if(preferNative && AudioRecord.getMinBufferSize(44100,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT)>0)44100 else 16000
            val size=AudioRecord.getMinBufferSize(rate,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT)
            require(size>0){"设备不支持此录音格式"}
            @Suppress("MissingPermission")
            val audio=AudioRecord(MediaRecorder.AudioSource.MIC,rate,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,maxOf(size,4096));recorder=audio
            try{require(audio.state==AudioRecord.STATE_INITIALIZED){"麦克风初始化失败"};audio.startRecording()
                val pcm=FloatArray(rate*180);val buffer=ShortArray(1024);var used=0;var last=-1
                while(!stopRecording.get() && !isCancelled(token) && used<pcm.size){
                    val n=audio.read(buffer,0,min(buffer.size,pcm.size-used),AudioRecord.READ_BLOCKING);require(n>0){"麦克风读取失败"}
                    var power=0.0;var peak=0f
                    for(i in 0 until n){val v=buffer[i]/32768f;pcm[used+i]=v;power+=v*v;peak=max(peak,abs(v))};used+=n
                    if(used/(rate/4)!=last){last=used/(rate/4);val sec=used/rate
                        val level=if(peak>.98f)255 else (sqrt(power/n)*800).toInt().coerceIn(0,240)
                        deliver(token){update(view.copy(seconds=sec,level=level))}}}
                audio.stop();if(!isCancelled(token)){require(used>=rate/4){"录音太短，请再录一段"}
                    val native=NativeMelodyPcm(pcm.copyOf(used),rate);val localPcm=native.local16k()
                    deliver(token){acceptSource(localPcm,"手机录音",native)}}
            }finally{recorder=null;audio.release()}
        }catch(e:Exception){deliver(token){update(view.copy(recording=false,busy=false,message="录音未完成：${e.message}"))}}}}
    fun finishRecording(){stopRecording.set(true)}
    private fun waveform(pcm:FloatArray):List<Float> {
        if(pcm.isEmpty())return emptyList()
        val bins=FloatArray(128);pcm.forEachIndexed{i,v->val k=(i.toLong()*128/pcm.size).toInt().coerceAtMost(127);bins[k]=max(bins[k],abs(v))}
        val peak=(bins.maxOrNull()?:1f).coerceAtLeast(.001f);return bins.map{it/peak}
    }
    private fun acceptSource(pcm:FloatArray,name:String,native:NativeMelodyPcm=NativeMelodyPcm(pcm,16000)){require(pcm.size>=4000){"录音太短，请再录一段"}
        val duration=min(pcm.size/16,(native.samples.size.toLong()*1000/native.rate).toInt());require(duration>=250)
        source=pcm;nativeSource=native;history.clear()
        update(view.copy(recording=false,busy=false,readingSource=false,progress=0,score=null,scoreRange=null,sourceDurationMs=duration,sourceName=name,
            range=MelodyRange(0,min(180000,duration)),positionMs=0,selectedNote=-1,undoAvailable=false,edited=false,level=0,waveform=waveform(pcm),
            message="音频已就绪 · 可回放原声，再识别旋律"));save()}
    fun acceptSheet(score:MelodyScore,name:String):Boolean {if(!idle)return false
        val checked=MelodyWorkspace.validated(score);source=FloatArray(0);nativeSource=NativeMelodyPcm(source,16000);history.clear()
        update(view.copy(score=checked,sourceDurationMs=0,sourceName=name,waveform=emptyList(),
            range=MelodyRange(0,checked.sourceDurationMs),scoreRange=MelodyRange(0,checked.sourceDurationMs),
            transpose=checked.suggestedTranspose?:0,selectedNote=0,positionMs=0,undoAvailable=false,edited=false,
            scoreOrigin="sheet",scoreAlgorithm="builtin-sheet-v1",message="曲谱已载入 · 可逐音修正、试听或传入设备"));save();return true}
    fun import(uri:Uri){if(view.busy || view.recording)return
        stopPreview();remember();cancelled.set(false);val token=++generation
        update(view.copy(busy=true,readingSource=true,progress=0,message="读取音频中…"))
        worker.execute{try{
            val name=runCatching{context.contentResolver.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{
                if(it.moveToFirst())it.getString(0) else "选择的音频"}}.getOrNull()?:"选择的音频"
            val decoded=decode(uri,token);require(decoded.first.size>=4000 && decoded.second.samples.size.toLong()*1000/decoded.second.rate>=250){"音频太短，请换一段"}
            deliver(token){acceptSource(decoded.first,name,decoded.second)}
        }catch(e:Exception){deliver(token){update(view.copy(busy=false,readingSource=false,message="读取失败：${e.message}"))}}}}
    fun recognize(local:Boolean=false){if(!idle || view.apiTesting || source.isEmpty())return;val range=view.range?:return;val old=view.score
        if(local && (old==null || view.scoreRange==null))return
        if(local && (range.startMs<view.scoreRange!!.startMs || range.endMs>view.scoreRange!!.endMs)){
            update(view.copy(message="局部范围需在已识别片段内；新片段请用整段识别"));return}
        val pcm=range.samples(source,16000);val duration=view.sourceDurationMs;val mode=view.inputMode
        if(old!=null)remember()
        cancelled.set(false);val token=++generation
        update(view.copy(busy=true,readingSource=false,progress=0,localRecognition=local,message=if(local)"正在重新识别所选片段…" else "正在辨认音高与节奏…"))
        worker.execute{try{
            if(isCancelled(token))return@execute
            val recognition=BuiltinMelodyRecognition.recognize(pcm,pitchObserver,mode,
                {p,phase->deliver(token){update(view.copy(progress=p,message=phase))}},{isCancelled(token)}) to BuiltinMelodyRecognition.ALGORITHM
            val found=recognition.first
            val next=if(local)MelodyWorkspace.replace(old!!,range,found) else MelodyWorkspace.absolute(found,range.startMs,duration)
            deliver(token){if(local && old!=null){history.addLast(MelodyRevision(old,view.transpose,view.scoreRange,view.edited,view.scoreOrigin,view.scoreAlgorithm));if(history.size>20)history.removeFirst()}else history.clear()
                update(view.copy(busy=false,localRecognition=false,score=next,progress=100,
                    engine=RecognitionEngine.LOCAL,apiReady=false,apiStatus="内置模型 · 无需联网",
                    scoreOrigin=if(local && view.scoreOrigin!="local")"mixed" else "local",
                    scoreAlgorithm=if(local && view.scoreAlgorithm!=recognition.second)"mixed" else recognition.second,
                    algorithmVersion=if(local && view.algorithmVersion!=BuiltinMelodyRecognition.VERSION)
                        view.algorithmVersion else BuiltinMelodyRecognition.VERSION,scoreRange=if(local)view.scoreRange else range,
                    transpose=if(local && runCatching{next.events(view.transpose)}.isSuccess)view.transpose else next.suggestedTranspose?:0,
                    selectedNote=0,positionMs=next.firstMs,undoAvailable=history.isNotEmpty(),edited=local,
                    message=if(next.suggestedTranspose==null)"跨度超过35音，可修正或换选片段" else "识别完成 · 可对照原声，点音符逐个核对"));save()}
        }catch(e:Throwable){
            if(e !is Exception && e !is OutOfMemoryError && e !is LinkageError)throw e
            val message=when(e){is OutOfMemoryError->"手机内存不足，可选择较短片段重试";is LinkageError->"本机无法载入音高模型，请安装配套完整APK";else->creationError(e as Exception)}
            deliver(token){update(view.copy(busy=false,localRecognition=false,message="$message；原结果保留"))}
        }}}
    fun preview(original:Boolean=false){if(view.previewing){stopPreview();return};if(!idle)return
        val range=view.range?:view.scoreRange?:return
        val samples=try{if(original){require(source.isNotEmpty()){"原音未保存，请重新选择音频"}
                val clip=range.samples(source,16000);ShortArray(clip.size){(clip[it].coerceIn(-1f,1f)*28000).toInt().toShort()}}
            else MelodyWorkspace.preview(view.score?:return,view.transpose,range)
        }catch(e:Exception){update(view.copy(message=e.message?:"此片段无法试听"));return}
        cancelled.set(false);val token=++generation
        update(view.copy(previewing=true,originalPreview=original,positionMs=range.startMs,message=if(original)"原声试听 · 同一时间轴" else "旋律试听 · 手机参考音"))
        worker.execute{var audio:AudioTrack?=null;var failed=false
            try{if(isCancelled(token))return@execute
                audio=AudioTrack.Builder().setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
                    .setAudioFormat(AudioFormat.Builder().setSampleRate(16000).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
                    .setTransferMode(AudioTrack.MODE_STREAM).setBufferSizeInBytes(8192).build()
                track=audio;audio.play();var offset=0;var last=-1;var movedAt=System.nanoTime();var head=-1
                while(!isCancelled(token) && audio.playbackHeadPosition<samples.size){
                    if(audio.playbackHeadPosition!=head){head=audio.playbackHeadPosition;movedAt=System.nanoTime()}
                    check(System.nanoTime()-movedAt<5_000_000_000){"音频播放已暂停，请重试"}
                    if(offset<samples.size){val n=audio.write(samples,offset,min(1024,samples.size-offset),AudioTrack.WRITE_NON_BLOCKING);check(n>=0){"无法播放音频"};offset+=n}
                    val pos=(audio.playbackHeadPosition/16).coerceAtMost(range.durationMs)
                    if(pos/60!=last){last=pos/60;deliver(token){update(view.copy(positionMs=range.startMs+pos))}};Thread.sleep(10)}
            }catch(e:Exception){failed=true;deliver(token){update(view.copy(message="试听失败：${e.message}"))}}
            finally{if(track===audio)track=null;audio?.release();deliver(token){update(view.copy(previewing=false,
                positionMs=if(failed)view.positionMs else range.endMs,message=if(failed)view.message else "试听结束"))}}}}
    fun stopPreview(){if(!view.previewing)return;cancelled.set(true);generation++
        try{track?.pause();track?.flush()}catch(_:Exception){};update(view.copy(previewing=false,message="已停止试听"))}
    private fun digest(bytes:ByteArray)=MessageDigest.getInstance("SHA-256").digest(bytes).joinToString(""){"%02x".format(it)}
    fun save(){
        if(worker.isShutdown)return
        val snapshot=view;val pcm=source;val native=nativeSource
        worker.execute{persist(snapshot,pcm,native)}
    }
    private fun persist(view:MelodyView,source:FloatArray,nativeSource:NativeMelodyPcm){if(view.range==null || view.score==null && source.isEmpty())return
        try{val j=MelodySessionJson.encode(view)
            if(source.isNotEmpty() && source!==persistedPcm){
                val bytes=ByteBuffer.allocate(source.size*4).order(ByteOrder.LITTLE_ENDIAN);source.forEach{bytes.putFloat(it)}
                val id=digest(bytes.array())
                if(id!=savedSourceId){val temp=stored("last_melody_source_v2.tmp");temp.writeBytes(bytes.array());check(temp.renameTo(pcmFile));savedSourceId=id}
                persistedPcm=source}
            if(source.isNotEmpty())j.put("source_id",savedSourceId)
            if(nativeSource.samples.isNotEmpty() && nativeSource.samples!==source){
                if(nativeSource!==persistedNative){val bytes=ByteBuffer.allocate(nativeSource.samples.size*4).order(ByteOrder.LITTLE_ENDIAN)
                    nativeSource.samples.forEach{bytes.putFloat(it)};val id=digest(bytes.array())
                    if(id!=nativeSourceId){val temp=stored("last_melody_native_v1.tmp");temp.writeBytes(bytes.array());check(temp.renameTo(nativeFile));nativeSourceId=id}
                    persistedNative=nativeSource}
                j.put("native_source_id",nativeSourceId).put("native_rate",nativeSource.rate)}
            val temp=stored("last_melody_v1.tmp");temp.writeText(j.toString());check(temp.renameTo(savedFile))
        }catch(_:Exception){main.post{if(!worker.isShutdown)update(this.view.copy(message="当前修正保留在页面中，保存失败"))}}}
    private fun load(){try{if(!savedFile.exists())return
        val j=JSONObject(savedFile.readText());val s=MelodySessionJson.score(j)
        val range=if(j.getInt("version")>=2)MelodyRange(j.getInt("range_start"),j.getInt("range_end")) else MelodyRange(s!!.firstMs,max(s.firstMs+250,s.firstMs+s.durationMs))
        if(j.has("source_id") && pcmFile.exists() && pcmFile.length() in 16000L..11520000L){val bytes=pcmFile.readBytes()
            if(digest(bytes)==j.getString("source_id")){val buffer=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
                val candidate=FloatArray(buffer.remaining()/4){buffer.float}
                if(candidate.all{it.isFinite()}){source=candidate;persistedPcm=source;savedSourceId=j.getString("source_id")}}}
        nativeSource=NativeMelodyPcm(source,16000)
        require(s!=null || source.isNotEmpty())
        if(source.isNotEmpty() && j.has("native_source_id") && nativeFile.exists() && nativeFile.length() in 16000L..34560000L){
            runCatching{val bytes=nativeFile.readBytes();require(bytes.size%4==0 && digest(bytes)==j.getString("native_source_id"))
                val b=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);val native=NativeMelodyPcm(FloatArray(b.remaining()/4){b.float},j.getInt("native_rate"))
                require(native.samples.all{it.isFinite()} && abs(native.samples.size.toLong()*16000/native.rate-source.size)<=1)
                nativeSource=native;persistedNative=native;nativeSourceId=j.getString("native_source_id")}}
        view=view.copy(score=s,transpose=j.getInt("transpose"),timbre=j.optInt("timbre",1).coerceIn(0,1),algorithmVersion=j.optInt("algorithm_version",1),
            scoreOrigin=j.optString("score_origin","local"),scoreAlgorithm=j.optString("score_algorithm","local-${j.optInt("algorithm_version",1)}"),
            engine=if(j.optString("input_mode","VOCAL")=="INSTRUMENT")RecognitionEngine.LOCAL else view.engine,
            sourceDurationMs=source.size/16,sourceName=j.optString("source_name","上次旋律"),range=range,scoreRange=if(s==null)null else range,positionMs=range.startMs,waveform=waveform(source),
            selectedNote=if(s==null)-1 else 0,edited=j.optBoolean("edited",false),inputMode=runCatching{MelodyInput.valueOf(j.optString("input_mode","VOCAL"))}.getOrDefault(MelodyInput.VOCAL),
            message=if(s==null)"已恢复上次录音，可回放或识别旋律" else if(source.isEmpty())"已恢复上次曲谱" else "已恢复上次曲谱与原声，可继续核对");onChange(view)
    }catch(_:Exception){}}
    fun suspendAudio(){if(view.recording || view.busy){cancelled.set(true);stopRecording.set(true);generation++
        update(view.copy(recording=false,busy=false,readingSource=false,localRecognition=false,level=0,message="已暂停录音识别，原结果保留"))};stopPreview();save()}
    fun close(){suspendAudio();worker.execute{pitchObserver.close()};worker.shutdown()}

    private fun decode(uri:Uri,token:Int):Pair<FloatArray,NativeMelodyPcm>{
        val extractor=MediaExtractor();var decoder:MediaCodec?=null
        try{extractor.setDataSource(context,uri,null)
            val index=(0 until extractor.trackCount).firstOrNull{extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/")==true}?:error("文件没有音轨")
            extractor.selectTrack(index);val format=extractor.getTrackFormat(index)
            if(format.containsKey(MediaFormat.KEY_DURATION))require(format.getLong(MediaFormat.KEY_DURATION)<=180_100_000){"请选择3分钟以内的音频，可整段识别或裁剪后识别"}
            val codec=MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME)!!);decoder=codec;codec.configure(format,null,null,0);codec.start()
            var rate=format.getInteger(MediaFormat.KEY_SAMPLE_RATE);var channels=format.getInteger(MediaFormat.KEY_CHANNEL_COUNT);var encoding=AudioFormat.ENCODING_PCM_16BIT
            val pcm=FloatArray(16000*180);var used=0;var nativeUsed=0
            var rawPcm:NativePcmBuffer?=null
            val expectedUs=if(format.containsKey(MediaFormat.KEY_DURATION))format.getLong(MediaFormat.KEY_DURATION).coerceIn(250000,180000000) else 40000000L
            var sampler=PcmResampler(rate){require(used<pcm.size){"音频超过3分钟"};pcm[used++]=it}
            var inputDone=false;var outputDone=false;val info=MediaCodec.BufferInfo();var lastOutput=System.nanoTime()
            while(!outputDone && !isCancelled(token)){
                check(System.nanoTime()-lastOutput<15_000_000_000){"解码超时"}
                if(!inputDone){val id=codec.dequeueInputBuffer(10000);if(id>=0){val buffer=codec.getInputBuffer(id)!!;val n=extractor.readSampleData(buffer,0)
                    if(n<0){codec.queueInputBuffer(id,0,0,0,MediaCodec.BUFFER_FLAG_END_OF_STREAM);inputDone=true}
                    else{codec.queueInputBuffer(id,0,n,extractor.sampleTime,0);extractor.advance()}}}
                val id=codec.dequeueOutputBuffer(info,10000)
                if(id==MediaCodec.INFO_OUTPUT_FORMAT_CHANGED){val out=codec.outputFormat;val newRate=out.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                    require(nativeUsed==0 || rate==newRate){"音频中途改变采样率"};rate=newRate;channels=out.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                    encoding=if(out.containsKey(MediaFormat.KEY_PCM_ENCODING))out.getInteger(MediaFormat.KEY_PCM_ENCODING) else AudioFormat.ENCODING_PCM_16BIT
                    require(rate in 8000..192000 && channels in 1..8 && encoding in listOf(AudioFormat.ENCODING_PCM_16BIT,AudioFormat.ENCODING_PCM_FLOAT))
                    if(nativeUsed==0)sampler=PcmResampler(rate){require(used<pcm.size){"音频超过3分钟"};pcm[used++]=it}
                }else if(id>=0){lastOutput=System.nanoTime();require(rate in 8000..192000 && channels in 1..8)
                    val buffer=codec.getOutputBuffer(id)!!.order(ByteOrder.LITTLE_ENDIAN);buffer.position(info.offset);buffer.limit(info.offset+info.size)
                    val width=if(encoding==AudioFormat.ENCODING_PCM_FLOAT)4 else 2
                    if(nativeUsed==0 && rawPcm==null && rate in listOf(22050,24000,32000,44100,48000))
                        rawPcm=NativePcmBuffer(rate,minOf(rate*180,(expectedUs*rate/1000000+rate/4).toInt()))
                    while(buffer.remaining()>=channels*width){var sum=0f;repeat(channels){sum+=if(width==4)buffer.float else buffer.short/32768f};val sample=sum/channels
                        rawPcm?.push(sample)
                        sampler.push(sample);nativeUsed++}
                    outputDone=info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM!=0;codec.releaseOutputBuffer(id,false)}}
            check(!isCancelled(token)){"已取消"};sampler.finish();val local=pcm.copyOf(used)
            return local to (rawPcm?.finish()?:NativeMelodyPcm(local,16000))
        }finally{try{decoder?.stop()}catch(_:Exception){};decoder?.release();extractor.release()}}
}
