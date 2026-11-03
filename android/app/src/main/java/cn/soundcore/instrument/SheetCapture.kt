package cn.soundcore.instrument

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.exifinterface.media.ExifInterface
import android.net.Uri
import android.os.Handler
import android.os.Looper
import org.json.JSONObject
import org.json.JSONArray
import java.io.ByteArrayOutputStream
import java.io.ByteArrayInputStream
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.Executors

enum class SheetRecognitionMode { PHONE, DEVICE }

data class SheetView(val mode:SheetRecognitionMode=SheetRecognitionMode.PHONE,val busy:Boolean=false,val progress:Int=0,val image:Bitmap?=null,
    val music:SheetMusic?=null,val bpm:Int=80,val part:Int=0,val loadedKey:String?=null,
    val message:String="选择清晰曲谱，开始识别",val imageId:String="",val pageCount:Int=0,val pageIndex:Int=0) {
    val parts get()=music?.parts(bpm)?:emptyList()
    val warnings get()=music?.compile(bpm)?.second?:emptyList()
    val selected get()=parts.getOrNull(part)
    val key get()="$imageId:$bpm:$part"
    val loaded get()=loadedKey==key && music!=null
}

/** Bundled phone OCR/model by default, with an explicit FPGA offline option. */
class SheetCapture(private val context:Context,private val ble:BleController,private val onChange:(SheetView)->Unit) {
    private val worker=Executors.newSingleThreadExecutor();private val main=Handler(Looper.getMainLooper())
    private val engine=OfflineSheetEngine(context,ble)
    @Volatile private var generation=0
    private var files=emptyList<File>()
    private val manifest=File(context.filesDir,"sheet_image_session_v2.json")
    var view=SheetView();private set
    private fun update(v:SheetView){view=v;onChange(v)}
    private fun deliver(g:Int,block:()->Unit){main.post{if(g==generation && !worker.isShutdown)block()}}
    init{load()}
    private fun decode(uri:Uri,g:Int):Triple<Bitmap,ByteArray,String>{
        val raw=context.contentResolver.openInputStream(uri)!!.use{input->val b=ByteArrayOutputStream();val bytes=ByteArray(8192)
            while(true){check(g==generation){"已取消"};val n=input.read(bytes);if(n<0)break;require(b.size()+n<=20_000_000){"图片过大，请先截取清晰的小段"};b.write(bytes,0,n)};b.toByteArray()}
        val bounds=BitmapFactory.Options().apply{inJustDecodeBounds=true};BitmapFactory.decodeByteArray(raw,0,raw.size,bounds)
        require(bounds.outWidth in 64..20000 && bounds.outHeight in 64..20000){"图片格式无法读取"}
        val opts=BitmapFactory.Options().apply{inSampleSize=1};while(maxOf(bounds.outWidth,bounds.outHeight)/opts.inSampleSize>2200)opts.inSampleSize*=2
        val decoded=BitmapFactory.decodeByteArray(raw,0,raw.size,opts)?:error("图片无法解码")
        val orientation=runCatching{ExifInterface(ByteArrayInputStream(raw)).getAttributeInt(ExifInterface.TAG_ORIENTATION,ExifInterface.ORIENTATION_NORMAL)}
            .getOrDefault(ExifInterface.ORIENTATION_NORMAL)
        val transform=Matrix().apply{when(orientation){
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL->setScale(-1f,1f)
            ExifInterface.ORIENTATION_ROTATE_180->setRotate(180f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL->setScale(1f,-1f)
            ExifInterface.ORIENTATION_TRANSPOSE->{setRotate(90f);postScale(-1f,1f)}
            ExifInterface.ORIENTATION_ROTATE_90->setRotate(90f)
            ExifInterface.ORIENTATION_TRANSVERSE->{setRotate(270f);postScale(-1f,1f)}
            ExifInterface.ORIENTATION_ROTATE_270->setRotate(270f)
        }}
        val bitmap=if(transform.isIdentity)decoded else Bitmap.createBitmap(decoded,0,0,decoded.width,decoded.height,transform,true)
            .also{if(it!==decoded)decoded.recycle()}
        val bytes=ByteArrayOutputStream().also{bitmap.compress(Bitmap.CompressFormat.JPEG,92,it)}.toByteArray()
        require(bytes.size<=6_000_000){"图片过大，请截取部分小节"}
        val id=MessageDigest.getInstance("SHA-256").digest(bytes).joinToString(""){"%02x".format(it)}

        return Triple(bitmap,bytes,id)

    }
    fun import(uris:List<Uri>){if(view.busy)return
        if(uris.isEmpty() || uris.size>6){update(view.copy(message="请按顺序选择同一首曲谱的1至6页"));return}
        val g=++generation;update(view.copy(busy=true,progress=0,message="读取曲谱图片…"))
        worker.execute{var preview:Bitmap?=null;try{
            val saved=mutableListOf<File>();var total=0
            for(uri in uris){
                val (bitmap,bytes,id)=decode(uri,g)
                try{
                    total+=bytes.size;require(total<=20_000_000){"多页图片合计超过20MB，请分次识别"}
                    saved+=File(context.filesDir,"sheet_image_$id.jpg").also{f->if(!f.exists())f.writeBytes(bytes)}
                    if(preview==null)preview=bitmap
                }finally{if(bitmap!==preview)bitmap.recycle()}
            }
            val image=checkNotNull(preview)
            deliver(g){files=saved;val ids=saved.joinToString(":"){it.name.removePrefix("sheet_image_").removeSuffix(".jpg")}
                update(SheetView(mode=view.mode,image=image,imageId=ids,pageCount=saved.size,message="已选择${saved.size}页 · 可以开始识别"));save()}
        }catch(e:Exception){preview?.recycle();deliver(g){update(view.copy(busy=false,message="读取失败：${e.message}"))}}}
    }
    fun recognize(overrides:JSONObject=JSONObject()){
        if(view.busy || files.isEmpty())return
        if(view.mode==SheetRecognitionMode.DEVICE && !ble.view.connected){update(view.copy(message="请先连接声芯，再使用设备离线识谱"));return}
        val g=++generation;val mode=view.mode;val selectedFiles=files.toList()
        update(view.copy(busy=true,progress=0,message="正在读取本地谱面…"))
        fun finish(result:Result<SheetMusic>){if(g==generation)result.fold({score->
            update(view.copy(busy=false,progress=100,music=score,bpm=score.defaultBpm,part=0,loadedKey=null,message="识谱完成，先听听这一段"));save()
        },{e->update(view.copy(busy=false,message="识谱未完成：${creationError(e as? Exception ?: Exception(e))}"))})}
        try { engine.recognize(selectedFiles,overrides,{p,s->if(g==generation)update(view.copy(progress=p,message=s))},::finish,mode) } catch(e:Exception){finish(Result.failure(e))}
    }
    fun setMode(value:SheetRecognitionMode){if(!view.busy)update(view.copy(mode=value,message=if(value==SheetRecognitionMode.PHONE)"手机内置识谱，不需要联网或连接设备" else "FPGA识谱，需要连接声芯"))}
    fun editSelection(){if(!view.busy)update(view.copy(loadedKey=null))}
    fun changeScore(raw:JSONObject){if(view.busy)return
        try{val music=SheetMusic(raw);music.compile();music.parts(view.bpm);update(view.copy(music=music,loadedKey=null,message="曲谱已修正，请重新载入片段"));save()}
        catch(e:Exception){update(view.copy(message="修正未保存：${e.message}"))}}
    fun setPage(index:Int){if(view.busy || index !in files.indices)return;val g=generation;val f=files[index]
        worker.execute{val image=BitmapFactory.decodeFile(f.path);deliver(g){if(image!=null)update(view.copy(image=image,pageIndex=index))}}}
    fun setBpm(value:Int){if(view.busy)return
        try{view.music?.parts(value);update(view.copy(bpm=value,part=0,loadedKey=null));save()}
        catch(e:Exception){update(view.copy(message=e.message?:"此拍速无法演奏"))}}
    fun setPart(value:Int){if(!view.busy && value in view.parts.indices){update(view.copy(part=value,loadedKey=null));save()}}
    fun use(onScore:(MelodyScore,String)->Boolean){if(view.busy)return;val p=view.selected?:return
        if(onScore(p.score,view.music!!.title+" · "+p.label)){update(view.copy(loadedKey=view.key,message="已准备好，可以试听或演奏"));save()}}
    fun cancel(){if(!view.busy)return;generation++;engine.cancel();update(view.copy(busy=false,message="已取消，原有结果保留"))}
    fun display():CaptureDisplay=if(view.busy)CaptureDisplay(stage=3,progress=view.progress) else CaptureDisplay()
    private fun save(){if(files.isEmpty())return;val snapshot=view;val saved=files.toList();val g=generation
        worker.execute{runCatching{
            val obj=JSONObject().put("images",JSONArray(saved.map{it.name})).put("bpm",snapshot.bpm).put("part",snapshot.part)
            snapshot.music?.let{obj.put("score",it.raw)}
            val tmp=File(context.filesDir,"sheet_image_session_v2.tmp");tmp.writeText(obj.toString());check(tmp.renameTo(manifest))
        }.onFailure{deliver(g){update(view.copy(message="结果仍在页面，本地保存失败"))}}}}
    private fun load(){runCatching{val legacy=File(context.filesDir,"sheet_image_session_v1.json")
        if(!manifest.exists() && !legacy.exists())return
        val obj=JSONObject((if(manifest.exists())manifest else legacy).readText())
        if(!obj.has("images"))obj.put("images",JSONArray(listOf("sheet_image_${obj.getString("image_id")}.jpg")))
        val array=obj.getJSONArray("images");require(array.length() in 1..6)
        val saved=(0 until array.length()).map{val name=array.getString(it);require(name.matches(Regex("sheet_image_[a-f0-9]{64}\\.jpg")))
            File(context.filesDir,name).also{f->require(f.length() in 1..6_000_000)
                val hash=MessageDigest.getInstance("SHA-256").digest(f.readBytes()).joinToString(""){b->"%02x".format(b)}
                require(name=="sheet_image_$hash.jpg")}}
        val image=BitmapFactory.decodeFile(saved[0].path)?:error("图片无法读取")
        val music=obj.optJSONObject("score")?.let{SheetMusic(it).also{m->m.compile();m.parts()}}
        val bpm=obj.optInt("bpm",music?.defaultBpm?:80).coerceIn(30,240)
        files=saved;view=SheetView(image=image,imageId=saved.joinToString(":"){it.name},pageCount=saved.size,music=music,bpm=bpm,
            part=obj.optInt("part",0).coerceIn(0,maxOf(0,(music?.parts(bpm)?.size?:0)-1)),message="已恢复上次曲谱；可重新识别或载入片段");onChange(view)
    }}
    fun close(){cancel();engine.close();worker.shutdown()}
}
