package cn.soundcore.instrument

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import kotlin.math.*

@Composable
internal fun ScopeWorkbench(view:ProductToolsView,controller:ProductToolsController?,onMicrophone:(Boolean)->Unit,onExpand:(()->Unit)?=null,fullScreen:Boolean=false,onClose:(()->Unit)?=null){
    val s=view.scope;val f=view.liveFrame
    var settingsOpen by remember{mutableStateOf(false)}
    Column(Modifier.fillMaxWidth().then(if(fullScreen)Modifier.fillMaxHeight()else Modifier)){
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){
            Text("声音示波器",color=White,style=MaterialTheme.typography.titleLarge)
            Text(when(s.state){1->"● HOLD";2->"● ARMED";3->"● SINGLE";else->"● RUN"},color=if(s.state==0)Aqua else Gold,fontFamily=FontFamily.Monospace)
            if(onClose!=null)TextButton(onClick=onClose,contentPadding=PaddingValues(0.dp)){Text("关闭")}
        }
        BoxWithConstraints(Modifier.fillMaxWidth()){
            if(maxWidth>=600.dp)Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                ScopeSources(view,onMicrophone);ScopeModes(view,controller)
            }else Column{
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){ScopeSources(view,onMicrophone)}
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){ScopeModes(view,controller)}
            }
        }
        val graph=if(fullScreen)Modifier.weight(1f).heightIn(min=110.dp)else Modifier.height(300.dp)
        if(view.liveMic)LiveScopePlot(view.plotKind,f,graph,s)else AudioAnalysisPlot(view.plotKind,view.plot,graph)
        if(view.liveMic){
            val peak=f?.peaks?.firstOrNull()?.hz
            Row(Modifier.fillMaxWidth().padding(top=10.dp),horizontalArrangement=Arrangement.SpaceBetween){
                ScopeMetric("主峰",peak?.let{"%.1f Hz".format(it)}?:"—")
                ScopeMetric("RMS",f?.let{"%.1f dBFS".format(it.rmsDb)}?:"—")
                ScopeMetric("峰值",f?.let{"%.3f FS".format(it.peak)}?:"—")
            }
            val range=f?.let{ScopeMath.window(it,s).milliseconds(it.sampleRate)/10}?:s.msPerDiv
            HintLine(when(view.plotKind){
                0->"%.2f ms/div · %.2f FS/div · %s · %s".format(range,s.fsPerDiv,if(s.ac)"AC"else "DC",if(s.rising)"上升沿触发"else "下降沿触发")
                1->f?.let{"Hann · ${it.fftSize}点 · Δf %.2f Hz · 窗长 %.1f ms".format(it.sampleRate.toFloat()/it.fftSize,it.fftSize*1000f/it.sampleRate)}?:"等待真实音频采样"
                else->f?.let{"单声道延迟投影 · τ %.3f ms · 非双通道相位仪".format(ScopeMath.delay(it,s)*1000f/it.sampleRate)}?:"X(t) 与 X(t−τ)，非独立双通道"
            })
        }else HintLine("FPGA 快照 #${view.plotFrame} · 回传 ${view.refreshMs} ms · ${if(view.plotKind==1)"32 对数频带，非32声部计数"else if(view.plotKind==2)"Y 延迟64采样，单声道投影"else "32组极值，约21.3ms窗口"}")
        Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(7.dp)){
            OutlinedButton(onClick={controller?.scope(s.copy(state=if(s.state in listOf(1,3))0 else 1))}){Text(if(s.state in listOf(1,3))"运行"else "冻结")}
            if(view.liveMic){
                OutlinedButton(onClick={controller?.scope(s.copy(state=2))}){Text("单次")}
                OutlinedButton(onClick={controller?.autoScope()}){Text("自动量程")}
                OutlinedButton(onClick={settingsOpen=true}){Text("调节")}
                OutlinedButton(onClick={controller?.exportScope()},enabled=f!=null && !view.scopeExporting){Text("导出")}
            }else OutlinedButton(onClick={controller?.snapshot(view.plotKind)},enabled=!view.busy){Text("采集一次")}
            if(onExpand!=null)TextButton(onClick=onExpand){Text("全屏 ↗")}
        }
        if(!fullScreen){
            val age=if(f?.timestampReliable==true && s.state==0)((System.nanoTime()-f.capturedNs)/1e6).takeIf{it in 0.0..10000.0}?.let{"采样年龄 %.0fms".format(it)} else null
            HintLine(if(view.liveMic)"${f?.sampleRate?.div(1000f)?:48f}kHz · FFT ${f?.analysisMs?.let{"%.1f".format(it)}?:"—"}ms${age?.let{" · $it"}?:""} · ${if((f?.peak?:0f)>=.98f)"输入削顶"else "手机麦克风"}" else "原始分析在FPGA中生成；串口带宽限制刷新率。快速观察可切换麦克风实时。")
        }
    }
    if(settingsOpen)AlertDialog(onDismissRequest={settingsOpen=false},containerColor=CardBlue,
        title={Text("采集与触发",color=White)},text={Column{
            Text("时基：${s.msPerDiv} ms/div",color=Aqua)
            val times=listOf(.2f,.5f,1f,2f,5f,10f,20f)
            Slider(times.indexOf(s.msPerDiv).coerceAtLeast(0).toFloat(),onValueChange={controller?.scope(s.copy(msPerDiv=times[it.roundToInt()]))},valueRange=0f..6f,steps=5)
            Text("增益：${s.fsPerDiv} FS/div",color=Aqua)
            val gains=listOf(.01f,.02f,.05f,.1f,.2f,.25f,.5f)
            Slider(gains.indexOf(s.fsPerDiv).coerceAtLeast(0).toFloat(),onValueChange={controller?.scope(s.copy(fsPerDiv=gains[it.roundToInt()]))},valueRange=0f..6f,steps=5)
            Text("触发电平：%.2f FS".format(s.trigger),color=Aqua)
            Slider(s.trigger,onValueChange={controller?.scope(s.copy(trigger=it))},valueRange=-.8f..0.8f)
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                FilterChip(s.rising,onClick={controller?.scope(s.copy(rising=!s.rising))},label={Text(if(s.rising)"上升沿"else "下降沿")})
                FilterChip(s.ac,onClick={controller?.scope(s.copy(ac=!s.ac))},label={Text(if(s.ac)"AC 耦合"else "DC 耦合")})
            }
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("高分辨率频谱",color=White,modifier=Modifier.padding(top=12.dp));Switch(s.highResolution,onCheckedChange={controller?.scope(s.copy(highResolution=it))})}
            HintLine("快速4096点；精细16384点。48kHz时分辨率约2.93Hz，窗长341ms；窗长不代表演奏延迟。")
            FilterChip(s.focusedSpectrum,onClick={controller?.scope(s.copy(focusedSpectrum=!s.focusedSpectrum))},label={Text("聚焦 200—1800 Hz")})
            Text("XY 延迟：${if(s.xyDelayMs==0f)"主峰的1/4周期"else "${s.xyDelayMs} ms"}",color=Aqua)
            Slider(s.xyDelayMs,onValueChange={controller?.scope(s.copy(xyDelayMs=it))},valueRange=0f..5f)
        }},confirmButton={TextButton(onClick={settingsOpen=false}){Text("完成")}})
}

@Composable private fun ScopeMetric(label:String,value:String){Column{Text(label,color=Muted,style=MaterialTheme.typography.labelSmall);Text(value,color=White,fontFamily=FontFamily.Monospace,style=MaterialTheme.typography.titleSmall)}}

@Composable private fun ScopeSources(view:ProductToolsView,onMicrophone:(Boolean)->Unit){
    FilterChip(!view.liveMic,onClick={onMicrophone(false)},label={Text("FPGA 输出")})
    FilterChip(view.liveMic,onClick={onMicrophone(true)},label={Text("麦克风实时")})
}
@Composable private fun ScopeModes(view:ProductToolsView,controller:ProductToolsController?){
    listOf("波形","频谱","XY 相图").forEachIndexed{i,label->FilterChip(view.plotKind==i,onClick={controller?.snapshot(i)},label={Text(label)})}
}
