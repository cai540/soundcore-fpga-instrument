package cn.soundcore.instrument

import app.cash.paparazzi.Paparazzi
import app.cash.paparazzi.DeviceConfig
import org.junit.Rule
import org.junit.Test
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import java.io.File

/** Captured RTL analyzer data, UI-only fixture; never a source of live telemetry. */
class ToolsSnapshotsTest {
    @get:Rule val paparazzi=Paparazzi(deviceConfig=DeviceConfig.PIXEL_5.copy(softButtons=false),theme="android:style/Theme.Material.NoActionBar")
    private val status=ToolStatus(32,32,1,32,64000,1,0)
    private fun plot(kind:Int):ByteArray {
        val line=File("../../../build/acceptance_20261102/analysis_vectors.txt").readLines()[kind]
        return line.chunked(2).map{it.toInt(16).toByte()}.reversed().toByteArray()
    }
    private fun screen(kind:Int=0,section:Int=0,diagnostic:Boolean=false)=paparazzi.snapshot {SoundcoreTheme{
        Column(Modifier.fillMaxSize().background(Navy).verticalScroll(rememberScrollState()).padding(20.dp)){
            ProductToolsPanel(ProductToolsView(supported=true,status=status,plotKind=kind,plot=plot(kind),plotFrame=1,message="真实RTL仿真数据 · 页面验收样张"),true,null,section,diagnostic){}
        }
    }}
    @Test fun waveform()=screen()
    @Test fun spectrum()=screen(1)
    @Test fun phase()=screen(2)
    @Test fun mapping()=screen(section=1)
    @Test fun microphone()=paparazzi.snapshot {SoundcoreTheme{
        Column(Modifier.fillMaxSize().background(Navy).verticalScroll(rememberScrollState()).padding(20.dp)){
            val frame=ScopeAnalysis.frame(FloatArray(1024){k->(.2*kotlin.math.sin(2*kotlin.math.PI*440*k/16000)).toFloat()},12)
            ProductToolsPanel(ProductToolsView(liveMic=true,liveFrame=frame,message="手机麦克风 · 界面测试信号"),false,null){}
        }
    }}
    @Test fun deviceRecording()=screen(section=2)
    @Test fun library()=paparazzi.snapshot {SoundcoreTheme{
        Column(Modifier.fillMaxSize().background(Navy).verticalScroll(rememberScrollState()).padding(20.dp)){
            val scores=File("src/main/assets/scores").listFiles()!!.map{StructuredScore.parse(it.readText())}
            ScoreLibraryPanel(ScoreLibraryView(scores=scores.take(3),catalog=scores.sortedBy{if(it.category=="熟悉旋律")0 else 1},exploring=true),null,{},{},{_,_->})
        }
    }}
}
