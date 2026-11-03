package cn.soundcore.instrument

import android.content.Context
import android.net.Uri
import android.os.Handler
import android.os.Looper
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.Executors

data class LibraryScore(val id:String,val title:String,val credit:String,val json:String,val parts:List<MelodyScore>,val category:String="精选",val composer:String="") { val durationMs get()=parts.sumOf{it.sourceDurationMs} }
/** Non-executable score data. Absolute cumulative tick timing avoids per-note drift. */
object StructuredScore {
    const val MAX_BYTES=262144
    fun parse(text:String):LibraryScore {
        require(text.toByteArray().size<=MAX_BYTES){"曲谱文件过大"}
        val root=JSONObject(text);require(root.getString("schema")=="soundcore.score.v1"){"不是声芯结构化曲谱"}
        val id=root.getString("id");val title=root.getString("title");val bpm=root.getInt("bpm")
        require(id.matches(Regex("[a-zA-Z0-9_-]{1,64}")) && title.length in 1..80 && bpm in 30..240)
        val tonic=root.optInt("tonic",0);require(tonic in 0..11)
        val events=root.getJSONArray("events");require(events.length() in 1..2048)
        var ticks=0L;var partStart=0;var partEnd=0;val notes=mutableListOf<MelodyNote>();val parts=mutableListOf<MelodyScore>()
        fun flush(){if(notes.isNotEmpty()){parts+=MelodyScore(notes.toList(),partEnd-partStart,true,tonic);notes.clear()};partStart=partEnd}
        repeat(events.length()){i->val e=events.getJSONObject(i);val duration=e.getInt("ticks");require(duration in 1..1536)
            val start=(ticks*60000/(bpm*96)).toInt();ticks+=duration
            val end=(ticks*60000/(bpm*96)).toInt();require(end<=600000 && end-start>=20){"音符时值或曲谱长度超出范围"}
            if(end-partStart>180000 || notes.size>=500){flush();partStart=start}
            if(!e.isNull("midi")){val midi=e.getInt("midi");require(midi in 36..107){"音高超出C2—B7"}
                notes+=MelodyNote(start-partStart,end-start,midi,1f)}
            partEnd=end
        }
        flush();require(parts.isNotEmpty()){ "曲谱没有音符" }
        parts.forEach{MelodyWorkspace.validated(it)}
        return LibraryScore(id,title,root.optString("credit","项目编配").take(160),text,parts,root.optString("category","精选"),root.optString("composer",""))
    }
    fun catalog(text:String):List<Pair<String,String>>{
        require(text.toByteArray().size<=MAX_BYTES);val root=JSONObject(text)
        require(root.getString("schema")=="soundcore.catalog.v1")
        val list=root.getJSONArray("scores");require(list.length()<=50)
        return (0 until list.length()).map{i->val item=list.getJSONObject(i);val title=item.getString("title");val url=item.getString("url")
            require(title.length in 1..80 && URL(url).protocol=="https");title to url}
    }
}
data class ScoreLibraryView(val scores:List<LibraryScore> = emptyList(),val busy:Boolean=false,val message:String="下载一次，离线也能演奏",val selected:Int=0,val part:Int=0,val url:String="",val remote:List<Pair<String,String>> = emptyList(),val catalog:List<LibraryScore> = emptyList(),
    val query:String="",val exploring:Boolean=false,val selectedId:String="") {
    val entries get()=(if(exploring)catalog else scores).filter{query.isBlank() || listOf(it.title,it.composer,it.category,it.credit).any{s->s.contains(query.trim(),true)}}
    val selection get()=(scores+catalog).firstOrNull{it.id==selectedId} ?: entries.firstOrNull()
}
class OnlineScores(private val context:Context,private val change:(ScoreLibraryView)->Unit){
    private fun readBounded(input:java.io.InputStream):ByteArray {
        val out=java.io.ByteArrayOutputStream();val buffer=ByteArray(4096)
        while(true){val n=input.read(buffer);if(n<0)break;require(out.size()+n<=StructuredScore.MAX_BYTES){"曲谱文件过大"};out.write(buffer,0,n)}
        return out.toByteArray()
    }
    private val main=Handler(Looper.getMainLooper());private val work=Executors.newSingleThreadExecutor();private var generation=0
    var view=ScoreLibraryView();private set
    private val dir=File(context.filesDir,"score_library").apply{mkdirs()}
    init {val defaults=context.assets.list("scores").orEmpty().filter{it.endsWith(".json")}.mapNotNull{name->runCatching{StructuredScore.parse(context.assets.open("scores/$name").bufferedReader().use{it.readText()})}.getOrNull()}
        val cached=dir.listFiles().orEmpty().mapNotNull{runCatching{StructuredScore.parse(it.readText())}.getOrNull()}
        view=view.copy(scores=(cached+defaults.filter{it.id in listOf("twinkle","ode_to_joy","frere_jacques")}).distinctBy{it.id},catalog=defaults.sortedWith(compareBy<LibraryScore>{when(it.category){"熟悉旋律"->0;"古典"->1;else->2}}.thenBy{it.title}),exploring=true);change(view)}
    private fun update(v:ScoreLibraryView){view=v;change(v)}
    fun query(text:String){update(view.copy(query=text.take(80)))}
    fun explore(value:Boolean){update(view.copy(exploring=value,selectedId="",part=0))}
    fun selectId(id:String){update(view.copy(selectedId=id,part=0))}
    fun collect(id:String){
        val score=view.catalog.firstOrNull{it.id==id}?:return
        runJob{score.json}
    }
    fun receiveLink(uri:Uri):Boolean {
        if(uri.scheme!="soundcore" || uri.host!="score")return false
        val id=uri.pathSegments.singleOrNull()?:return false
        if(!id.matches(Regex("[a-zA-Z0-9_-]{1,64}")) || view.catalog.none{it.id==id})return false
        collect(id);return true
    }
    fun select(i:Int){update(view.copy(selected=i,part=0))}
    fun part(i:Int){update(view.copy(part=i))}
    fun url(s:String){update(view.copy(url=s.take(2048)))}
    private fun accept(text:String){
        val score=StructuredScore.parse(text);val name=MessageDigest.getInstance("SHA-256").digest(score.id.toByteArray()).take(8).joinToString(""){"%02x".format(it)}
        File(dir,"$name.json").writeText(text)
        val list=listOf(score)+view.scores.filter{it.id!=score.id}
        update(view.copy(busy=false,scores=list,selected=0,selectedId=score.id,exploring=false,part=0,message="${score.title}已保存，可离线试听、演奏和指引"))
    }
    fun import(uri:Uri){if(view.busy)return;runJob{
        context.contentResolver.openInputStream(uri)!!.use{input->String(readBounded(input),Charsets.UTF_8)}
    }}
    fun fetch(url:String=view.url){if(view.busy)return;runJob{download(url)}}
    private fun runJob(read:()->String){val token=++generation;update(view.copy(busy=true,message="读取曲谱中…"))
        work.execute{val result=runCatching{read()};main.post{if(token==generation)result.onSuccess{text->runCatching{
            if(JSONObject(text).optString("schema")=="soundcore.catalog.v1")update(view.copy(busy=false,remote=StructuredScore.catalog(text),message="在线目录已更新，选择曲目即可下载"))else accept(text)
        }.onFailure{update(view.copy(busy=false,message="曲谱未载入：${it.message}"))}}.onFailure{update(view.copy(busy=false,message="下载未完成：${it.message}；已保存曲谱仍可使用"))}}}}
    private fun download(text:String):String {
        var url=URL(text);require(url.protocol=="https" && url.userInfo==null){"请输入HTTPS曲谱或目录地址"}
        repeat(4){val connection=url.openConnection()as HttpURLConnection
            connection.connectTimeout=8000;connection.readTimeout=10000;connection.instanceFollowRedirects=false
            try{val code=connection.responseCode
                if(code in 300..399){val target=URL(url,connection.getHeaderField("Location")?:error("缺少重定向地址"));require(target.protocol=="https" && target.userInfo==null);url=target}
                else {require(code==200){"服务器返回$code"};val bytes=connection.inputStream.use{readBounded(it)}
                    require(bytes.size<=StructuredScore.MAX_BYTES){"曲谱文件过大"};return String(bytes,Charsets.UTF_8)}
            }finally{connection.disconnect()}}
        error("重定向次数过多")
    }
    fun close(){generation++;work.shutdownNow();main.removeCallbacksAndMessages(null)}
}
