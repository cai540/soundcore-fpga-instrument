package cn.soundcore.instrument

import org.json.JSONArray
import org.json.JSONObject

/** Page concatenation remaps symbolic ids; no melody- or title-specific corrections. */
object SheetDocuments {
    fun merge(pages:List<SheetMusic>,overrides:JSONObject=JSONObject()):SheetMusic {
        require(pages.isNotEmpty())
        val result=JSONObject(pages.first().raw.toString())
        val measures=JSONArray();val order=JSONArray();val warnings=JSONArray()
        var nextId=1
        pages.forEachIndexed { page,music ->
            require(music.notation==pages.first().notation){"曲谱类型不一致，请分开识别"}
            if(music.notation=="jianpu")require(music.raw.getInt("tonic_midi")==result.getInt("tonic_midi")){"多页调号不一致，请分开识别或核对原图"}
            val ids=mutableMapOf<Int,Int>();val source=music.raw.getJSONArray("measures")
            for(i in 0 until source.length()) {
                val bar=JSONObject(source.getJSONObject(i).toString());val old=bar.getInt("id")
                ids[old]=nextId;bar.put("id",nextId++);measures.put(bar)
                if(!bar.has("meter"))bar.put("meter",JSONArray(listOf(music.raw.getInt("numerator"),music.raw.getInt("denominator"))))
            }
            val play=music.raw.optJSONArray("play_order")?:JSONArray((0 until source.length()).map{source.getJSONObject(it).getInt("id")})
            for(i in 0 until play.length())order.put(ids[play.getInt(i)]?:error("曲谱反复顺序无效"))
            music.raw.optJSONArray("review_unresolved")?.let{a->for(i in 0 until a.length())warnings.put(if(pages.size>1)"第${page+1}页：${a.getString(i)}" else a.getString(i))}
            music.raw.optJSONArray("warnings")?.let{a->for(i in 0 until a.length())warnings.put(if(pages.size>1)"第${page+1}页：${a.getString(i)}" else a.getString(i))}
        }
        result.put("measures",measures).put("play_order",order).put("review_unresolved",warnings)
        result.remove("warnings")
        for(field in listOf("tonic_midi","bpm"))if(overrides.has(field))result.put(field,overrides.get(field))
        overrides.optJSONArray("meter")?.let{result.put("numerator",it.getInt(0)).put("denominator",it.getInt(1))}
        return SheetMusic(result).also{it.compile();it.parts()}
    }
}
