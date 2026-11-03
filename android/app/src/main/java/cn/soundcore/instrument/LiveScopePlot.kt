package cn.soundcore.instrument

import android.graphics.Paint
import android.graphics.Typeface
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.*
import androidx.compose.ui.unit.dp
import kotlin.math.*

/** Instrument-style graticule; units describe the actual source, never inferred volts. */
@Composable
internal fun LiveScopePlot(kind:Int,frame:LiveAudioFrame?,modifier:Modifier=Modifier.height(300.dp),settings:ScopeSettings=ScopeSettings()) {
    val paint=remember{Paint(Paint.ANTI_ALIAS_FLAG).apply{typeface=Typeface.create(Typeface.MONOSPACE,Typeface.NORMAL)}}
    Canvas(Modifier.fillMaxWidth().then(modifier).background(Color(0xff07131d),RoundedCornerShape(14.dp))){
        val left=43.dp.toPx();val top=28.dp.toPx();val w=size.width-left-15.dp.toPx();val h=size.height-top-29.dp.toPx()
        if(w<=0 || h<=0)return@Canvas
        fun label(text:String,x:Float,y:Float,color:Color=Muted,small:Boolean=false){paint.color=color.toArgb();paint.textSize=(if(small)9 else 10).dp.toPx();drawContext.canvas.nativeCanvas.drawText(text,x,y,paint)}
        val signal=if(kind==1)Color(0xffffcb70)else Aqua
        clipRect(left,top,left+w,top+h){
            repeat(51){i->val x=left+w*i/50;drawLine(BorderBlue.copy(alpha=if(i%5==0).55f else .15f),Offset(x,top),Offset(x,top+h),if(i%5==0)1f else .6f)}
            repeat(41){i->val y=top+h*i/40;drawLine(BorderBlue.copy(alpha=if(i%5==0).55f else .15f),Offset(left,y),Offset(left+w,y),if(i%5==0)1f else .6f)}
            drawLine(Muted.copy(alpha=.45f),Offset(left,top+h/2),Offset(left+w,top+h/2))
        }
        label(when(kind){0->"CH1 · FS";1->"FFT · dBFS";else->"X(t) / Y(t−τ) · FS"},left,17.dp.toPx(),signal)
        if(frame==null){label("WAITING FOR AUDIO",left+8.dp.toPx(),top+h/2);return@Canvas}
        val window=ScopeMath.window(frame,settings);val data=frame.samples
        val bias=if(settings.ac)frame.dc else 0f
        fun y(v:Float)=top+h/2-(v-bias)/(settings.fsPerDiv*8)*h
        val path=Path()
        clipRect(left,top,left+w,top+h){
            when(kind){
                0->{
                    val columns=min(w.roundToInt(),window.count).coerceAtLeast(1)
                    if(window.count>columns*2){repeat(columns){i->
                        val a=window.start+i*window.count/columns;val b=window.start+(i+1)*window.count/columns
                        var lo=Float.POSITIVE_INFINITY;var hi=Float.NEGATIVE_INFINITY
                        for(k in a until b){lo=min(lo,data[k]);hi=max(hi,data[k])}
                        val x=left+(i+.5f)*w/columns;drawLine(signal,Offset(x,y(lo)),Offset(x,y(hi)),1.dp.toPx())
                    }}else for(i in 0 until window.count){val x=left+i*w/(window.count-1);val py=y(data[window.start+i]);if(i==0)path.moveTo(x,py)else path.lineTo(x,py)}
                    val tx=left+w*.2f;val ty=y(settings.trigger+bias)
                    drawLine(Gold.copy(alpha=.45f),Offset(left,ty),Offset(left+w,ty),pathEffect=PathEffect.dashPathEffect(floatArrayOf(6f,6f)))
                    drawLine(Gold.copy(alpha=.35f),Offset(tx,top),Offset(tx,top+h),pathEffect=PathEffect.dashPathEffect(floatArrayOf(4f,8f)))
                }
                1->{
                    val low=if(settings.focusedSpectrum)200f else 0f;val high=if(settings.focusedSpectrum)1800f else min(12000f,frame.sampleRate/2f)
                    val columns=min(w.roundToInt(),frame.spectrum.size).coerceAtLeast(1)
                    repeat(columns){i->
                        val a=max(1,((low+(high-low)*i/columns)*frame.fftSize/frame.sampleRate).toInt()).coerceAtMost(frame.spectrum.lastIndex)
                        val b=max(a+1,((low+(high-low)*(i+1)/columns)*frame.fftSize/frame.sampleRate).toInt()).coerceAtMost(frame.spectrum.size)
                        val db=(a until b).maxOf{frame.spectrum[it]}.coerceIn(-100f,0f)
                        val x=left+i*w/(columns-1).coerceAtLeast(1);val py=top-db*h/100
                        if(i==0)path.moveTo(x,py)else path.lineTo(x,py)
                    }
                    var prior=Float.NEGATIVE_INFINITY
                    frame.peaks.filter{it.hz in low..high}.take(6).sortedBy{it.hz}.forEach{p->
                        val x=left+(p.hz-low)/(high-low)*w
                        if(x-prior>65.dp.toPx()){drawCircle(signal,2.dp.toPx(),Offset(x,top-p.dbFs.coerceIn(-100f,0f)*h/100));label("%.0f Hz".format(p.hz),x-18.dp.toPx(),top+12.dp.toPx(),signal,true);prior=x}
                    }
                }
                2->{val delay=ScopeMath.delay(frame,settings);val start=max(delay,data.size-4096);val step=max(1,(data.size-start)/1400)
                    var first=true
                    for(i in start until data.size step step){val x=left+w/2+(data[i]-bias)/(settings.fsPerDiv*10)*w;val py=y(data[i-delay]);if(first){path.moveTo(x,py);first=false}else path.lineTo(x,py)}
                }
            }
            drawPath(path,signal.copy(alpha=.13f),style=Stroke(5.dp.toPx(),cap=StrokeCap.Round,join=StrokeJoin.Round))
            drawPath(path,signal,style=Stroke(1.2.dp.toPx(),cap=StrokeCap.Round,join=StrokeJoin.Round))
        }
        repeat(5){i->val t=i/4f
            label(if(kind==1)"${(-100*t).roundToInt()}"else "%.2f".format((.5f-t)*8*settings.fsPerDiv),2.dp.toPx(),top+h*t+3.dp.toPx(),small=true)
        }
        repeat(6){i->val t=i/5f
            val text=when(kind){
                0->"%.1f".format((t-.2f)*window.milliseconds(frame.sampleRate))
                1->{val lo=if(settings.focusedSpectrum)200f else 0f;val hi=if(settings.focusedSpectrum)1800f else min(12000f,frame.sampleRate/2f);val hz=lo+(hi-lo)*t;if(hz>=1000)"%.1fk".format(hz/1000)else "%.0f".format(hz)}
                else->"%.2f".format((t-.5f)*10*settings.fsPerDiv)
            }
            label(text,(left+w*t-10.dp.toPx()).coerceAtMost(size.width-30.dp.toPx()),top+h+15.dp.toPx(),small=true)
        }
        label(when(kind){0->if(window.triggered)if(settings.rising)"T ↑"else "T ↓"else "AUTO";1->"Hz";else->"FS"},left+w-30.dp.toPx(),17.dp.toPx(),if(window.triggered)Gold else Muted)
    }
}

