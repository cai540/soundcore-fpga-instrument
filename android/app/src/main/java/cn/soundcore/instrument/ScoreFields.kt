package cn.soundcore.instrument

import org.json.JSONObject

/** API exists only for parsing old saved metadata. No production client is shipped. */
enum class RecognitionEngine { LOCAL, API }

internal object ScoreFields {
    fun int(j:JSONObject,key:String,min:Int,max:Int):Int {
        val value=j.opt(key)
        require(value is Int || value is Long){"曲谱字段无效：$key"}
        val number=(value as Number).toLong()
        require(number in min.toLong()..max.toLong()){"曲谱字段超出范围：$key"}
        return number.toInt()
    }
}
