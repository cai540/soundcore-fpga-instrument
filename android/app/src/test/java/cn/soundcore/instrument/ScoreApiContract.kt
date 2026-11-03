package cn.soundcore.instrument

import org.json.JSONObject
import java.net.URI

data class ScoreApiConfig(val url:String="",val token:String="",val managed:Boolean=false,val installationId:String="") {
    fun checked():ScoreApiConfig {
        val base=ScoreApiContract.baseUrl(url)
        if(managed)require(installationId.matches(Regex("[a-f0-9]{32}"))) { "创作会话初始化失败，请重新打开App" }
        else require(token.length in 24..256 && token.all{it.code in 33..126}) { "创作连接未就绪" }
        return copy(url=base)
    }
}

/** A single source clock and identity are carried through every response. */
object ScoreApiContract {
    fun baseUrl(text:String):String {
        val u=runCatching{URI(text.trim())}.getOrElse{error("服务地址格式不正确")}
        require(u.scheme in listOf("http","https") && !u.host.isNullOrBlank() &&
            u.rawUserInfo==null && u.rawQuery==null && u.rawFragment==null &&
            (u.rawPath.isNullOrEmpty() || u.rawPath=="/") && (u.port==-1 || u.port in 1..65535)) {
            "填写服务根地址，例如 http://192.168.1.20:8765" }
        if(u.scheme=="http") {
            val p=u.host.split('.').map{it.toIntOrNull()}
            require(p.size==4 && p.all{it!=null && it in 0..255} &&
                (p[0]==10 || p[0]==127 || (p[0]==192 && p[1]==168) || (p[0]==172 && p[1]!! in 16..31))) {
                "HTTP只支持局域网数字地址；公网服务请使用HTTPS" }
        }
        return text.trim().trimEnd('/')
    }
    fun int(j:JSONObject,key:String,min:Int,max:Int):Int {
        val n=j.opt(key)
        require(n is Int || n is Long) { "服务字段无效：$key" }
        val v=(n as Number).toLong()
        require(v in min.toLong()..max.toLong()) { "服务字段超出范围：$key" }
        return v.toInt()
    }
    fun identity(j:JSONObject,id:String,sha:String,rate:Int,duration:Int) {
        require(int(j,"schema_version",1,1)==1 && j.optString("request_id")==id &&
            j.optString("source_sha256")==sha && int(j,"source_sample_rate",rate,rate)==rate &&
            int(j,"source_duration_ms",duration,duration)==duration) { "服务结果与当前音频不一致" }
    }
    fun score(j:JSONObject,id:String,sha:String,rate:Int,duration:Int):MelodyScore {
        identity(j,id,sha,rate,duration)
        val a=j.getJSONArray("notes");require(a.length() in 1..512) { "服务没有返回有效旋律" }
        val notes=(0 until a.length()).map { i -> val n=a.getJSONObject(i)
            MelodyNote(int(n,"start_ms",0,duration),int(n,"duration_ms",20,40000),int(n,"midi",24,108),0f) }
        var end=0;var count=0
        notes.forEachIndexed{i,n->require(n.startMs>=end && n.startMs.toLong()+n.durationMs<=duration) { "服务音符重叠或超出片段" }
            count+=1+if(i>0 && n.startMs>end)1 else 0;end=n.startMs+n.durationMs}
        require(count<=512) { "旋律过密，请缩短识别片段" }
        return MelodyWorkspace.validated(MelodyScore(notes,duration))
    }
}
