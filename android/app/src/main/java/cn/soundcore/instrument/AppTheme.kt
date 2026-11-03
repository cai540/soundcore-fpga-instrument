package cn.soundcore.instrument

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

internal val Navy = Color(0xFF09171F)
internal val CardBlue = Color(0xFF112A35)
internal val RaisedBlue = Color(0xFF1B3945)
internal val BorderBlue = Color(0xFF294852)
internal val Aqua = Color(0xFF62DFC7)
internal val Gold = Color(0xFFE4BC89)
internal val White = Color(0xFFF1F5F0)
internal val Muted = Color(0xFF91A8B1)
internal val LocalDeviceNavigation = staticCompositionLocalOf<() -> Unit> { {} }
internal val LocalPageTop = staticCompositionLocalOf<() -> Unit> { {} }

@Composable
fun SoundcoreTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(primary=Aqua,onPrimary=Navy,secondary=Gold,onSecondary=Navy,
            primaryContainer=Color(0xFF19463F),onPrimaryContainer=White,secondaryContainer=RaisedBlue,onSecondaryContainer=White,
            background=Navy,onBackground=White,surface=CardBlue,onSurface=White,
            surfaceContainerLowest=Navy,surfaceContainerLow=CardBlue,surfaceContainer=CardBlue,
            surfaceContainerHigh=RaisedBlue,surfaceContainerHighest=BorderBlue,outlineVariant=BorderBlue,
            surfaceVariant=RaisedBlue,onSurfaceVariant=Muted,outline=BorderBlue,error=Color(0xFFFF9C92)),
        typography = Typography(
            headlineLarge=TextStyle(fontFamily=FontFamily.SansSerif,fontWeight=FontWeight.Bold,fontSize=32.sp,lineHeight=41.sp),
            headlineMedium=TextStyle(fontWeight=FontWeight.SemiBold,fontSize=26.sp,lineHeight=35.sp),
            titleLarge=TextStyle(fontWeight=FontWeight.SemiBold,fontSize=21.sp,lineHeight=29.sp),
            titleMedium=TextStyle(fontWeight=FontWeight.SemiBold,fontSize=16.sp,lineHeight=24.sp),
            bodyLarge=TextStyle(fontSize=16.sp,lineHeight=25.sp),
            bodyMedium=TextStyle(fontSize=14.sp,lineHeight=22.sp),
            bodySmall=TextStyle(fontSize=12.sp,lineHeight=19.sp),
            labelLarge=TextStyle(fontWeight=FontWeight.SemiBold,fontSize=14.sp,lineHeight=20.sp),
            labelSmall=TextStyle(fontSize=11.sp,lineHeight=16.sp)),
        shapes=Shapes(small=RoundedCornerShape(12.dp),medium=RoundedCornerShape(18.dp),large=RoundedCornerShape(26.dp)),
        content=content)
}

internal enum class Glyph { PADS, LIBRARY, CREATE, VOICE, DEVICE, PLAY, PAUSE, STOP, BACK, ARROW, RECORD, IMAGE, UPLOAD, WAVE, CHECK, MORE, REFRESH }

