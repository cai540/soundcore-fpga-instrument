package cn.soundcore.instrument

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.roundToInt

@Composable
internal fun PerformancePage(view:BleView,canWrite:Boolean,command:(Int,Int?)->Unit,onNote:(Int,Boolean,Int)->Unit,
    onPitch:(Int,Boolean,Int)->Unit={_,_,_->},onRelease:()->Unit={}) {
    val s=view.state
    var velocity by remember { mutableFloatStateOf(176f) }
    var chromatic by remember { mutableStateOf(false) }
    val key=view.pitchLayout?.key?:0
    val handpan=InstrumentTone.isHandpan(s?.timbre)
    val metal=InstrumentTone.isMetal(s?.timbre)
    val keysEnabled=canWrite && s?.vibratoDepth!=null
    PageLead(if(metal)"金属现场" else if(handpan)"指尖手碟" else "自由演奏",
        if(metal)"敲出节奏，滑出声音的锋芒" else if(handpan)"轻敲成音，让余韵自由交叠" else "七个琴键，把旋律握在指尖")
    if(!view.connected){ConnectionHint();Spacer(Modifier.height(18.dp))}
    if(view.connected && view.pitchLayout==null)HintLine(if(view.layoutSupported==false)"请安装配套的七自然音固件" else "正在核对设备音高版本…")
    val runtimeGuide=view.uploadedScore?.let{it.guiding && !it.finished && !it.paused}==true
    val guide=runtimeGuide || (s?.guideUiState==2 && s.step<SongCatalog.length(s.song))
    StudioCard {
        Row(verticalAlignment=Alignment.CenterVertically) {
            Text("七音演奏",Modifier.weight(1f),style=MaterialTheme.typography.titleMedium)
            SmallBadge(if(s==null)"等待连接" else "${PitchLayout.keys[key]}调 · 音区${s.bank+1}")
        }
        Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            FilterChip(!chromatic,onClick={onRelease();chromatic=false},label={Text(if(handpan)"手碟七键" else "简谱 1—7")})
            FilterChip(chromatic,onClick={onRelease();chromatic=true},label={Text("完整十二音")})
        }
        if(chromatic) {
            ChromaticKeys(s?.bank?:2,key,keysEnabled){index,down->onPitch(index,down,velocity.roundToInt())}
        } else {
            PadArc(guide,if(runtimeGuide)view.uploadedScore?.pad?:-1 else s?.target?:-1,
                s?.padMask?:0,keysEnabled,if(handpan)InstrumentTone.handpanLabels(s?.bank?:2,key).let{labels->view.padOrder.map{labels[it]}} else null,degrees=view.padOrder){pad,down->onNote(pad,down,velocity.roundToInt())}
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
            Text(if(s==null)"音色待同步" else InstrumentTone.name(s.timbre),color=White,fontSize=13.sp)
            HintLine(if(guide)"跟随亮灯 · 自动切换音高" else if(handpan)"${InstrumentTone.style(s!!.timbre)} · ${if(chromatic)"精确十二音" else "五声音阶"}" else PitchLayout.range(s?.bank?:2,key))
        }
        HorizontalDivider(color=BorderBlue.copy(alpha=.5f))
        if(!metal) {
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
            Text("力度",color=Muted,fontSize=12.sp)
            Text("${(velocity*100/255).roundToInt()}%",color=Aqua,fontSize=12.sp)
        }
        Slider(value=velocity,onValueChange={velocity=it},valueRange=32f..255f)
        }
        if(metal) {
            RockControls(s,canWrite,velocity,{velocity=it},command)
        } else if(handpan) {
            HintLine("敲一下即可自然延音，连续敲击会叠加余韵。")
        } else {
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
            Column(Modifier.weight(1f)){Text("颤音",style=MaterialTheme.typography.titleMedium);HintLine("让长音自然起伏")}
            Switch(checked=s?.vibrato==true,onCheckedChange={command(Protocol.SET_VIBRATO,if(it)1 else 0)},enabled=canWrite)
        }
        if(s?.vibrato==true && s.vibratoDepth!=null){
            var depth by remember(s.vibratoDepth){mutableFloatStateOf(s.vibratoDepth.toFloat())}
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){HintLine("颤音深度");HintLine("${(depth/15*100).roundToInt()}%")}
            Slider(value=depth,onValueChange={depth=it},onValueChangeFinished={command(Protocol.SET_VIB_DEPTH,depth.roundToInt())},
                valueRange=0f..15f,enabled=canWrite)
        }
        BendControl(s,canWrite,command)
        }
    }
    SectionHeader("演奏设置")
    StudioCard {
        Row(verticalAlignment=Alignment.CenterVertically) {
            Text("音区",Modifier.weight(1f),style=MaterialTheme.typography.titleMedium)
            HintLine(if(handpan)"五声音阶 · 随心即兴" else "七个自然音 × 五个八度")
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(7.dp)) {
            repeat(5){bank->Box(Modifier.weight(1f)){
                Surface(onClick={command(Protocol.SET_BANK,bank)},enabled=canWrite,shape=RoundedCornerShape(12.dp),
                    color=if(s?.bank==bank)Aqua else RaisedBlue) {
                    Box(Modifier.fillMaxWidth().height(44.dp),contentAlignment=Alignment.Center){
                        Text("${bank+1}",color=if(s?.bank==bank)Navy else White,fontWeight=FontWeight.Medium)}
                }
            }}
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically) {
            Text("调号",style=MaterialTheme.typography.titleMedium)
            var open by remember{mutableStateOf(false)}
            Box {
                TextButton(onClick={open=true},enabled=canWrite && !guide && s?.playbackState !in 1..2){Text("${PitchLayout.keys[key]} ${if(handpan)"五声" else "大调"} ▾",color=Aqua)}
                DropdownMenu(expanded=open,onDismissRequest={open=false}) {
                    PitchLayout.keys.forEachIndexed{index,label->DropdownMenuItem(text={Text("$label ${if(handpan)"五声音阶" else "大调"}")},onClick={open=false;onRelease();command(Protocol.SET_KEY,index)})}
                }
            }
        }
        VolumeControl(s?.volume,canWrite,command)
    }
    if(s?.playbackState in 1..2 || s?.guideUiState in 2..3) {
        Spacer(Modifier.height(16.dp))
        StudioCard {
            SmallBadge(if(s?.playbackState in 1..2)"正在聆听" else "正在跟弹",Gold)
            Text(SongCatalog.title(s?.song?:0),style=MaterialTheme.typography.titleLarge)
            Row(horizontalArrangement=Arrangement.spacedBy(10.dp)){
                val automatic=s?.playbackState in 1..2
                val paused=if(automatic)s?.playbackState==2 else s?.guideUiState==3
                OutlinedButton(onClick={command(if(automatic)Protocol.AUTOPLAY_ACTION else Protocol.GUIDE_ACTION,if(paused)3 else 2)},enabled=canWrite){Text(if(paused)"继续" else "暂停")}
                TextButton(onClick={command(if(automatic)Protocol.AUTOPLAY_ACTION else Protocol.GUIDE_ACTION,0)},enabled=canWrite){Text("结束")}
            }
        }
    }
    SectionHeader("实时力度")
    StudioCard {
        ForceMeters(view,84)
        HintLine(if(view.telemetry==null)"连接设备后，显示七片琴键的实时力度" else "与设备琴键同步")
    }
}

