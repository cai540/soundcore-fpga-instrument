package cn.soundcore.instrument

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.roundToInt

@Composable
internal fun TimbrePage(view:BleView,canWrite:Boolean,command:(Int,Int?)->Unit,
    onScene:(InstrumentScene)->Unit,savedScene:InstrumentScene?,onSaveScene:()->Unit) {
    val s=view.state
    PageLead("声音的性格","换一种音色，听见不同的情绪")
    TimbreTile("口琴","清亮悠扬 · 适合旋律",R.drawable.timbre_harmonica,s?.timbre==1,canWrite){command(Protocol.SET_TIMBRE,1)}
    Spacer(Modifier.height(13.dp))
    TimbreTile("二胡","温润弓弦 · 适合长音",R.drawable.timbre_erhu,s?.timbre==0,canWrite){command(Protocol.SET_TIMBRE,0)}
    Spacer(Modifier.height(13.dp))
    StudioCard {
        Text("节奏与共鸣",style=MaterialTheme.typography.titleLarge)
        HintLine("轻敲空灵的余韵，或用旋钮与滑杆塑造金属张力")
        Row(horizontalArrangement=Arrangement.spacedBy(10.dp)) {
            listOf(2 to "◉ 空灵手碟",3 to "ϟ 金属电音").forEach { (id,label) ->
                FilterChip(s?.timbre==id,onClick={command(Protocol.SET_TIMBRE,id)},enabled=canWrite,label={Text(label)})
            }
        }
    }
    SectionHeader("声音效果")
    StudioCard {
        listOf(Triple("回声","让尾音层层散开",1),Triple("合唱","增添音色的厚度",2),Triple("混响","让旋律拥有空间",4)).forEachIndexed{index,item->
            if(index>0)HorizontalDivider(color=BorderBlue.copy(alpha=.4f))
            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
                Column(Modifier.weight(1f)){Text(item.first,style=MaterialTheme.typography.titleMedium);HintLine(item.second)}
                val checked=s?.effectMask?.and(item.third)!=0 && s?.effectMask!=null
                Switch(checked=checked,onCheckedChange={on->
                    val mask=s?.effectMask?:0
                    command(Protocol.SET_EFFECTS,if(on)mask or item.third else mask and item.third.inv())
                },enabled=canWrite && s?.effectMask!=null)
            }
        }
    }
    SectionHeader("演奏场景")
    HintLine("将音色、音区和设备氛围一起切换")
    Spacer(Modifier.height(12.dp))
    LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp)){
        items(InstrumentScene.presets.filter{it.timbre<=1}){scene ->
            Surface(onClick={onScene(scene)},enabled=canWrite && s?.vibratoDepth!=null,
                shape=RoundedCornerShape(20.dp),color=if(s?.let(scene::matches)==true)Aqua.copy(alpha=.12f) else CardBlue) {
                Column(Modifier.width(148.dp).padding(18.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
                    StudioIcon(Glyph.WAVE,Modifier.size(26.dp),if(scene.timbre==1)Aqua else Gold)
                    Text(scene.name,color=White,fontSize=15.sp,fontWeight=FontWeight.Medium)
                    HintLine("${InstrumentTone.name(scene.timbre)} · 音区${scene.bank+1}")
                }
            }
        }
    }
    Spacer(Modifier.height(12.dp))
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)){
        if(savedScene!=null && savedScene.timbre<=1)OutlinedButton(onClick={onScene(savedScene)},enabled=canWrite,modifier=Modifier.weight(1f)){Text("我的场景")}
        OutlinedButton(onClick=onSaveScene,enabled=canWrite && s?.vibratoDepth!=null,modifier=Modifier.weight(1f)){Text("保存当前场景")}
    }
    if(!view.connected){Spacer(Modifier.height(14.dp));ConnectionHint()}
}

@Composable
private fun TimbreTile(name:String,subtitle:String,image:Int,selected:Boolean,enabled:Boolean,onClick:()->Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(CardBlue)
        .border(1.dp,if(selected)Aqua.copy(alpha=.7f) else BorderBlue.copy(alpha=.45f),RoundedCornerShape(24.dp))
        .clickable(enabled=enabled,onClick=onClick).padding(12.dp),verticalAlignment=Alignment.CenterVertically) {
        Image(painterResource(image),null,Modifier.size(92.dp).clip(RoundedCornerShape(17.dp)),contentScale=ContentScale.Crop)
        Column(Modifier.weight(1f).padding(horizontal=15.dp),verticalArrangement=Arrangement.spacedBy(7.dp)){
            Text(name,color=White,fontSize=24.sp,fontWeight=FontWeight.SemiBold)
            Text(subtitle,color=Muted,fontSize=11.sp)
            if(selected)Text("当前音色",color=Aqua,fontSize=11.sp)
        }
        if(selected)StudioIcon(Glyph.CHECK,Modifier.size(19.dp))
    }
}

