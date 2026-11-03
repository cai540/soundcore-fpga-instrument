package cn.soundcore.instrument

import org.json.JSONObject

data class SheetEvent(val startMs:Int,val durationMs:Int,val midi:Int?,val measure:Int,val phraseEnd:Boolean=false,val slurNext:Boolean=false)
data class SheetPart(val label:String,val score:MelodyScore)
data class SheetMusic(val raw:JSONObject) {
    val title get()=raw.optString("title","图片曲谱").take(60)
    val defaultBpm get()=if(raw.isNull("bpm"))80 else ScoreFields.int(raw,"bpm",30,240)
    val notation get()=raw.getString("notation")
    val tempoMarked get()=!raw.isNull("bpm")
    private data class Symbol(val midi:Int?,val ticks:Int,val tie:Boolean,val phrase:Boolean,val slur:Boolean)
    fun compile(bpm:Int=defaultBpm):Pair<List<SheetEvent>,List<String>> {
        require(bpm in 30..240 && notation in listOf("jianpu","staff")){"曲谱类型或拍速无效"}
        val numerator=ScoreFields.int(raw,"numerator",1,12);val denominator=ScoreFields.int(raw,"denominator",2,16)
        require(denominator in listOf(2,4,8,16)){"拍号无效"}
        val tonic=if(notation=="jianpu")ScoreFields.int(raw,"tonic_midi",48,71) else 60
        val measures=raw.getJSONArray("measures");require(measures.length() in 1..256)
        val items=linkedMapOf<Int,List<Symbol>>();val warnings=mutableListOf<String>();var count=0
        if(!tempoMarked)warnings+="谱面未标拍速，当前使用${bpm} BPM，可调整"
        val scale=intArrayOf(0,2,4,5,7,9,11)
        for(i in 0 until measures.length()) {
            val m=measures.getJSONObject(i);val id=ScoreFields.int(m,"id",1,256);require(id !in items){"小节编号重复"}
            val a=m.getJSONArray("events");require(a.length() in 1..128)
            val symbols=(0 until a.length()).map { k -> val e=a.getJSONObject(k)
                val ticks=ScoreFields.int(e,"ticks",3,3072)
                e.optJSONArray("uncertain")?.let{u->if(u.length()>0)warnings+="第${id}小节第${k+1}音需核对："+(0 until u.length()).joinToString("、"){u.optString(it)}}
                val midi=if(notation=="jianpu") {
                    val degree=ScoreFields.int(e,"degree",0,7)
                    val octave=if(e.has("octave"))ScoreFields.int(e,"octave",-2,2) else 0
                    val accidental=if(e.has("accidental"))ScoreFields.int(e,"accidental",-1,1) else 0
                    if(degree==0)null else tonic+scale[degree-1]+12*octave+accidental
                } else {require(e.has("midi")){"五线谱缺少音高，不能当作休止符"};if(e.isNull("midi"))null else ScoreFields.int(e,"midi",24,108)}
                require(midi==null || midi in 24..108){"音高超出可编辑范围"}
                val tie=if(e.has("tie_next")){require(e.get("tie_next") is Boolean);e.getBoolean("tie_next")} else false
                Symbol(midi,ticks,tie,e.optBoolean("phrase_end"),e.optBoolean("slur_next"))
            }
            count+=symbols.size;require(count<=2048){"曲谱过长，请分开识别"}
            val meter=m.optJSONArray("meter");val localNum=meter?.optInt(0,numerator)?:numerator;val localDen=meter?.optInt(1,denominator)?:denominator
            require(localNum in 1..12 && localDen in listOf(2,4,8,16)){"本小节拍号无效"}
            if(symbols.sumOf{it.ticks}!=localNum*384/localDen && m.optString("incomplete") !in listOf("pickup","ending"))warnings+="第${id}小节拍数与拍号不一致，请核对弱起或漏识"
            items[id]=symbols
        }
        val order=if(raw.has("play_order"))raw.getJSONArray("play_order").let{a->
            require(a.length() in 1..512);(0 until a.length()).map{i->val n=a.get(i);require(n is Int || n is Long)
                val v=(n as Number).toLong();require(v in 1..256);v.toInt()}}
            else items.keys.toList()
        require(order.toSet()==items.keys && order.all{items.containsKey(it) && order.count{v->v==it}<=4}){"小节顺序缺失或重复过多"}
        fun ms(t:Long)=((t*60000+bpm*48)/(bpm*96)).toInt()
        val result=mutableListOf<SheetEvent>();var tick=0L;var pending=false
        for(id in order) for(s in items.getValue(id)) {
            val start=ms(tick);tick+=s.ticks;val end=ms(tick)
            require(end-start>=20 && end<=600000){"时值过短或曲谱超过10分钟"}
            if(pending){val old=result.last();require(old.midi!=null && old.midi==s.midi){"延音线两端音高不同"}
                result[result.lastIndex]=old.copy(durationMs=end-old.startMs,phraseEnd=s.phrase,slurNext=s.slur)}
            else result+=SheetEvent(start,end-start,s.midi,id,s.phrase,s.slur)
            require(result.size<=2048);pending=s.tie
        }
        require(!pending && result.any{it.midi!=null}){"缺少可演奏音符或延音线不完整"}
        raw.optJSONArray("review_unresolved")?.let{a->repeat(minOf(a.length(),32)){warnings+=a.optString(it).take(240)}}
        raw.optJSONArray("warnings")?.let{a->repeat(minOf(a.length(),12)){warnings+=a.optString(it).take(160)}}
        return result to warnings
    }
    fun parts(bpm:Int=defaultBpm):List<SheetPart> {
        val all=compile(bpm).first;val groups=mutableListOf<List<SheetEvent>>();var group=mutableListOf<SheetEvent>();var begin=0
        for(event in all){
            require(event.durationMs<=65535){"有单音超过65秒，请提高拍速或识别更短片段"}
            if(group.isNotEmpty() && (event.startMs+event.durationMs-begin>180000 || group.size>=512)) {
                groups+=group;group=mutableListOf();begin=event.startMs
            }
            if(group.isEmpty())begin=event.startMs
            group+=event
        }
        if(group.isNotEmpty())groups+=group
        return groups.mapIndexedNotNull { index,events ->
            val a=events.first().startMs;val z=events.last().let{it.startMs+it.durationMs}
            val notes=events.mapIndexedNotNull{k,e->e.midi?.let{pitch->
                val next=events.getOrNull(k+1)
                val printedRest=if(next?.midi==null)next?.durationMs?:0 else 0
                val cadence=printedRest==0 && (e.phraseEnd || e.durationMs>=1200 && next!=null)
                val breath=if(!raw.optBoolean("natural_phrasing") || e.slurNext)0.0 else if(cadence)minOf(240.0,maxOf(60.0,e.durationMs*(if(e.phraseEnd).18 else .1)),e.durationMs*.45) else minOf(35.0,e.durationMs*.06)
                MelodyNote(e.startMs-a,(e.durationMs-breath).toInt().coerceAtLeast(20),pitch,0f)}}
            if(notes.isEmpty())null else SheetPart("第${index+1}段 · ${a/1000}—${z/1000}秒 · 小节${events.first().measure}—${events.last().measure}",
                MelodyWorkspace.validated(MelodyScore(notes,z-a,true,if(notation=="jianpu")Math.floorMod(raw.getInt("tonic_midi"),12) else null)))
        }
    }
}