@Composable
private fun BendControl(s:DeviceState?,enabled:Boolean,command:(Int,Int?)->Unit,
    title:String="临时滑音",hint:String="松手回中") {
    var dragging by remember { mutableStateOf(false) }
    var bend by remember { mutableFloatStateOf(128f) }
    LaunchedEffect(s?.bend){if(!dragging)bend=(s?.bend?:128).toFloat()}
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text(title,style=MaterialTheme.typography.titleMedium);HintLine(hint)}
    Slider(value=bend,onValueChange={dragging=true;bend=it;command(Protocol.SET_BEND,it.roundToInt())},
        onValueChangeFinished={dragging=false;bend=128f;command(Protocol.RELEASE_BEND,null)},valueRange=0f..255f,
        enabled=enabled && s?.bend!=null)
}

@Composable
private fun RockControls(s:DeviceState?,enabled:Boolean,velocity:Float,onVelocity:(Float)->Unit,
    command:(Int,Int?)->Unit) {
    var drive by remember(s?.vibratoDepth){mutableFloatStateOf((s?.vibratoDepth?:4).toFloat())}
    Column(verticalArrangement=Arrangement.spacedBy(6.dp)) {
        Row(horizontalArrangement=Arrangement.spacedBy(18.dp)) {
            Column(Modifier.weight(1f)) {
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("力度",fontSize=12.sp);Text("${(velocity*100/255).roundToInt()}%",color=Aqua,fontSize=12.sp)}
                Slider(value=velocity,onValueChange=onVelocity,valueRange=32f..255f,modifier=Modifier.height(34.dp))
            }
            Column(Modifier.weight(1f)) {
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("失真",fontSize=12.sp);Text("${(drive/15*100).roundToInt()}%",color=Aqua,fontSize=12.sp)}
                Slider(value=drive,onValueChange={drive=it},onValueChangeFinished={command(Protocol.SET_VIB_DEPTH,drive.roundToInt())},
                    valueRange=0f..15f,enabled=enabled && s?.vibratoDepth!=null,modifier=Modifier.height(34.dp))
            }
        }
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
            Text("摇摆颤音",Modifier.weight(1f),fontSize=13.sp)
            Switch(checked=s?.vibrato==true,onCheckedChange={command(Protocol.SET_VIBRATO,if(it)1 else 0)},enabled=enabled)
        }
        BendControl(s,enabled,command,"扫频与滑音","松手交回实体滑杆")
        HintLine("长按旋钮调失真，短按切换颤音。")
    }
}

@Composable
internal fun VolumeControl(volume:Int?,enabled:Boolean,command:(Int,Int?)->Unit) {
    var draft by remember(volume){mutableFloatStateOf((volume?:16).toFloat())}
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("音量",style=MaterialTheme.typography.titleMedium);Text(if(volume==null)"—" else "${(draft/31*100).roundToInt()}%",color=Aqua,fontSize=13.sp)}
    Slider(value=draft,onValueChange={draft=it},onValueChangeFinished={command(Protocol.SET_VOLUME,draft.roundToInt())},
        valueRange=0f..31f,enabled=enabled)
}

@Composable
internal fun ForceMeters(view:BleView,height:Int=72) {
    Row(Modifier.fillMaxWidth().height((height+24).dp),horizontalArrangement=Arrangement.spacedBy(12.dp),verticalAlignment=Alignment.Bottom) {
        repeat(7){i->
            val level=view.telemetry?.pads?.getOrNull(i)?:0
            Column(Modifier.weight(1f),horizontalAlignment=Alignment.CenterHorizontally) {
                Box(Modifier.fillMaxWidth().height(maxOf(5,height*level/255).dp)
                    .background(if(level>0)Aqua else BorderBlue,RoundedCornerShape(5.dp)))
                Spacer(Modifier.height(7.dp));Text("${i+1}",color=Muted,fontSize=10.sp)
            }
        }
    }
}