/** FPGA sends 32 min/max pairs, 32 log bands or 32 XY pairs, not full-rate PCM. */
@Composable
internal fun AudioAnalysisPlot(kind:Int,data:ByteArray,modifier:Modifier=Modifier.height(300.dp)){
    val paint=remember{Paint(Paint.ANTI_ALIAS_FLAG).apply{typeface=Typeface.MONOSPACE}}
    Canvas(Modifier.fillMaxWidth().then(modifier).background(Color(0xff07131d),RoundedCornerShape(14.dp))){
        val l=37.dp.toPx();val t=26.dp.toPx();val w=size.width-l-12.dp.toPx();val h=size.height-t-30.dp.toPx()
        fun label(text:String,x:Float,y:Float,c:Color=Muted){paint.color=c.toArgb();paint.textSize=9.dp.toPx();drawContext.canvas.nativeCanvas.drawText(text,x,y,paint)}
        repeat(11){val x=l+w*it/10;drawLine(BorderBlue.copy(alpha=.4f),Offset(x,t),Offset(x,t+h))}
        repeat(9){val y=t+h*it/8;drawLine(BorderBlue.copy(alpha=.4f),Offset(l,y),Offset(l+w,y))}
        label(if(kind==1)"FPGA FFT · RELATIVE LEVEL"else "FPGA PCM · NORMALIZED",l,16.dp.toPx(),Aqua)
        if(data.isEmpty()){label("WAITING FOR DEVICE",l+8.dp.toPx(),t+h/2);return@Canvas}
        fun v(i:Int)=data[i].toInt()and 255
        val path=Path()
        clipRect(l,t,l+w,t+h){when(kind){
            0->if(data.size==64)repeat(32){i->val x=l+(i+.5f)*w/32;drawLine(Aqua,Offset(x,t+v(i*2)/47f*h),Offset(x,t+v(i*2+1)/47f*h),2.dp.toPx())}
            1->if(data.size==32)repeat(32){i->val height=v(i).coerceAtMost(48)/48f*h;drawRect(Gold,Offset(l+i*w/32+1,t+h-height),Size(max(1f,w/32-2),height))}
            2->if(data.size==64){repeat(32){i->val x=l+v(i*2)/127f*w;val y=t+v(i*2+1)/47f*h;if(i==0)path.moveTo(x,y)else path.lineTo(x,y)};drawPath(path,Aqua,style=Stroke(1.5.dp.toPx()))}
        }}
        when(kind){
            0->{label("+1",2.dp.toPx(),t+10.dp.toPx());label("0",4.dp.toPx(),t+h/2);label("−1",2.dp.toPx(),t+h);listOf("0","5.3","10.7","16.0","21.3 ms").forEachIndexed{i,s->label(s,l+w*i/4-(if(i==4)38.dp.toPx()else 0f),t+h+17.dp.toPx())}}
            1->{listOf("47","188","750","3k","12k Hz").forEachIndexed{i,s->label(s,l+w*i/4-(if(i==4)35.dp.toPx()else 0f),t+h+17.dp.toPx())};label("48",2.dp.toPx(),t+10.dp.toPx());label("0",4.dp.toPx(),t+h)}
            2->{label("X(t)",l+w/2,t+h+17.dp.toPx());label("Y",4.dp.toPx(),t+h/2)}
        }
    }
}
