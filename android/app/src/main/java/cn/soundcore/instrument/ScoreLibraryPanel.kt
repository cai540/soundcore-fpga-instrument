package cn.soundcore.instrument

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun ScoreLibraryPanel(view:ScoreLibraryView,controller:OnlineScores?,onImport:()->Unit,onBrowse:()->Unit,onUse:(MelodyScore,String)->Unit){
    PageLead("旋律，随身收藏","30首精选 · 每首1—2分钟 · 下载一次，离线演奏")
    StudioCard {
        Row(verticalAlignment=Alignment.CenterVertically){
            Text("♫",fontSize=42.sp,color=Aqua,modifier=Modifier.padding(end=16.dp))
            Column { Text("曲谱书架",color=White,style=MaterialTheme.typography.headlineSmall)
                HintLine("传统旋律与古典主题，让下一次演奏有迹可循") }
        }
        OutlinedTextField(view.query,onValueChange={controller?.query(it)},modifier=Modifier.fillMaxWidth(),
            singleLine=true,label={Text("搜索曲名、作曲家或风格")},shape=RoundedCornerShape(16.dp))
        Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
            FilterChip(view.exploring,onClick={controller?.explore(true)},label={Text("发现曲谱 ${view.catalog.size}")})
            FilterChip(!view.exploring,onClick={controller?.explore(false)},label={Text("我的书架 ${view.scores.size}")})
        }
    }
    Spacer(Modifier.height(16.dp))
    if(view.entries.isEmpty())StudioCard{Text("这里暂时没有匹配的曲谱",color=White);HintLine("换个关键词，或到发现曲谱收藏一首。")}
    var expanded by remember(view.query,view.exploring){mutableStateOf(false)}
    view.entries.take(if(expanded)50 else 8).forEach { score ->
        val selected=view.selection?.id==score.id
        StudioCard {
            Row(Modifier.fillMaxWidth().clickable{controller?.selectId(score.id)},verticalAlignment=Alignment.CenterVertically){
                Box(Modifier.size(48.dp).background(if(score.category=="古典")Gold.copy(alpha=.13f) else Aqua.copy(alpha=.13f),RoundedCornerShape(14.dp)),contentAlignment=Alignment.Center){
                    Text(if(score.category=="古典")"♬" else "♪",fontSize=26.sp,color=if(score.category=="古典")Gold else Aqua)}
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)){Text(score.title,color=White,fontWeight=FontWeight.SemiBold,fontSize=15.sp)
                    HintLine("${score.category} · ${score.durationMs/60000}:${"%02d".format(score.durationMs/1000%60)} · ${score.composer}")}
                Text(if(selected)"⌄" else "›",color=Muted,fontSize=24.sp)
            }
            if(selected){
                HintLine(score.credit)
                if(score.parts.size>1)HintLine("共${score.parts.size}段，每段可独立试听与演奏")
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                    Button(onClick={onUse(score.parts[view.part.coerceIn(score.parts.indices)],score.title)},enabled=!view.busy,modifier=Modifier.weight(1f)){Text("试听与演奏")}
                    if(view.exploring)OutlinedButton(onClick={controller?.collect(score.id)},enabled=!view.busy){Text(if(view.scores.any{it.id==score.id})"已收藏" else "收藏")}
                }
            }
        }
        Spacer(Modifier.height(10.dp))
    }
    if(view.entries.size>8)TextButton(onClick={expanded=!expanded},modifier=Modifier.fillMaxWidth()){Text(if(expanded)"收起曲目" else "查看全部 ${view.entries.size} 首")}
    StudioCard {
        Text("更多旋律，从这里带回来",color=White,style=MaterialTheme.typography.titleMedium)
        HintLine("在线目录中的“加入声芯”会直接收藏到 App；也可以导入已有的结构化曲谱文件。")
        Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
            OutlinedButton(onClick=onBrowse){Text("浏览在线曲库 ↗")}
            OutlinedButton(onClick=onImport,enabled=!view.busy){Text("导入文件")}}
        var advanced by remember{mutableStateOf(false)}
        TextButton(onClick={advanced=!advanced}){Text(if(advanced)"收起链接导入" else "从下载链接导入")}
        if(advanced){OutlinedTextField(view.url,onValueChange={controller?.url(it)},label={Text("HTTPS曲谱直链")},modifier=Modifier.fillMaxWidth(),singleLine=true)
            Button(onClick={controller?.fetch()},enabled=!view.busy && view.url.startsWith("https://")){Text("下载并收藏")}}
        view.remote.filter{view.query.isBlank() || it.first.contains(view.query,true)}.forEach{(title,url)->TextButton(onClick={controller?.fetch(url)},enabled=!view.busy){Text("下载 · $title")}}
        if(view.busy)LinearProgressIndicator(Modifier.fillMaxWidth())
        HintLine(view.message)
    }
}
