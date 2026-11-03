package cn.soundcore.instrument

import app.cash.paparazzi.Paparazzi
import app.cash.paparazzi.DeviceConfig
import org.junit.Rule
import org.junit.Test
import androidx.compose.runtime.Composable
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.Density
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.runtime.CompositionLocalProvider
import org.json.JSONObject
import org.json.JSONArray
import java.io.File

/** Real Compose rendering. Fixture state is confined to tests and never enters the APK. */
class ProductSnapshotsTest {
    @get:Rule val paparazzi=Paparazzi(deviceConfig=DeviceConfig.PIXEL_5.copy(softButtons=false),theme="android:style/Theme.Material.NoActionBar")
    private fun page(tab:Int)=paparazzi.snapshot {SoundcoreTheme{
        StudioScreen(BleView(),{},{},{},{_,_->},initialTab=tab,
            melodyContent={CreativeWorkspace(MelodyView(),SheetView(),MelodyView(),{},{},recordContent={},sheetContent={})})
    }}
    @Test fun performance()=page(0)
    @Test fun library()=page(1)
    @Test fun creation()=page(2)
    @Test fun sound()=page(3)
    @Test fun device()=page(4)
    @Test fun recordingInput()=paparazzi.snapshot {SoundcoreTheme{SnapshotFrame{
        MelodyPanel(MelodyView(),BleView(),{},{},{},{},{},{},{},{},{})
    }}}
    @Test fun sheetInput()=paparazzi.snapshot {SoundcoreTheme{SnapshotFrame{
        SheetPanel(SheetView(),false,true,{},{},{},{},{},{},{},{})
    }}}
    @Test fun sheetResult() {
        val root=File("../../..").canonicalFile
        val music=SheetMusic(JSONArray(File(root,"tests/fixtures/sheet_music_cases.json").readText()).getJSONObject(0).getJSONObject("score"))
        paparazzi.snapshot {SoundcoreTheme{SnapshotFrame{
            SheetPanel(SheetView(music=music,bpm=music.defaultBpm),false,true,{},{},{},{},{},{},{},{})
        }}}
    }
    @Test fun melodyResult() {
        val score=MelodyScore(listOf(MelodyNote(0,600,60,0f),MelodyNote(700,600,62,0f),MelodyNote(1400,1400,64,0f)),3000)
        paparazzi.snapshot {SoundcoreTheme{SnapshotFrame{
            MelodyPanel(MelodyView(score=score,range=MelodyRange(0,3000),scoreRange=MelodyRange(0,3000),message="旋律已保存在手机"),BleView(),{},{},{},{},{},{},{},{},{})
        }}}
    }
    @Test fun recognitionProgress()=paparazzi.snapshot {SoundcoreTheme{SnapshotFrame{
        MelodyPanel(MelodyView(busy=true,progress=58,message="分析基频与八度"),BleView(),{},{},{},{},{},{},{},{},{})
    }}}
    @Test fun connectedPerformance()=paparazzi.snapshot {SoundcoreTheme{
        val device=BleView(connected=true,pitchLayout=PitchLayoutState(0,7),layoutSupported=true,state=DeviceState(2,1,16,false,0,0,0,7,true,
            vibratoDepth=4,bend=128,ledMode=0,oledContrast=160,padMask=8,effectMask=0,songExtended=true,realtimeNotes=true))
        StudioScreen(device,{},{},{},{_,_->})
    }}
    @Test fun libraryLargeText()=paparazzi.snapshot {SoundcoreTheme{
        CompositionLocalProvider(LocalDensity provides Density(LocalDensity.current.density,1.3f)){
            StudioScreen(BleView(),{},{},{},{_,_->},initialTab=1)
        }
    }}
}

@Composable private fun SnapshotFrame(content:@Composable ColumnScope.()->Unit){
    Column(Modifier.fillMaxSize().background(Navy).verticalScroll(rememberScrollState()).padding(20.dp),content=content)
}
