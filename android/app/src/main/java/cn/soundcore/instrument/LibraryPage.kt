package cn.soundcore.instrument

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
internal fun SongsPage(view:BleView,canWrite:Boolean,command:(Int,Int?)->Unit,onNote:(Int,Boolean,Int)->Unit) {
    val s=view.state
    var selected by rememberSaveable { mutableIntStateOf(s?.song?:0) }
    var listen by rememberSaveable { mutableStateOf(true) }
    LaunchedEffect(s?.song){if(s!=null)selected=s.song}
    LaunchedEffect(s?.playbackState,s?.guideUiState){
        if(s?.playbackState in 1..2)listen=true else if(s?.guideUiState in 2..3)listen=false
    }
    val auto=s?.playbackState in 1..2
    val guiding=s?.guideUiState in 2..3
    val playing=auto || guiding
    val paused=if(auto)s?.playbackState==2 else guiding && s?.guideUiState==3
    val length=SongCatalog.length(selected)
    PageLead("曲库","选一首喜欢的，让声芯奏给你听")
    Box(Modifier.fillMaxWidth().height(148.dp).clip(RoundedCornerShape(26.dp))) {
        Image(painterResource(R.drawable.cover_moon),null,Modifier.fillMaxSize(),contentScale=ContentScale.Crop)
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0x2209171F),Navy.copy(alpha=.92f)))))
        Column(Modifier.align(Alignment.BottomStart).padding(22.dp),verticalArrangement=Arrangement.spacedBy(7.dp)) {
            SmallBadge("内置精选",Gold)
            Text(SongCatalog.title(selected),color=White,fontSize=27.sp,fontWeight=FontWeight.SemiBold)
            Text(if(selected==0)"口琴 · 熟悉而温暖的旋律" else "二胡 · 辽阔悠长的草原之歌",color=White.copy(alpha=.72f),fontSize=12.sp)
        }
    }
    Spacer(Modifier.height(18.dp))
    SongCatalog.songs.forEach { song ->
        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp))
            .background(if(selected==song.id)RaisedBlue else CardBlue)
            .border(1.dp,if(selected==song.id)Aqua.copy(alpha=.45f) else Color.Transparent,RoundedCornerShape(18.dp))
            .clickable(enabled=!playing){selected=song.id;if(canWrite)command(Protocol.SONG_SELECT,song.id)}
            .padding(13.dp),verticalAlignment=Alignment.CenterVertically) {
            Text("0${song.id+1}",color=if(selected==song.id)Aqua else Muted,fontSize=13.sp,modifier=Modifier.width(34.dp))
            Column(Modifier.weight(1f)){Text(song.title,color=White,fontSize=15.sp,fontWeight=FontWeight.Medium);Spacer(Modifier.height(4.dp));HintLine(if(song.id==0)"口琴" else "二胡")}
            StudioIcon(if(selected==song.id)Glyph.CHECK else Glyph.PLAY,Modifier.size(18.dp),if(selected==song.id)Aqua else Muted)
        }
        Spacer(Modifier.height(9.dp))
    }
    Spacer(Modifier.height(11.dp))
    StudioCard {
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            Box(Modifier.weight(1f)){ModeButton("聆听",Glyph.PLAY,listen,!playing){listen=true}}
            Box(Modifier.weight(1f)){ModeButton("跟着弹",Glyph.PADS,!listen,!playing){listen=false}}
        }
        HintLine(if(listen)"由设备自动演奏完整曲目" else "跟随亮灯敲击，音区会自动切换")
        if(guiding) {
            val finished=(s?.step?:0)>=length
            LinearProgressIndicator(progress={((s?.step?:0).toFloat()/length).coerceIn(0f,1f)},modifier=Modifier.fillMaxWidth())
            HintLine(if(finished)"本曲完成" else "进度 ${s?.step?:0} / $length")
            PadArc(!paused && !finished,s?.target?:-1,s?.padMask?:0,
                canWrite && s?.vibratoDepth!=null && !paused && !finished){pad,down ->
                if(down && s!=null && !s.realtimeNotes && s.bank!=s.guideTargetBank)command(Protocol.SET_BANK,s.guideTargetBank)
                onNote(pad,down,176)
            }
        } else if(auto) {
            Text(if(paused)"已暂停" else "声芯正在演奏",color=Aqua,fontSize=14.sp)
            ForceMeters(view,48)
        }
        Button(onClick={
            if(playing)command(if(auto)Protocol.AUTOPLAY_ACTION else Protocol.GUIDE_ACTION,if(paused)3 else 2)
            else {
                command(Protocol.SONG_SELECT,selected)
                command(if(listen)Protocol.GUIDE_ACTION else Protocol.AUTOPLAY_ACTION,0)
                command(if(listen)Protocol.AUTOPLAY_ACTION else Protocol.GUIDE_ACTION,1)
            }
        },enabled=canWrite && (!listen || s?.songExtended==true),modifier=Modifier.fillMaxWidth().height(52.dp),shape=RoundedCornerShape(16.dp)) {
            StudioIcon(if(playing && !paused)Glyph.PAUSE else Glyph.PLAY,Modifier.size(17.dp),Navy)
            Spacer(Modifier.width(9.dp))
            Text(if(playing)if(paused)"继续" else "暂停" else if(listen)"播放这首" else "开始跟弹")
        }
        if(playing)OutlinedButton(onClick={command(if(auto)Protocol.AUTOPLAY_ACTION else Protocol.GUIDE_ACTION,0)},
            enabled=canWrite,modifier=Modifier.fillMaxWidth()){Text("结束演奏")}
        if(!view.connected)HintLine("连接设备后即可聆听或跟弹")
    }
}

@Composable
private fun ModeButton(label:String,icon:Glyph,selected:Boolean,enabled:Boolean,onClick:()->Unit) {
    Surface(onClick=onClick,enabled=enabled,shape=RoundedCornerShape(13.dp),color=if(selected)Aqua.copy(alpha=.13f) else RaisedBlue) {
        Row(Modifier.fillMaxWidth().padding(vertical=14.dp),horizontalArrangement=Arrangement.Center,verticalAlignment=Alignment.CenterVertically){
            StudioIcon(icon,Modifier.size(17.dp),if(selected)Aqua else Muted);Spacer(Modifier.width(7.dp));Text(label,color=if(selected)Aqua else Muted,fontSize=14.sp)
        }
    }
}
