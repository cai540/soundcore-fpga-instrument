package cn.soundcore.instrument

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import org.json.JSONArray

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SheetPanel(sheet:SheetView,connected:Boolean,enabled:Boolean,onImport:()->Unit,onRecognize:(JSONObject)->Unit,onCancel:()->Unit,
    onPage:(Int)->Unit,onScoreChange:(JSONObject)->Unit,onBpm:(Int)->Unit,onPart:(Int)->Unit,onUse:()->Unit,
    onMode:(SheetRecognitionMode)->Unit={},onCamera:()->Unit={}) {
    var advanced by remember{mutableStateOf(false)}
    var correction by remember{mutableStateOf(false)}
    var key by remember{mutableStateOf("")};var meter by remember{mutableStateOf("")};var bpm by remember{mutableStateOf("")}
    var expandedWarnings by remember{mutableStateOf(false)}
    var showSource by remember{mutableStateOf(false)}
    val pageTop=LocalPageTop.current
    LaunchedEffect(sheet.busy,sheet.music!=null){if(!sheet.busy && sheet.music!=null)showSource=false;pageTop()}
    fun recognize(){
        val cfg=JSONObject()
        mapOf("C" to 60,"升C" to 61,"降D" to 61,"D" to 62,"降E" to 63,"E" to 64,"F" to 65,"升F" to 66,"降G" to 66,"G" to 67,"降A" to 68,"A" to 69,"降B" to 70,"B" to 71)[key.trim()]?.let{cfg.put("tonic_midi",it)}
        val parts=meter.split('/');if(parts.size==2 && parts.all{it.toIntOrNull()!=null})cfg.put("meter",JSONArray(parts.map{it.toInt()}))
        bpm.toIntOrNull()?.let{cfg.put("bpm",it)};onRecognize(cfg)
    }
    PageLead("AI识谱",if(sheet.music==null)"拍下曲谱，先试听，再演奏" else "曲谱已读好，选一段听听")
    if(sheet.busy){
        StudioCard {
            StudioIcon(Glyph.IMAGE,Modifier.size(40.dp))
            Text("正在读懂曲谱",color=White,style=MaterialTheme.typography.headlineMedium)
            Text("${sheet.progress}%",color=Aqua,fontSize=28.sp)
            LinearProgressIndicator(progress={sheet.progress/100f},modifier=Modifier.fillMaxWidth())
            HintLine(sheet.message)
            OutlinedButton(onClick=onCancel,modifier=Modifier.fillMaxWidth()){Text("取消读谱")}
        }
        return
    }
    if(sheet.music!=null)Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){
        SmallBadge(if(sheet.pageCount>0)"${sheet.pageCount}页曲谱" else "曲谱已识别")
        TextButton(onClick={showSource=!showSource}){Text(if(showSource)"收起原谱" else "查看原谱 / 重新识别")}
    }
    if(sheet.music==null || showSource)StudioCard {
        if(sheet.image!=null){
            if(sheet.pageCount>1)LazyRow(horizontalArrangement=Arrangement.spacedBy(7.dp)){itemsIndexed((0 until sheet.pageCount).toList()){i,_->
                ChoiceChip("第${i+1}页",i==sheet.pageIndex){onPage(i)}}}
            Image(sheet.image.asImageBitmap(),"曲谱原图",Modifier.fillMaxWidth().heightIn(min=120.dp,max=250.dp),contentScale=ContentScale.Fit)
        }else{
            StudioIcon(Glyph.IMAGE,Modifier.size(44.dp))
            Text("让纸上的音符响起来",color=White,style=MaterialTheme.typography.titleLarge)
            HintLine("清晰的单声部数字简谱，最多6页。请保留调号、拍号和八度点。")
        }
        Row(horizontalArrangement=Arrangement.spacedBy(10.dp)) {
            OutlinedButton(onClick=onCamera,enabled=enabled,modifier=Modifier.weight(1f).heightIn(min=50.dp)){Text("拍摄曲谱")}
            OutlinedButton(onClick=onImport,enabled=enabled,modifier=Modifier.weight(1f).heightIn(min=50.dp)){Text(if(sheet.image==null)"从相册选择" else "更换图片")}
        }
        if(sheet.image!=null)Button(onClick=::recognize,enabled=enabled && (sheet.mode==SheetRecognitionMode.PHONE || connected),modifier=Modifier.fillMaxWidth().heightIn(min=52.dp)){
            Text(if(sheet.music==null)"开始识谱" else "重新识谱")}
        HintLine(if(sheet.mode==SheetRecognitionMode.PHONE)"手机执行内置符号模型与谱面分析，断网也能识谱、试听。" else "与手机使用同一份符号权重，数字分类由FPGA执行；文字、八度点和节奏在手机整理。")
        TextButton(onClick={advanced=!advanced},contentPadding=PaddingValues(0.dp)){Text(if(advanced)"收起识谱选项" else "识谱选项",fontSize=12.sp)}
        if(advanced){
            Row(horizontalArrangement=Arrangement.spacedBy(7.dp)){
                ChoiceChip("手机内置",sheet.mode==SheetRecognitionMode.PHONE,enabled){onMode(SheetRecognitionMode.PHONE)}
                ChoiceChip("FPGA识谱",sheet.mode==SheetRecognitionMode.DEVICE,enabled){onMode(SheetRecognitionMode.DEVICE)}
            }
            if(sheet.mode==SheetRecognitionMode.DEVICE && !connected)ConnectionHint()
            HintLine("参数默认从谱面读取；原图模糊时，可手动补充。")
            Row(horizontalArrangement=Arrangement.spacedBy(7.dp)){
                OutlinedTextField(key,{key=it},label={Text("调号")},placeholder={Text("降E")},singleLine=true,modifier=Modifier.weight(1f))
                OutlinedTextField(meter,{meter=it},label={Text("拍号")},placeholder={Text("6/8")},singleLine=true,modifier=Modifier.weight(1f))
                OutlinedTextField(bpm,{bpm=it},label={Text("拍速")},placeholder={Text("62")},singleLine=true,modifier=Modifier.weight(1f))
            }
        }
    }
    if((sheet.image!=null && sheet.music==null) || sheet.message.contains("失败") || sheet.message.contains("未完成")){Spacer(Modifier.height(14.dp));HintLine(sheet.message)}
    sheet.music?.let{music->
        Spacer(Modifier.height(20.dp))
        StudioCard {
            SmallBadge("识谱完成")
            Text(music.title,color=White,style=MaterialTheme.typography.headlineMedium)
            HintLine("${if(music.notation=="jianpu")"简谱" else "五线谱"} · ${music.raw.getInt("numerator")}/${music.raw.getInt("denominator")}")
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("演奏拍速",color=White);Text("${sheet.bpm} BPM",color=Aqua)}
            var tempo by remember(sheet.bpm){mutableFloatStateOf(sheet.bpm.toFloat())}
            Slider(value=tempo,onValueChange={tempo=it},onValueChangeFinished={onBpm(tempo.toInt())},valueRange=30f..240f,enabled=enabled)
            if(!music.tempoMarked)HintLine("原谱未标拍速，暂用80 BPM。")
            val warnings=sheet.warnings.distinct()
            if(warnings.isNotEmpty()){
                Surface(onClick={expandedWarnings=!expandedWarnings},color=Gold.copy(alpha=.08f),shape=MaterialTheme.shapes.medium){
                    Text("${warnings.size}处建议核对 · ${if(expandedWarnings)"收起" else "查看"}",Modifier.fillMaxWidth().padding(13.dp),color=Gold,fontSize=13.sp)}
                if(expandedWarnings)warnings.map(::friendlySheetWarning).distinct().forEach{Text(it,color=Gold,fontSize=12.sp,lineHeight=20.sp)}
            }
            if(sheet.parts.size>1){
                Text("选择演奏片段",color=White,style=MaterialTheme.typography.titleMedium)
                LazyRow(horizontalArrangement=Arrangement.spacedBy(7.dp)){itemsIndexed(sheet.parts){i,p->ChoiceChip(p.label,i==sheet.part,enabled){onPart(i)}}}
                HintLine("长谱分段载入，每段最长3分钟；可先试听再发送到设备。")
            }
            Button(onClick=onUse,enabled=enabled && sheet.selected!=null,modifier=Modifier.fillMaxWidth().heightIn(min=52.dp)){Text("试听这段曲谱")}
            TextButton(onClick={correction=true},enabled=enabled){Text("对照原图微调")}
        }
        if(correction)ModalBottomSheet(onDismissRequest={correction=false},containerColor=CardBlue){
            Column(Modifier.verticalScroll(rememberScrollState()).padding(20.dp).padding(bottom=30.dp)){
                Text("谱面核对",color=White,style=MaterialTheme.typography.headlineMedium)
                sheet.image?.let{Image(it.asImageBitmap(),"曲谱原图",Modifier.fillMaxWidth().heightIn(max=190.dp),contentScale=ContentScale.Fit)}
                SheetCorrection(music.raw,enabled,onScoreChange)
                Button(onClick={correction=false},modifier=Modifier.fillMaxWidth()){Text("完成")}
            }
        }
    }
}

internal fun friendlySheetWarning(text:String):String=when {
    text.contains("tie_next") || text.contains("slur_next")->"部分连线需要核对：同音延长与不同音高的连奏应区分。"
    text.contains("ticks") || text.contains("时值")->"部分音符时值需要对照原谱核对，请先试听节奏。"
    text.contains("play_order")->"反复顺序需要核对，可在“对照原图微调”中调整。"
    text.contains("水印")->"已忽略谱面水印。"
    else->text.replace("tie_next=true","延音").take(220)
}
