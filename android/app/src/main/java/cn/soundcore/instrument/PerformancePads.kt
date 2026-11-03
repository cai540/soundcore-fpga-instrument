package cn.soundcore.instrument

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Each pad owns its pointer lifetime; no queued musical notes are introduced here. */
@Composable
fun PadArc(guideRunning:Boolean,target:Int,activeMask:Int=0,enabled:Boolean=false,
    noteLabels:List<String>?=null,degrees:List<Int>?=null,
    onNote:(Int,Boolean)->Unit={_,_->}) {
    val send by rememberUpdatedState(onNote)
    val scope=rememberCoroutineScope()
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val diameter=((maxWidth-24.dp)/7).coerceAtMost(49.dp)
        Row(Modifier.fillMaxWidth().height(115.dp),horizontalArrangement=Arrangement.spacedBy(4.dp)) {
            repeat(7){index ->
                var pressed by remember(index){mutableStateOf(false)}
                val targetNow=guideRunning && target==index
                val sounding=activeMask and (1 shl index)!=0
                val y=when(index){0,6->24.dp;1,5->10.dp;else->0.dp}
                Column(Modifier.weight(1f).fillMaxHeight()
                    .semantics {contentDescription="琴键${index+1}";role=Role.Button
                        if(enabled)onClick("演奏"){send(index,true);scope.launch{try{delay(100)}finally{send(index,false)}};true}}
                    .pointerInput(enabled,index){if(enabled)detectTapGestures(onPress={
                        pressed=true;send(index,true)
                        try{tryAwaitRelease()}finally{pressed=false;send(index,false)}
                    })},horizontalAlignment=Alignment.CenterHorizontally) {
                    Spacer(Modifier.height(y+10.dp))
                    Box(Modifier.size(diameter)
                        .background(if(pressed || sounding)Aqua else if(targetNow)Gold.copy(alpha=.18f) else RaisedBlue,CircleShape)
                        .border(if(targetNow)2.dp else 1.dp,if(targetNow)Gold else Aqua.copy(alpha=.45f),CircleShape),
                        contentAlignment=Alignment.Center) {
                        Text("${(degrees?.getOrNull(index)?:index)+1}",color=if(pressed||sounding)Navy else if(targetNow)Gold else White,
                            fontSize=19.sp,fontWeight=FontWeight.SemiBold)
                    }
                    Spacer(Modifier.height(8.dp))
                    Box(Modifier.size(3.dp).background(if(targetNow)Gold else if(pressed||sounding)Aqua else BorderBlue,CircleShape))
                    noteLabels?.getOrNull(index)?.let{label->
                        Spacer(Modifier.height(6.dp));Text(label,color=Muted,fontSize=9.sp)
                    }
                }
            }
        }
    }
}
