package cn.soundcore.instrument
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import org.json.JSONArray
import kotlin.math.pow

/** Edit the symbolic document rather than accumulating playback-only patches. */
@Composable fun SheetCorrection(raw:JSONObject,enabled:Boolean,onChange:(JSONObject)->Unit){
    var open by remember{mutableStateOf(false)}
    var bar by remember{mutableIntStateOf(0)};var index by remember{mutableIntStateOf(0)}
    var title by remember(raw){mutableStateOf(raw.optString("title"))}
    var order by remember(raw){mutableStateOf(raw.optJSONArray("play_order")?.let{a->(0 until a.length()).joinToString(","){a.getInt(it).toString()}}?:"")}
    var message by remember{mutableStateOf("")}
    TextButton(onClick={open=!open}){Text(if(open)"收起谱面核对" else "对照原图，修正音符与反复顺序")}
    if(!open)return
    val measures=raw.getJSONArray("measures");bar=bar.coerceIn(0,measures.length()-1)
    val measure=measures.getJSONObject(bar);val events=measure.getJSONArray("events");index=index.coerceIn(0,events.length()-1);val event=events.getJSONObject(index)
    fun edit(block:(JSONObject)->Unit){val next=JSONObject(raw.toString());block(next);onChange(next)}
    fun patch(field:String,value:Any){edit{next->val e=next.getJSONArray("measures").getJSONObject(bar).getJSONArray("events").getJSONObject(index)
        e.put(field,value);e.put("uncertain",JSONArray())
        if(field in listOf("beams","dots","extend")){val beam=e.optInt("beams");val dot=e.optInt("dots");val extend=e.optInt("extend")
            e.put("ticks",(96/2.0.pow(beam)*(2-1/2.0.pow(dot))+96*extend).toInt())}}}
    OutlinedTextField(value=title,onValueChange={title=it},label={Text("曲名")},singleLine=true,enabled=enabled,modifier=Modifier.fillMaxWidth())
    TextButton(onClick={edit{it.put("title",title.take(60))}},enabled=enabled){Text("保存曲名")}
    LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){itemsIndexed((0 until measures.length()).toList()){i,_->FilterChip(selected=bar==i,
        onClick={bar=i;index=0},enabled=enabled,label={Text("小节${measures.getJSONObject(i).getInt("id")}",fontSize=11.sp)})}}
    LazyRow(horizontalArrangement=Arrangement.spacedBy(6.dp)){itemsIndexed((0 until events.length()).toList()){i,_->FilterChip(selected=index==i,
        onClick={index=i},enabled=enabled,label={Text("${i+1}: ${events.getJSONObject(i).optInt("degree")}",fontSize=11.sp)})}}
    Text("数字0为休止；八度点、附点和减时线分别核对。",fontSize=11.sp)
    LazyRow(horizontalArrangement=Arrangement.spacedBy(4.dp)){itemsIndexed((0..7).toList()){_,n->FilterChip(selected=event.optInt("degree")==n,
        onClick={patch("degree",n)},enabled=enabled,label={Text(n.toString())})}}
    for((field,label,range) in listOf(Triple("octave","八度",-2..2),Triple("beams","减时线",0..3),Triple("dots","右附点",0..2),Triple("extend","延长线",0..8),Triple("accidental","临时升降",-1..1))){
        Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
            Text("$label ${event.optInt(field)}",modifier=Modifier.weight(1f))
            OutlinedButton(onClick={patch(field,event.optInt(field)-1)},enabled=enabled && event.optInt(field)>range.first){Text("−")}
            OutlinedButton(onClick={patch(field,event.optInt(field)+1)},enabled=enabled && event.optInt(field)<range.last){Text("+")}
        }
    }
    Row{Checkbox(checked=event.optBoolean("phrase_end"),onCheckedChange={patch("phrase_end",it)},enabled=enabled);Text("句尾换气")}
    Row{Checkbox(checked=event.optBoolean("tie_next"),onCheckedChange={patch("tie_next",it)},enabled=enabled);Text("与下一音同音延长")}
    Row{Checkbox(checked=event.optBoolean("slur_next"),onCheckedChange={patch("slur_next",it)},enabled=enabled);Text("与下一音圆滑连奏")}
    var lyric by remember(event.toString()){mutableStateOf(event.optString("lyric"))}
    OutlinedTextField(value=lyric,onValueChange={lyric=it},label={Text("对应歌词")},enabled=enabled,modifier=Modifier.fillMaxWidth())
    TextButton(onClick={patch("lyric",lyric.take(24))},enabled=enabled){Text("保存歌词")}
    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
        OutlinedButton(onClick={edit{next->val a=next.getJSONArray("measures").getJSONObject(bar).getJSONArray("events");val list=(0 until a.length()).map{a.getJSONObject(it)}.toMutableList()
            list.add(index+1,JSONObject().put("degree",1).put("octave",0).put("ticks",96).put("beams",0).put("dots",0).put("extend",0));
            next.getJSONArray("measures").getJSONObject(bar).put("events",JSONArray(list))}},enabled=enabled){Text("后面补音")}
        OutlinedButton(onClick={edit{it.getJSONArray("measures").getJSONObject(bar).getJSONArray("events").remove(index)}},enabled=enabled && events.length()>1){Text("删除此音")}
    }
    OutlinedTextField(value=order,onValueChange={order=it},label={Text("实际演奏的小节顺序")},supportingText={Text("用逗号分隔；反复段填写重复的小节编号")},enabled=enabled,modifier=Modifier.fillMaxWidth())
    TextButton(onClick={runCatching{val values=order.split(Regex("[，,\\s]+")).filter{it.isNotBlank()}.map{it.toInt()};require(values.isNotEmpty())
        edit{it.put("play_order",JSONArray(values))};message="已应用；请试听核对"}.onFailure{message="小节顺序无效"}},enabled=enabled){Text("应用演奏顺序")}
    if((raw.optJSONArray("review_unresolved")?.length()?:0)>0)TextButton(onClick={edit{it.put("review_unresolved",JSONArray())}},enabled=enabled){Text("已对照原图核对未定记号")}
    if(message.isNotEmpty())Text(message,fontSize=11.sp)
}
