package cn.soundcore.instrument

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun CreativeWorkspace(audio:MelodyView,sheet:SheetView,sheetAudio:MelodyView,
    onMode:(Boolean)->Unit,onLeave:()->Unit,onWorkspaceActive:(Boolean)->Unit={},
    recordContent:@Composable ()->Unit,sheetContent:@Composable ()->Unit) {
    var route by rememberSaveable { mutableStateOf("hub") }
    val pageTop=LocalPageTop.current
    LaunchedEffect(route){onWorkspaceActive(route!="hub");pageTop()}
    fun open(sheetMode:Boolean){onMode(sheetMode);route=if(sheetMode)"sheet" else "record"}
    fun back(){onLeave();route="hub"}
    BackHandler(route!="hub"){back()}
    if(route=="hub") {
        PageLead("创作","把听见的、看见的，变成自己的旋律")
        CreationEntry("录音成曲","录下清唱或独奏，留住这一段旋律",Glyph.RECORD,Color(0xFF174239),"从声音开始"){open(false)}
        Spacer(Modifier.height(15.dp))
        CreationEntry("AI识谱","选取曲谱照片，让纸上的音符响起来",Glyph.IMAGE,Color(0xFF193445),"从曲谱开始"){open(true)}
        if(audio.hasSource || audio.score!=null || sheet.music!=null || audio.busy || sheet.busy || audio.recording) {
            SectionHeader("继续创作")
            if(audio.hasSource || audio.score!=null || audio.busy || audio.recording)RecentCreation(audio.sourceName.ifBlank{"录音旋律"},
                if(audio.recording)"正在录音" else if(audio.busy)"正在整理 · ${audio.progress}%" else if(audio.score==null)"片段已准备好 · 等待识别" else "${audio.score.notes.size}个音符 · 已保存在手机",Glyph.WAVE){open(false)}
            if(sheet.music!=null || sheet.busy){Spacer(Modifier.height(9.dp));RecentCreation(sheet.music?.title?:"曲谱识别",
                if(sheet.busy)"正在读谱 · ${sheet.progress}%" else "${sheet.pageCount}页曲谱 · 可以继续调整",Glyph.IMAGE){open(true)}}
        }
        Spacer(Modifier.height(23.dp))
        HintLine("先在手机试听，连接声芯后再演奏。")
    } else {
        TextButton(onClick=::back,contentPadding=PaddingValues(start=0.dp,end=12.dp)){
            StudioIcon(Glyph.BACK,Modifier.size(18.dp),Muted);Spacer(Modifier.width(5.dp));Text("创作",color=Muted)
        }
        Spacer(Modifier.height(5.dp))
        if(route=="sheet")sheetContent() else recordContent()
    }
}

@Composable
private fun CreationEntry(title:String,subtitle:String,glyph:Glyph,color:Color,action:String,onClick:()->Unit) {
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(25.dp)).background(color).clickable(onClick=onClick).padding(24.dp),
        verticalArrangement=Arrangement.spacedBy(15.dp)) {
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.Top){
            StudioIcon(glyph,Modifier.size(34.dp),Aqua)
            SmallBadge(if(glyph==Glyph.IMAGE)"离线AI" else "3分钟",Aqua)
        }
        Text(title,color=White,fontSize=26.sp,fontWeight=FontWeight.SemiBold)
        Text(subtitle,color=White.copy(alpha=.66f),fontSize=13.sp,lineHeight=21.sp)
        Row(Modifier.padding(top=3.dp),verticalAlignment=Alignment.CenterVertically){Text(action,color=Aqua,fontSize=13.sp,fontWeight=FontWeight.Medium);Spacer(Modifier.width(9.dp));StudioIcon(Glyph.ARROW,Modifier.size(15.dp))}
    }
}

@Composable
private fun RecentCreation(title:String,subtitle:String,glyph:Glyph,onClick:()->Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(17.dp)).background(CardBlue).clickable(onClick=onClick).padding(16.dp),verticalAlignment=Alignment.CenterVertically){
        StudioIcon(glyph,Modifier.size(22.dp));Spacer(Modifier.width(13.dp))
        Column(Modifier.weight(1f)){Text(title,color=White,fontSize=14.sp,maxLines=1,overflow=TextOverflow.Ellipsis);Spacer(Modifier.height(4.dp));HintLine(subtitle)}
        StudioIcon(Glyph.ARROW,Modifier.size(15.dp),Muted)
    }
}
