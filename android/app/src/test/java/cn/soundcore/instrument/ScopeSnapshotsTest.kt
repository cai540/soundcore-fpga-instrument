package cn.soundcore.instrument

import app.cash.paparazzi.Paparazzi
import app.cash.paparazzi.DeviceConfig
import org.junit.Rule
import org.junit.Test
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlin.math.*

/** Deliberate test input; no synthetic values enter production acquisition. */
class ScopeSnapshotsTest {
    @get:Rule val paparazzi=Paparazzi(deviceConfig=DeviceConfig.PIXEL_5.copy(softButtons=false),theme="android:style/Theme.Material.NoActionBar")
    private fun view(kind:Int):ProductToolsView {
        val frame=ScopeAnalysis.frame(FloatArray(16384){i->(.28*sin(2*PI*440*i/48000)+.07*sin(2*PI*880*i/48000)).toFloat()},32,48000)
        return ProductToolsView(liveMic=true,liveFrame=frame,plotKind=kind,scope=ScopeSettings(fsPerDiv=.1f,msPerDiv=1f,focusedSpectrum=true,highResolution=true),message="界面测试信号")
    }
    private fun page(kind:Int)=paparazzi.snapshot {SoundcoreTheme{
        Column(Modifier.fillMaxSize().background(Navy).padding(18.dp)){
            ScopeWorkbench(view(kind),null,{},fullScreen=true)
        }
    }}
    @Test fun wave()=page(0)
    @Test fun fft()=page(1)
    @Test fun xy()=page(2)
}

class ScopeLandscapeSnapshotsTest {
    @get:Rule val paparazzi=Paparazzi(deviceConfig=DeviceConfig.PIXEL_5.copy(orientation=com.android.resources.ScreenOrientation.LANDSCAPE,softButtons=false),theme="android:style/Theme.Material.NoActionBar")
    @Test fun waveLandscape()=paparazzi.snapshot {SoundcoreTheme{
        val f=ScopeAnalysis.frame(FloatArray(4096){(.3*sin(2*PI*440*it/48000)).toFloat()},5,48000)
        Column(Modifier.fillMaxSize().background(Navy).padding(12.dp)){
            ScopeWorkbench(ProductToolsView(liveMic=true,liveFrame=f),null,{},fullScreen=true)
        }
    }}
}
