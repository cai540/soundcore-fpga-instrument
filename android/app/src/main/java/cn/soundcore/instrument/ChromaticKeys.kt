package cn.soundcore.instrument

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Seven concurrent owner slots, twelve exact pitch choices. Never a tap FIFO. */
@Composable
internal fun ChromaticKeys(bank:Int,key:Int,enabled:Boolean,onNote:(Int,Boolean)->Unit) {
    BoxWithConstraints(Modifier.fillMaxWidth().height(160.dp).padding(vertical=10.dp)) {
        val width=(maxWidth-18.dp)/7
        val base=bank*12+key
        listOf(0,2,4,5,7,9,11).forEachIndexed{degree,offset->
            ChromaticKey(base+offset,"${degree+1}",false,enabled,
                Modifier.offset(x=(width+3.dp)*degree).width(width).height(140.dp),onNote)
        }
        listOf(1,3,6,8,10).forEachIndexed{order,offset->
            val left=listOf(0,1,3,4,5)[order]
            ChromaticKey(base+offset,listOf("#1","#2","#4","#5","#6")[order],true,enabled,
                Modifier.offset(x=(width+3.dp)*(left+1)-width*.34f).width(width*.68f).height(90.dp),onNote)
        }
    }
}

@Composable private fun ChromaticKey(index:Int,label:String,accidental:Boolean,enabled:Boolean,
    modifier:Modifier,onNote:(Int,Boolean)->Unit) {
    val send by rememberUpdatedState(onNote)
    var pressed by remember(index){mutableStateOf(false)}
    Column(modifier.background(if(pressed)Aqua else if(accidental)Navy else RaisedBlue,RoundedCornerShape(7.dp))
        .border(1.dp,if(pressed)Aqua else BorderBlue,RoundedCornerShape(7.dp))
        .semantics{contentDescription="$label ${PitchLayout.name(index+36)}"}
        .pointerInput(enabled,index){if(enabled)detectTapGestures(onPress={
            pressed=true;send(index,true)
            try{tryAwaitRelease()}finally{pressed=false;send(index,false)}
        })}.padding(bottom=12.dp),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.Bottom) {
        Text(label,color=if(pressed)Navy else White,fontSize=if(accidental)11.sp else 15.sp)
        Spacer(Modifier.height(5.dp));Text(PitchLayout.name(index+36),color=if(pressed)Navy else Muted,fontSize=8.sp)
    }
}
