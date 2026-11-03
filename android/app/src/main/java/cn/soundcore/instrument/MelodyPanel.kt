package cn.soundcore.instrument

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MelodyPanel(audio:MelodyView,device:BleView,
    onRecord:()->Unit,onFinish:()->Unit,onImport:()->Unit,
    onPreview:()->Unit,onTranspose:(Int)->Unit,onTimbre:(Int)->Unit,
    onUpload:()->Unit,onCancel:()->Unit,onAction:(Int)->Unit,
    onNote:(Int,Boolean)->Unit={_,_->},onInputMode:(MelodyInput)->Unit={},
    onCancelRecognition:()->Unit={},onRecognize:(Boolean)->Unit={},onRange:(Int,Int)->Unit={_,_->},
    onSeek:(Int)->Unit={},onSelectNote:(Int)->Unit={},onOriginal:()->Unit={},
    onEdit:(Int,Int,Int)->Unit={_,_,_->},onUndo:()->Unit={},onSplit:()->Unit={},
    onMerge:()->Unit={},onDelete:()->Unit={},capture:Boolean=true,onBackToSheet:()->Unit={}) {
    val score=audio.score
    // Synthetic-trained support is a review hint, never a claim that a note is
    // wrong. Old imports, sheet results and manually edited scores are excluded.
    val weakNotes=remember(score,audio.scoreAlgorithm,audio.inputMode,audio.edited,capture){
        if(capture && !audio.edited && audio.inputMode==MelodyInput.VOCAL &&
            audio.scoreAlgorithm==BuiltinMelodyRecognition.ALGORITHM)
            score?.notes?.mapIndexedNotNull{i,n->i.takeIf{n.durationMs>=120 && n.confidence<.5f}}?:emptyList()
        else emptyList()
    }
    val events=remember(score,audio.transpose){runCatching{score?.events(audio.transpose)}.getOrNull()}
    val crc=remember(events){events?.let{MelodyWire.crc16(MelodyWire.bytes(it))}}
    val uploaded=device.uploadedScore
    val matching=events!=null && uploaded?.ready==true && uploaded.crc==crc && uploaded.count==events.size && uploaded.timbre==audio.timbre
    val active=uploaded?.let{(it.playing || it.guiding) && !it.finished}==true
    val idle=!audio.busy && !audio.recording && device.uploadProgress==null
    val editable=idle && !audio.previewing && !active
    var editor by rememberSaveable{mutableStateOf(false)}
    var input by rememberSaveable{mutableStateOf(false)}
    val pageTop=LocalPageTop.current
    val stage=if(audio.recording)1 else if(audio.busy)2 else if(score==null || input)3 else 4
    LaunchedEffect(stage){pageTop()}
    LaunchedEffect(score){if(score!=null)input=false}
    PageLead(if(capture)"录音成曲" else "曲谱已就绪",if(capture)"录下灵感，让声芯接着演奏" else audio.sourceName)

    if(audio.recording || audio.busy) {
        StudioCard {
            StudioIcon(if(audio.recording)Glyph.RECORD else Glyph.WAVE,Modifier.size(40.dp))
            Text(if(audio.recording)"正在聆听" else "正在整理旋律",color=White,style=MaterialTheme.typography.headlineMedium)
            Text(if(audio.recording)"${audio.seconds} / 180 秒" else "${audio.progress}%",color=Aqua,fontSize=28.sp)
            LinearProgressIndicator(progress={if(audio.recording)audio.level/255f else audio.progress/100f},modifier=Modifier.fillMaxWidth())
            HintLine(if(audio.recording){if(audio.level>240)"声音偏大，请稍远一点" else "结束录音后，可以先听原声再识别"}else audio.message)
            OutlinedButton(onClick=if(audio.recording)onFinish else onCancelRecognition,modifier=Modifier.fillMaxWidth()){
                Text(if(audio.recording)"结束录音" else "取消识别")}
        }
        return
    }
    if(capture && (score==null || input)) {
        StudioCard {
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                ChoiceChip("清唱 / 哼唱",audio.inputMode==MelodyInput.VOCAL,editable){onInputMode(MelodyInput.VOCAL)}
                ChoiceChip("单音乐器",audio.inputMode==MelodyInput.INSTRUMENT,editable){onInputMode(MelodyInput.INSTRUMENT)}
            }
            HintLine("内置模型在手机识别，录音无需上传；适合清晰的单一旋律。")
            Row(horizontalArrangement=Arrangement.spacedBy(10.dp)) {
                Button(onClick=onRecord,enabled=editable,modifier=Modifier.weight(1f).heightIn(min=50.dp)){StudioIcon(Glyph.RECORD,Modifier.size(18.dp),Navy);Spacer(Modifier.width(7.dp));Text("录一段")}
                OutlinedButton(onClick=onImport,enabled=editable,modifier=Modifier.weight(1f).heightIn(min=50.dp)){Text("导入音频")}
            }
        }
        if(audio.hasSource && audio.range!=null) {
            Spacer(Modifier.height(16.dp))
            StudioCard {
                Text(audio.sourceName,color=White,style=MaterialTheme.typography.titleMedium,maxLines=2)
                MelodyTimeline(audio.copy(score=null),onSeek)
                val range=audio.range
                var selected by remember(audio.sourceDurationMs,range){mutableStateOf(range.startMs.toFloat()..range.endMs.toFloat())}
                Text("${timeLabel(selected.start.toInt())} — ${timeLabel(selected.endInclusive.toInt())}",color=Aqua,fontSize=14.sp)
                RangeSlider(value=selected,onValueChange={next->
                    val a=next.start.toInt();val b=next.endInclusive.toInt()
                    selected=when{b-a<250->selected;b-a<=180000->next
                        next.start!=selected.start->a.toFloat()..(a+180000).coerceAtMost(audio.sourceDurationMs).toFloat()
                        else->(b-180000).coerceAtLeast(0).toFloat()..b.toFloat()}
                },onValueChangeFinished={onRange(selected.start.toInt(),selected.endInclusive.toInt())},
                    valueRange=0f..audio.sourceDurationMs.toFloat(),enabled=editable)
                HintLine("拖动两端选择片段，最长3分钟。")
                OutlinedButton(onClick=onOriginal,enabled=idle && !active,modifier=Modifier.fillMaxWidth()){
                    Text(if(audio.previewing && audio.originalPreview)"停止原声" else "试听原声")}
                Button(onClick={onRecognize(false)},enabled=editable,modifier=Modifier.fillMaxWidth().heightIn(min=52.dp)){Text("识别这段旋律")}
                if(score!=null)Row {
                    TextButton(onClick={onRecognize(true)},enabled=editable){Text("只更新所选部分")}
                    TextButton(onClick={input=false},enabled=editable){Text("返回已有旋律")}
                }
            }
        }
        if(audio.hasSource || audio.message!="录一段独唱或独奏，让设备接着演奏"){Spacer(Modifier.height(14.dp));HintLine(audio.message)}
        return
    }
    if(score==null)return
    StudioCard {
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
            SmallBadge(if(audio.edited)"已微调" else "旋律已生成")
            Text("${score.notes.size} 音 · ${String.format(Locale.ROOT,"%.1f",(audio.scoreRange?.durationMs?:score.durationMs)/1000f)}秒",color=Muted,fontSize=12.sp)
        }
        MelodyTimeline(audio,onSeek)
        val range=audio.range
        if(range!=null){Slider(value=audio.positionMs.coerceIn(range.startMs,range.endMs).toFloat(),
            onValueChange={onSeek(it.toInt())},valueRange=range.startMs.toFloat()..range.endMs.toFloat(),enabled=editable)
            HintLine("${timeLabel(audio.positionMs)} / ${timeLabel(range.endMs)}")}
        Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
            ChoiceChip("口琴",audio.timbre==1,editable){onTimbre(1)}
            ChoiceChip("二胡",audio.timbre==0,editable){onTimbre(0)}
        }
        Button(onClick=onPreview,enabled=idle && events!=null,modifier=Modifier.fillMaxWidth().heightIn(min=52.dp)){
            StudioIcon(if(audio.previewing)Glyph.STOP else Glyph.PLAY,Modifier.size(19.dp),Navy);Spacer(Modifier.width(8.dp));Text(if(audio.previewing)"停止试听" else "手机试听")}
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
            TextButton(onClick={editor=true},enabled=editable){Text("微调音符与音域")}
            TextButton(onClick={if(capture)input=true else onBackToSheet()},enabled=editable){Text(if(capture)"更换 / 重选片段" else "返回曲谱")}
        }
        if(weakNotes.isNotEmpty())HintLine("部分音高证据偏弱，可在微调中对照原声核对。")
        HintLine(audio.message)
    }
    Spacer(Modifier.height(20.dp));SectionHeader("在声芯上演奏")
    if(!device.connected)ConnectionHint()
    else StudioCard {
        if(device.uploadProgress!=null){
            Text("正在传入 · ${device.uploadProgress}%",color=Aqua)
            LinearProgressIndicator(progress={device.uploadProgress/100f},modifier=Modifier.fillMaxWidth())
            TextButton(onClick=onCancel){Text("取消传输")}
        } else {
            Text(if(matching)"旋律已在设备上" else "将旋律传入声芯",color=White,style=MaterialTheme.typography.titleMedium)
            HintLine(if(matching)"可以聆听，也可以跟随亮灯演奏。" else "传输完成后，手机与OLED会同步显示演奏进度。")
            if(!matching)Button(onClick=onUpload,enabled=editable && events!=null && audio.canUpload && device.pitchLayout!=null && device.state?.writeAllowed==true && device.scoreSupported==true,modifier=Modifier.fillMaxWidth()){Text("传入设备")}
            if(events==null)HintLine("部分音符超出设备音域，请先点“微调音符与音域”。")
            if(device.scoreSupported==false)HintLine("当前固件不支持曲谱传输，请更新设备固件。")
        }
        if(matching) {
            if(active){
                Text(if(uploaded!!.paused)"已暂停" else if(uploaded.guiding)"跟随亮灯演奏" else "声芯正在演奏",color=Aqua)
                LinearProgressIndicator(progress={(uploaded.step.toFloat()/maxOf(1,uploaded.count)).coerceIn(0f,1f)},modifier=Modifier.fillMaxWidth())
                HintLine("${uploaded.step} / ${uploaded.count} · "+(uploaded.noteIndex?.let{PitchLayout.name(it+36)}?:"休止"))
                if(uploaded.guiding)PadArc(!uploaded.paused,uploaded.pad,device.state?.padMask?:0,device.state?.writeAllowed==true && !uploaded.paused,onNote=onNote)
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                    Button(onClick={onAction(if(uploaded.paused)3 else 2)},modifier=Modifier.weight(1f)){Text(if(uploaded.paused)"继续" else "暂停")}
                    OutlinedButton(onClick={onAction(0)},modifier=Modifier.weight(1f)){Text("结束")}
                }
            } else Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                Button(onClick={onAction(1)},enabled=idle,modifier=Modifier.weight(1f)){Text("整段演奏")}
                OutlinedButton(onClick={onAction(4)},enabled=idle,modifier=Modifier.weight(1f)){Text("亮灯跟弹")}
            }
        }
        if(device.scoreMessage.isNotBlank())HintLine(device.scoreMessage)
    }
    if(editor)ModalBottomSheet(onDismissRequest={editor=false},containerColor=CardBlue){
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal=22.dp).padding(bottom=32.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
            Text("微调旋律",color=White,style=MaterialTheme.typography.headlineMedium)
            Text("整体音域",color=White,style=MaterialTheme.typography.titleMedium)
            HintLine(if(audio.transpose==0)"保留原调" else "整体${if(audio.transpose>0)"升" else "降"}${kotlin.math.abs(audio.transpose)}个半音")
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                ChoiceChip("原调",audio.transpose==0,editable){onTranspose(0)}
                ChoiceChip("适配设备",audio.transpose!=0,editable && score.suggestedTranspose!=null){score.suggestedTranspose?.let(onTranspose)}
            }
            Text("逐音核对",color=White,style=MaterialTheme.typography.titleMedium)
            if(weakNotes.isNotEmpty())TextButton(onClick={onSelectNote(weakNotes.firstOrNull{it>audio.selectedNote}?:weakNotes.first())},enabled=editable){Text("定位证据较弱的音")}
            LazyRow(horizontalArrangement=Arrangement.spacedBy(7.dp)){
                itemsIndexed(score.notes){i,n->ChoiceChip("${i+1} · ${MelodyWorkspace.noteName(n.midi)}",i==audio.selectedNote,editable){onSelectNote(i)}}}
            val note=score.notes.getOrNull(audio.selectedNote)
            if(note==null)HintLine("先选择一个音符。") else {
                SmallBadge("第${audio.selectedNote+1}音 · ${MelodyWorkspace.noteName(note.midi)} · ${note.durationMs}ms",Gold)
                if(audio.selectedNote in weakNotes)HintLine("当前音高证据偏弱，可先听原声再决定是否修改。")
                EditPair("降半音","升半音",{onEdit(-1,0,0)},{onEdit(1,0,0)})
                EditPair("缩短50ms","延长50ms",{onEdit(0,-50,0)},{onEdit(0,50,0)})
                EditPair("提前50ms","延后50ms",{onEdit(0,0,-50)},{onEdit(0,0,50)})
                Row{TextButton(onClick=onSplit){Text("拆分")};TextButton(onClick=onMerge){Text("合并后音")};TextButton(onClick=onDelete,enabled=score.notes.size>1){Text("删除")}}
                TextButton(onClick=onUndo,enabled=audio.undoAvailable){Text("撤销上一步")}
            }
            Button(onClick={editor=false},modifier=Modifier.fillMaxWidth()){Text("完成微调")}
        }
    }
}

