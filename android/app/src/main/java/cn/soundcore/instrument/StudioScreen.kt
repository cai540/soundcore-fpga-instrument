package cn.soundcore.instrument

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

@Composable
fun StudioScreen(view:BleView,onScan:()->Unit,onConnect:(String)->Unit,onDisconnect:()->Unit,
    onCommand:(Int,Int?)->Unit,onNote:(Int,Boolean,Int)->Unit={_,_,_->},onAllNotesOff:()->Unit={},
    onScene:(InstrumentScene)->Unit={},savedScene:InstrumentScene?=null,onSaveScene:()->Unit={},
    onTabChanged:(Int)->Unit={},initialTab:Int=0,onPitch:(Int,Boolean,Int)->Unit={_,_,_->},melodyContent:@Composable ()->Unit={},deviceContent:(@Composable ()->Unit)?=null,libraryContent:(@Composable ()->Unit)?=null) {
    var tab by rememberSaveable { mutableIntStateOf(AppDestination.fromIndex(initialTab).index) }
    val scrolls=List(5){rememberScrollState()}
    val scope=rememberCoroutineScope()
    val state=view.state
    val canWrite=view.connected && state?.writeAllowed==true && view.pitchLayout!=null
    fun navigate(next:Int) {
        if(next!=tab){onAllNotesOff();if(state?.bend!=null)onCommand(Protocol.RELEASE_BEND,null);tab=next}
    }
    LaunchedEffect(initialTab){navigate(initialTab)}
    LaunchedEffect(tab){onTabChanged(tab)}
    BackHandler(tab!=0){navigate(0)}
    CompositionLocalProvider(LocalDeviceNavigation provides {navigate(4)},LocalPageTop provides {scope.launch{scrolls[tab].scrollTo(0)}}) {
        Scaffold(containerColor=Navy,contentWindowInsets=WindowInsets.safeDrawing,
            bottomBar={NavigationBar(containerColor=Navy,tonalElevation=0.dp) {
                AppDestination.entries.forEach { page ->
                    val glyph=when(page){AppDestination.PERFORMANCE->Glyph.PADS;AppDestination.LIBRARY->Glyph.LIBRARY;
                        AppDestination.CREATE->Glyph.CREATE;AppDestination.SOUND->Glyph.VOICE;AppDestination.DEVICE->Glyph.DEVICE}
                    NavigationBarItem(selected=tab==page.index,onClick={navigate(page.index)},
                        icon={StudioIcon(glyph,Modifier.size(23.dp),if(tab==page.index)Aqua else Muted)},
                        label={Text(page.label,fontSize=11.sp,fontWeight=if(tab==page.index)FontWeight.SemiBold else FontWeight.Normal)},
                        colors=NavigationBarItemDefaults.colors(selectedTextColor=Aqua,unselectedTextColor=Muted,
                            indicatorColor=Aqua.copy(alpha=.11f)))
                }
            }}) { insets ->
            Column(Modifier.fillMaxSize().padding(insets)) {
                Row(Modifier.fillMaxWidth().padding(horizontal=22.dp,vertical=12.dp),verticalAlignment=Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("声芯",color=White,fontSize=23.sp,fontWeight=FontWeight.Bold,letterSpacing=2.sp)
                        Text("SOUNDCORE",color=Muted,fontSize=9.sp,letterSpacing=2.sp)
                    }
                    Row(Modifier.background(if(state!=null)Aqua.copy(alpha=.09f) else RaisedBlue,RoundedCornerShape(30.dp))
                        .clickable{navigate(4)}.padding(horizontal=13.dp,vertical=10.dp),
                        horizontalArrangement=Arrangement.spacedBy(7.dp),verticalAlignment=Alignment.CenterVertically) {
                        Box(Modifier.size(6.dp).background(if(state!=null)Aqua else Gold,CircleShape))
                        Text(if(state!=null)"已连接" else if(view.connected)"同步中" else "连接设备",
                            color=if(state!=null)Aqua else Gold,fontSize=11.sp)
                    }
                }
                Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(scrolls[tab]).padding(horizontal=20.dp)) {
                    Spacer(Modifier.height(14.dp))
                    when(AppDestination.fromIndex(tab)) {
                        AppDestination.PERFORMANCE -> PerformancePage(view,canWrite,onCommand,onNote,onPitch,onAllNotesOff)
                        AppDestination.LIBRARY -> if(libraryContent!=null)libraryContent() else SongsPage(view,canWrite,onCommand,onNote)
                        AppDestination.CREATE -> melodyContent()
                        AppDestination.SOUND -> TimbrePage(view,canWrite,onCommand,onScene,savedScene,onSaveScene)
                        AppDestination.DEVICE -> if(deviceContent!=null)deviceContent() else DevicePage(view,onScan,onConnect,onDisconnect,onCommand)
                    }
                    Spacer(Modifier.height(28.dp))
                }
            }
        }
    }
}