@Composable
internal fun StudioIcon(kind: Glyph, modifier: Modifier=Modifier, tint: Color=Aqua) {
    Canvas(modifier.size(24.dp)) {
        val u=size.minDimension/24f
        fun line(x:Float,y:Float,a:Float,b:Float)=drawLine(tint,Offset(x*u,y*u),Offset(a*u,b*u),1.7f*u)
        fun circle(x:Float,y:Float,r:Float,filled:Boolean=false)=drawCircle(tint,r*u,Offset(x*u,y*u),style=if(filled) androidx.compose.ui.graphics.drawscope.Fill else Stroke(1.6f*u))
        when(kind) {
            Glyph.PLAY -> drawPath(Path().apply{moveTo(8*u,5*u);lineTo(20*u,12*u);lineTo(8*u,19*u);close()},tint)
            Glyph.PAUSE -> {drawRoundRect(tint,Offset(6*u,5*u),Size(4*u,14*u));drawRoundRect(tint,Offset(14*u,5*u),Size(4*u,14*u))}
            Glyph.STOP -> drawRoundRect(tint,Offset(6*u,6*u),Size(12*u,12*u))
            Glyph.BACK -> {line(15f,5f,8f,12f);line(8f,12f,15f,19f)}
            Glyph.ARROW -> {line(9f,5f,16f,12f);line(16f,12f,9f,19f)}
            Glyph.PADS -> {for(i in 0..2){circle(5f+i*7,8f,2.5f);circle(5f+i*7,17f,2.5f)}}
            Glyph.LIBRARY -> {line(9f,5f,19f,3f);line(9f,5f,9f,18f);line(19f,3f,19f,16f);circle(6f,18f,3f);circle(16f,16f,3f)}
            Glyph.CREATE -> {circle(12f,12f,9f);line(7f,12f,17f,12f);line(12f,7f,12f,17f)}
            Glyph.VOICE -> {for(i in 0..4){val h=floatArrayOf(5f,11f,17f,11f,5f)[i];line(4f+i*4,12-h/2,4f+i*4,12+h/2)}}
            Glyph.WAVE -> {for(i in 0..6){val h=floatArrayOf(4f,9f,16f,11f,19f,10f,4f)[i];line(3f+i*3,12-h/2,3f+i*3,12+h/2)}}
            Glyph.DEVICE -> {line(10f,2f,10f,22f);line(10f,2f,18f,8f);line(18f,8f,5f,18f);line(5f,6f,18f,16f);line(18f,16f,10f,22f)}
            Glyph.RECORD -> {drawRoundRect(tint,Offset(9*u,3*u),Size(6*u,12*u),androidx.compose.ui.geometry.CornerRadius(3*u),style=Stroke(1.7f*u));drawArc(tint,0f,180f,false,Offset(5*u,7*u),Size(14*u,12*u),style=Stroke(1.7f*u));line(12f,19f,12f,22f);line(8f,22f,16f,22f)}
            Glyph.IMAGE -> {drawRoundRect(tint,Offset(3*u,3*u),Size(18*u,18*u),androidx.compose.ui.geometry.CornerRadius(3*u),style=Stroke(1.7f*u));circle(8f,8f,1.5f);line(4f,18f,10f,12f);line(10f,12f,14f,16f);line(14f,16f,18f,11f);line(18f,11f,21f,15f)}
            Glyph.UPLOAD -> {line(12f,17f,12f,3f);line(12f,3f,6f,9f);line(12f,3f,18f,9f);line(4f,17f,4f,21f);line(4f,21f,20f,21f);line(20f,21f,20f,17f)}
            Glyph.CHECK -> {line(5f,12f,10f,17f);line(10f,17f,20f,6f)}
            Glyph.MORE -> {circle(5f,12f,1.3f,true);circle(12f,12f,1.3f,true);circle(19f,12f,1.3f,true)}
            Glyph.REFRESH -> {drawArc(tint,35f,285f,false,Offset(4*u,4*u),Size(16*u,16*u),style=Stroke(1.7f*u));line(20f,4f,20f,10f);line(20f,10f,14f,10f)}
        }
    }
}

@Composable
internal fun StudioCard(modifier:Modifier=Modifier, content:@Composable ColumnScope.()->Unit) {
    Column(modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(CardBlue)
        .border(1.dp,BorderBlue.copy(alpha=.45f),RoundedCornerShape(24.dp)).padding(20.dp),
        verticalArrangement=Arrangement.spacedBy(12.dp),content=content)
}

@Composable
internal fun PageLead(title:String,subtitle:String) {
    Text(title,color=White,style=MaterialTheme.typography.headlineLarge)
    Spacer(Modifier.height(6.dp))
    Text(subtitle,color=Muted,style=MaterialTheme.typography.bodyMedium)
    Spacer(Modifier.height(24.dp))
}

@Composable
internal fun SectionHeader(title:String,action:String?=null,onAction:()->Unit={}) {
    Row(Modifier.fillMaxWidth().padding(top=8.dp,bottom=12.dp),verticalAlignment=Alignment.CenterVertically) {
        Text(title,Modifier.weight(1f),color=White,style=MaterialTheme.typography.titleMedium)
        if(action!=null)TextButton(onClick=onAction,contentPadding=PaddingValues(horizontal=4.dp)){Text(action,fontSize=12.sp)}
    }
}

@Composable
internal fun ChoiceChip(text:String,selected:Boolean,enabled:Boolean=true,onClick:()->Unit) {
    Surface(onClick=onClick,enabled=enabled,shape=RoundedCornerShape(12.dp),
        color=if(selected)Aqua else RaisedBlue,contentColor=if(selected)Navy else White) {
        Text(text,Modifier.padding(horizontal=16.dp,vertical=12.dp),fontSize=13.sp,fontWeight=FontWeight.Medium)
    }
}

@Composable
internal fun SmallBadge(text:String,color:Color=Aqua) {
    Text(text,Modifier.background(color.copy(alpha=.11f),RoundedCornerShape(8.dp)).padding(horizontal=9.dp,vertical=5.dp),
        color=color,fontSize=11.sp,fontWeight=FontWeight.Medium)
}

@Composable
internal fun HintLine(text:String,modifier:Modifier=Modifier) {
    Text(text,modifier,color=Muted,style=MaterialTheme.typography.bodySmall)
}

@Composable
internal fun ConnectionHint(onConnect:()->Unit=LocalDeviceNavigation.current) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(RaisedBlue.copy(alpha=.6f))
        .clickable(onClick=onConnect).padding(15.dp),verticalAlignment=Alignment.CenterVertically) {
        StudioIcon(Glyph.DEVICE,Modifier.size(20.dp),Gold)
        Text("连接声芯，在设备上演奏",Modifier.weight(1f).padding(horizontal=10.dp),color=White,fontSize=13.sp)
        StudioIcon(Glyph.ARROW,Modifier.size(16.dp),Muted)
    }
}