@Composable private fun EditPair(a:String,b:String,onA:()->Unit,onB:()->Unit){Row(horizontalArrangement=Arrangement.spacedBy(9.dp)){
    OutlinedButton(onClick=onA,modifier=Modifier.weight(1f)){Text(a)};OutlinedButton(onClick=onB,modifier=Modifier.weight(1f)){Text(b)}}}

@Composable private fun MelodyTimeline(audio:MelodyView,onSeek:(Int)->Unit) {
    Canvas(Modifier.fillMaxWidth().height(95.dp).pointerInput(audio.score,audio.range){detectTapGestures{pos->
        val range=audio.range;if(audio.score!=null && range!=null && !audio.busy && !audio.previewing)onSeek(range.startMs+(pos.x/size.width*range.durationMs).toInt())
    }}){
        val score=audio.score
        for(i in 1..3)drawLine(BorderBlue.copy(alpha=.3f),Offset(0f,i*size.height/4),Offset(size.width,i*size.height/4),1f)
        if(score==null)audio.waveform.forEachIndexed{i,v->
            val h=maxOf(3f,v*size.height*.8f);val t=i.toFloat()/maxOf(1,audio.waveform.size)*audio.sourceDurationMs
            val selected=audio.range?.let{t>=it.startMs && t<=it.endMs}==true
            drawRoundRect(Aqua.copy(alpha=if(selected).8f else .18f),Offset(i*size.width/maxOf(1,audio.waveform.size),(size.height-h)/2),Size(maxOf(1f,size.width/maxOf(1,audio.waveform.size)-1),h),CornerRadius(2f))
        } else {
            val begin=audio.range?.startMs?:score.firstMs;val span=maxOf(1,audio.range?.durationMs?:score.durationMs)
            val lo=score.notes.minOf{it.midi};val hi=score.notes.maxOf{it.midi}
            score.notes.forEachIndexed{i,n->
                val x=(n.startMs-begin).toFloat()/span*size.width;val w=n.durationMs.toFloat()/span*size.width
                val y=10+(hi-n.midi).toFloat()/maxOf(1,hi-lo)*(size.height-25)
                if(x+w>=0 && x<size.width)drawRoundRect(if(i==audio.selectedNote)Gold else Aqua,Offset(x.coerceAtLeast(0f),y),Size(maxOf(2f,minOf(size.width-x,w)-2),8f),CornerRadius(3f))
            }
            val position=(audio.positionMs-begin).toFloat()/span*size.width
            if(position in 0f..size.width)drawLine(White.copy(alpha=.8f),Offset(position,0f),Offset(position,size.height),2f)
        }
    }
}
private fun timeLabel(ms:Int)=String.format(Locale.ROOT,"%02d:%02d.%01d",ms/60000,ms/1000%60,ms/100%10)