@Composable
internal fun DevicePage(view:BleView,onScan:()->Unit,onConnect:(String)->Unit,onDisconnect:()->Unit,command:(Int,Int?)->Unit,onTools:(()->Unit)?=null) {
    val s=view.state
    val ready=view.connected && s!=null
    val canWrite=ready && s?.writeAllowed==true
    PageLead("我的声芯","设备与手机，在这里相遇")
    StudioCard {
        Box(Modifier.fillMaxWidth(),contentAlignment=Alignment.Center){DeviceDrawing(ready)}
        Text(if(ready)"声芯已就绪" else if(view.connected)"正在同步设备" else "连接你的声芯",style=MaterialTheme.typography.titleLarge)
        HintLine(if(ready)"可以演奏、选曲和调整声音" else if(view.connected)"蓝牙已连接，正在读取设备状态" else "打开设备电源，保持手机蓝牙开启")
        Button(onClick=if(view.connected)onDisconnect else onScan,modifier=Modifier.fillMaxWidth().height(50.dp),shape=RoundedCornerShape(15.dp)) {
            StudioIcon(Glyph.DEVICE,Modifier.size(18.dp),Navy);Spacer(Modifier.width(8.dp));Text(if(view.connected)"断开连接" else "扫描附近设备")
        }
        if(view.connected)TextButton(onClick=onScan,modifier=Modifier.align(Alignment.CenterHorizontally)){Text("连接其他设备")}
        deviceNotice(view.message)?.let{HintLine(it)}
    }
    if(onTools!=null) {
        StudioCard {
            Text("演奏工具",style=MaterialTheme.typography.titleLarge)
            HintLine("声音图景 · 自定义琴键 · 设备录音与回听")
            Button(onClick=onTools,modifier=Modifier.fillMaxWidth()){Text("进入演奏工具")}
        }
    }
    if(!view.connected && view.devices.isNotEmpty()) {
        SectionHeader("附近的设备")
        orderedDevices(view.devices).forEach { device ->
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(CardBlue).clickable{onConnect(device.address)}.padding(17.dp),
                verticalAlignment=Alignment.CenterVertically) {
                StudioIcon(Glyph.DEVICE,Modifier.size(22.dp));Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)){Text(device.name,color=White,fontSize=15.sp);HintLine(device.address)}
                StudioIcon(Glyph.ARROW,Modifier.size(16.dp),Muted)
            }
            Spacer(Modifier.height(8.dp))
        }
    }
    SectionHeader("灯光与显示")
    StudioCard {
        Text("琴键灯光",style=MaterialTheme.typography.titleMedium)
        val names=listOf("跟随敲击","曲目指引","流光","呼吸")
        repeat(2){row -> Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(9.dp)){
            repeat(2){column -> val index=row*2+column
                Surface(onClick={command(Protocol.SET_LED_MODE,index)},enabled=canWrite && s?.ledMode!=null,
                    color=if(s?.ledMode==index)Aqua.copy(alpha=.14f) else RaisedBlue,shape=RoundedCornerShape(12.dp),modifier=Modifier.weight(1f)){
                    Text(names[index],Modifier.padding(horizontal=12.dp,vertical=13.dp),color=if(s?.ledMode==index)Aqua else Muted,fontSize=13.sp)
                }
            }
        }}
        HorizontalDivider(color=BorderBlue.copy(alpha=.4f))
        var brightness by remember(s?.oledContrast){mutableFloatStateOf((s?.oledContrast?:160).toFloat())}
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("屏幕亮度",style=MaterialTheme.typography.titleMedium);Text(if(s?.oledContrast==null)"—" else "${(brightness/255*100).roundToInt()}%",color=Aqua,fontSize=12.sp)}
        Slider(value=brightness,onValueChange={brightness=it},onValueChangeFinished={command(Protocol.SET_OLED_CONTRAST,brightness.roundToInt())},valueRange=0f..255f,
            enabled=canWrite && s?.oledContrast!=null)
    }
    SectionHeader("关于声芯")
    StudioCard {
        InfoRow("连接方式","蓝牙低功耗")
        InfoRow("七键音域","每调35个自然音 · 五个八度")
        InfoRow("精确音域","C2—B7 · 保留全部升降音")
        InfoRow("音色","口琴 / 二胡 / 空灵手碟 / 金属")
        InfoRow("App版本",BuildConfig.VERSION_NAME.substringBefore('-'))
    }
}

private fun deviceNotice(message:String):String?=when {
    message.startsWith("已连接") -> null
    message in listOf("尚未连接","已连接","已连接 · FPGA 已确认")->null
    message.contains("状态帧无效") || message.contains("力度帧无效") || message.contains("未知 FPGA")->"设备状态未能同步，请断开后重新连接。"
    message.contains("FPGA 未确认")->"设备暂时没有响应，请检查电源和连接。"
    message.contains("GATT") || message.startsWith("连接已断开 (")->"蓝牙连接已中断，请重新连接。"
    message.contains("数据通道就绪")->"正在同步设备设置…"
    else->message.take(150)
}

@Composable
private fun InfoRow(label:String,value:String) {
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text(label,color=Muted,fontSize=12.sp);Text(value,color=White,fontSize=12.sp)}
}

@Composable
private fun DeviceDrawing(connected:Boolean) {
    Canvas(Modifier.size(220.dp,94.dp)) {
        val w=size.width;val h=size.height
        drawRoundRect(RaisedBlue,Offset(w*.04f,h*.25f),Size(w*.92f,h*.63f),CornerRadius(14f))
        drawRoundRect(BorderBlue,Offset(w*.04f,h*.76f),Size(w*.92f,h*.12f),CornerRadius(5f))
        repeat(7){i->val y=if(i==0||i==6)h*.43f else if(i==1||i==5)h*.35f else h*.30f
            drawRoundRect(if(connected)Aqua.copy(alpha=.55f) else BorderBlue,Offset(w*(.09f+i*.105f),y),Size(w*.074f,h*.18f),CornerRadius(5f))}
        drawRoundRect(if(connected)Aqua.copy(alpha=.6f) else Muted.copy(alpha=.3f),Offset(w*.81f,h*.38f),Size(w*.1f,h*.09f),CornerRadius(2f))
    }
}
