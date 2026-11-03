package cn.soundcore.instrument

import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/** Legacy protocol regression helper. Test source only; excluded from APK. */
class ScoreApiClient(config:ScoreApiConfig) {
    private val config=config.checked()
    private val stopped=AtomicBoolean(false)
    private val active=AtomicReference<HttpURLConnection?>()
    @Volatile private var posting=false
    private var sessionToken=""
    private var sessionExpires=0L
    private fun session() {
        if(!config.managed || (sessionToken.isNotBlank() && sessionExpires>System.currentTimeMillis()/1000+60))return
        val value=request("POST","/v1/session",JSONObject().put("installation_id",config.installationId).toString().toByteArray(),
            mapOf("Content-Type" to "application/json"),bootstrap=true)
        sessionToken=value.getString("access_token")
        require(sessionToken.length in 40..1024){"创作会话无效，请重试"}
        sessionExpires=value.getLong("expires_at")
    }
    fun cancel() {
        stopped.set(true)
        // Let an accepted POST return its job id so finally can remove the job.
        if(!posting)active.get()?.disconnect()
    }
    private fun ensureActive(){check(!stopped.get() && !Thread.currentThread().isInterrupted){"已取消"}}
    private fun request(method:String,path:String,body:ByteArray?=null,headers:Map<String,String> = emptyMap(),cleanup:Boolean=false,bootstrap:Boolean=false):JSONObject {
        if(!cleanup)ensureActive()
        if(!bootstrap && config.managed)session()
        val c=URL(config.url+path).openConnection() as HttpURLConnection
        if(!cleanup)active.set(c)
        try {
            c.requestMethod=method;c.instanceFollowRedirects=false
            c.connectTimeout=if(cleanup)3000 else 8000;c.readTimeout=if(cleanup)3000 else 20000
            if(!bootstrap)c.setRequestProperty("Authorization","Bearer ${if(config.managed)sessionToken else config.token}")
            c.setRequestProperty("Accept","application/json")
            headers.forEach{(k,v)->c.setRequestProperty(k,v)}
            if(body!=null){c.doOutput=true;c.setFixedLengthStreamingMode(body.size)
                c.outputStream.use{it.write(body)}}
            val status=c.responseCode
            require(status !in 300..399) { "创作服务暂时不可用，请稍后重试" }
            val stream=if(status in 200..299)c.inputStream else c.errorStream
            val bytes=ByteArrayOutputStream()
            stream?.use { input -> val buffer=ByteArray(8192)
                while(true){val n=input.read(buffer);if(n<0)break
                    require(bytes.size()+n<=1_048_576){"服务响应过大"};bytes.write(buffer,0,n)} }
            val j=runCatching{JSONObject(bytes.toString("UTF-8"))}.getOrElse{error("创作服务暂时离线，请稍后重试")}
            if(status !in 200..299)error(when(status){401->"创作会话已过期，请重新识别";429->"创作请求较多，请稍后再试";503->"识谱服务正在准备，请稍后重试"
                else->j.optJSONObject("error")?.optString("message")?.take(150)?:"服务请求失败（$status）"})
            return j
        } finally {active.compareAndSet(c,null);c.disconnect()}
    }
    fun health(sheet:Boolean=false):String {
        val j=request("GET",if(sheet)"/v1/sheet-health" else "/v1/health")
        ScoreApiContract.int(j,"schema_version",1,1)
        require(j.optBoolean("ready",false)) { "服务可达，但模型尚未就绪" }
        if(sheet)return "图片识谱接口已就绪 · 模型额度会在实际读谱时校验"
        require(j.getJSONArray("input_modes").toString().contains("\"vocal\"")) { "服务不支持人声识谱" }
        return "服务已就绪 · 中文独唱 · 最长40秒"
    }
    fun recognize(pcm:FloatArray,rate:Int,progress:(Int,String)->Unit):Pair<MelodyScore,String> {
        require(rate in listOf(16000,22050,24000,32000,44100,48000) && pcm.size in rate/4..rate*40)
        val bytes=ByteBuffer.allocate(pcm.size*4).order(ByteOrder.LITTLE_ENDIAN)
        pcm.forEach{require(it.isFinite() && kotlin.math.abs(it)<=8);bytes.putFloat(it)}
        val raw=bytes.array();val sha=MessageDigest.getInstance("SHA-256").digest(raw).joinToString(""){"%02x".format(it)}
        val id=UUID.randomUUID().toString().replace("-","");val duration=(pcm.size.toLong()*1000/rate).toInt()
        val result=runTask("transcriptions",raw,mapOf("Content-Type" to "application/octet-stream",
            "X-Audio-Format" to "f32le","X-Sample-Rate" to "$rate","X-Input-Mode" to "vocal","X-Audio-SHA256" to sha),id,sha,rate,duration,progress)
        val score=ScoreApiContract.score(result,id,sha,rate,duration)
        val algorithm=result.optString("algorithm_id");require(algorithm.matches(Regex("[A-Za-z0-9_.-]{1,80}"))){"服务算法标识无效"}
        return score to algorithm
    }
    fun recognizeSheet(bytes:ByteArray,mime:String,progress:(Int,String)->Unit):SheetMusic {
        require(bytes.size in 1..6_000_000 && mime in listOf("image/jpeg","image/png")){"曲谱图片格式或大小不支持"}
        val sha=MessageDigest.getInstance("SHA-256").digest(bytes).joinToString(""){"%02x".format(it)}
        val id=UUID.randomUUID().toString().replace("-","")
        val result=runTask("sheet-transcriptions",bytes,mapOf("Content-Type" to mime,"X-Image-SHA256" to sha),id,sha,0,0,progress)
        return SheetMusic(result.getJSONObject("score")).also{it.compile();it.parts()}
    }
    private fun runTask(kind:String,body:ByteArray,headers:Map<String,String>,id:String,sha:String,rate:Int,duration:Int,
        progress:(Int,String)->Unit):JSONObject {
        var complete=false;var remoteId:String?=null
        try {
            if(kind=="transcriptions")health() else {
                val h=request("GET","/v1/sheet-health");ScoreApiContract.int(h,"schema_version",1,1)
                require(h.optBoolean("ready",false)){"图片识谱服务尚未配置，请更新并启动服务"}
            }
            progress(0,"发送所选片段")
            posting=true
            val first=try{request("POST","/v1/$kind",body,headers+("Idempotency-Key" to id))}finally{posting=false}
            val job=first.getString("job_id");require(job.matches(Regex("[a-f0-9]{32}"))){"服务任务标识无效"};remoteId=job
            ScoreApiContract.identity(first,id,sha,rate,duration)
            val deadline=System.nanoTime()+610_000_000_000L;var lastProgress=0
            while(true) {
                ensureActive();check(System.nanoTime()<deadline){"识别超时，请缩短片段或检查服务"}
                val value=request("GET","/v1/$kind/$job")
                require(value.optString("job_id")==job){"服务任务不一致"}
                ScoreApiContract.identity(value,id,sha,rate,duration)
                val p=ScoreApiContract.int(value,"progress",0,100);lastProgress=maxOf(lastProgress,p)
                val phase=when(value.optString("phase")){"queued"->"排队中";"speech"->"辨认演唱字音";"aligning"->"对齐字音与节奏"
                    "pitch"->"分析基频与八度";"melody"->"提取主旋律";"decoding"->"生成可演奏曲谱"
                    "reading_sheet"->"AI读取曲谱音符与时值";"checking_rhythm"->"核对调号与节奏";else->"识别中"}
                progress(lastProgress,phase)
                when(value.getString("status")) {
                    "succeeded"->{val result=value.getJSONObject("result");ScoreApiContract.identity(result,id,sha,rate,duration)
                        ensureActive();complete=true;return result}
                    "failed"->error(value.optJSONObject("error")?.optString("message")?.take(200)?:"识别未完成")
                    "cancelled"->error("服务任务已取消")
                    "queued","running"->Unit
                    else->error("未知服务任务状态")
                }
                repeat(5){ensureActive();Thread.sleep(100)}
            }
        } finally {if(!complete)remoteId?.let{runCatching{request("DELETE","/v1/$kind/$it",cleanup=true)}}}
    }
}
