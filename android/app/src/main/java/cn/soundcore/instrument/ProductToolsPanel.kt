package cn.soundcore.instrument

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import kotlin.math.roundToInt

@Composable
fun ProductToolsPanel(view:ProductToolsView,connected:Boolean,controller:ProductToolsController?,initialSection:Int=0,showDiagnostic:Boolean=false,onMicrophone:(Boolean)->Unit={},onBack:()->Unit) {
    BackHandler(onBack=onBack)
    DisposableEffect(controller){controller?.open();onDispose{controller?.leave()}}
    TextButton(onClick=onBack){Text("‹ 返回设备")}
    PageLead("演奏工具","看见声音，也留住刚刚的灵感")
    var tab by remember{mutableIntStateOf(initialSection)}
    var zoom by remember{mutableStateOf(false)}
    var editPad by remember{mutableIntStateOf(-1)}
    var editKey by remember{mutableIntStateOf(0)}
    LaunchedEffect(tab){controller?.section(tab)}
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)){
        listOf("声音图景","琴键设置","设备录音").forEachIndexed{i,label->FilterChip(tab==i,onClick={tab=i},label={Text(label)})}
    }
    Spacer(Modifier.height(14.dp))
    val enabled=connected && (!view.busy || view.refreshing)
    when(tab){
        0->{
            StudioCard { ScopeWorkbench(view,controller,onMicrophone,onExpand={zoom=true}) }
            var expanded by remember{mutableStateOf(showDiagnostic)}
            TextButton(onClick={expanded=!expanded}){Text(if(expanded)"收起复音检测 ▴" else "打开复音检测 ▾")}
            if(expanded)StudioCard {
                Text("独立声部检测",color=White,style=MaterialTheme.typography.titleLarge)
                HintLine("测试会切换为低音量纯音，便于在实验室观察频谱。最长60秒，退出页面或断开连接自动停止。")
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)){
                    listOf(4,8,16,32).forEach{n->OutlinedButton(onClick={controller?.diagnose(n)},enabled=enabled,modifier=Modifier.weight(1f),contentPadding=PaddingValues(6.dp)){Text("$n")}}}
                Text("请求 ${view.status?.requested?:0}  · 活动声部 ${view.status?.active?:0}",color=Aqua)
                Text(if(view.status?.deadlineFault==true)"音频时限：检测到超时" else "音频时限：${if(view.status==null)"待连接" else "未检测到超时"}",color=if(view.status?.deadlineFault==true)Gold else Muted)
                var slot by remember{mutableFloatStateOf(0f)}
                Text("声部 ${view.selectedVoice+1} · ${PitchLayout.name(view.voiceNote+36)}",color=White)
                Slider(slot,onValueChange={slot=it},onValueChangeFinished={controller?.selectVoice(slot.roundToInt())},valueRange=0f..31f,steps=30,enabled=enabled)
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                    OutlinedButton(onClick={controller?.voice(view.voiceNote-1,view.voiceOn)},enabled=enabled && view.status?.requested!=0){Text("降半音")}
                    OutlinedButton(onClick={controller?.voice(view.voiceNote+1,view.voiceOn)},enabled=enabled && view.status?.requested!=0){Text("升半音")}
                    Switch(view.voiceOn,onCheckedChange={controller?.voice(view.voiceNote,it)},enabled=enabled && view.status?.requested!=0)
                }
                Button(onClick={controller?.diagnose(0)},enabled=connected,modifier=Modifier.fillMaxWidth()){Text("停止检测")}
            }
        }
        1->StudioCard {
            Text("同一音区，自由排列",color=White,style=MaterialTheme.typography.titleLarge)
            HintLine("每片选择一个简谱音级，1—7各一次。交换位置后，音区加减与调号对全部琴键共同生效。")
            view.mapping.forEachIndexed{i,n->
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){
                    Text("琴片 ${i+1}",Modifier.padding(top=12.dp),color=White)
                    TextButton(onClick={editPad=i;editKey=n},enabled=enabled){Text("${n+1}  ›",color=Aqua)}
                }
            }
            Button(onClick={controller?.applyMap(true)},enabled=enabled,modifier=Modifier.fillMaxWidth()){Text("应用并保存排列")}
            OutlinedButton(onClick={controller?.applyMap(false)},enabled=enabled,modifier=Modifier.fillMaxWidth()){Text("恢复 1—7 顺序")}
            HintLine("曲目指引按曲谱目标优先，十二音琴键保持原来的精确音高。")
        }
        2->StudioCard {
            Text("留住设备的声音",color=White,style=MaterialTheme.typography.titleLarge)
            HintLine("直接记录设备发给音响的声音，包含演奏和音效。最长8秒；8kHz压缩录音，适合回听与验证。")
            val seconds=(view.status?.samples?:0)/8000f
            Text("%.1f / 8.0 秒".format(seconds),color=Aqua,style=MaterialTheme.typography.headlineMedium)
            LinearProgressIndicator(progress={seconds/8f},modifier=Modifier.fillMaxWidth())
            Row(horizontalArrangement=Arrangement.spacedBy(9.dp)){
                Button(onClick={controller?.record()},enabled=enabled && view.status?.recording!=true){Text("开始录音")}
                OutlinedButton(onClick={controller?.stopRecord()},enabled=enabled && view.status?.recording==true){Text("停止")}}
            Button(onClick={controller?.download()},enabled=enabled && view.status?.ready==true,modifier=Modifier.fillMaxWidth()){Text("回传到手机")}
            HintLine("蓝牙串口带宽有限，8秒录音预计需约40—90秒回传；期间可取消，设备保留原录音。")
            if(view.reading){LinearProgressIndicator(progress={view.transferPercent/100f},modifier=Modifier.fillMaxWidth());Text("回传 ${view.transferPercent}%",color=Aqua);TextButton(onClick={controller?.cancelRead()}){Text("取消回传")}}
            if(view.recordingFile!=null)Row(horizontalArrangement=Arrangement.spacedBy(10.dp)){
                Button(onClick={controller?.preview()},enabled=!view.busy){Text(if(view.previewing)"停止回听" else "回听")}
                OutlinedButton(onClick={controller?.share()},enabled=!view.busy){Text("导出 WAV")}}
        }
    }
    if(zoom)androidx.compose.ui.window.Dialog(onDismissRequest={zoom=false},properties=androidx.compose.ui.window.DialogProperties(usePlatformDefaultWidth=false)) {
        Surface(color=Navy,modifier=Modifier.fillMaxSize()) {Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing).padding(12.dp)){
            ScopeWorkbench(view,controller,onMicrophone,fullScreen=true,onClose={zoom=false})
        }}
    }
    if(editPad>=0)AlertDialog(onDismissRequest={editPad=-1},containerColor=CardBlue,
        title={Text("琴片 ${editPad+1} 的音高",color=White)},text={Column{
            Text("选择要放在这里的音级，原位置会自动交换。",color=Muted)
            Row(horizontalArrangement=Arrangement.spacedBy(3.dp)){repeat(7){degree->
                FilterChip(editKey==degree,onClick={editKey=degree},label={Text("${degree+1}")})}}
        }},confirmButton={TextButton(onClick={controller?.editMap(editPad,editKey);editPad=-1}){Text("交换")}},
        dismissButton={TextButton(onClick={editPad=-1}){Text("取消")}})
    Spacer(Modifier.height(12.dp));HintLine(if(connected || view.liveMic)view.message else "手机现场收音可直接使用；设备快照、琴键设置和设备录音需连接配套固件。")
    if(view.busy && !view.reading && !view.refreshing)LinearProgressIndicator(Modifier.fillMaxWidth().padding(top=12.dp))
}

