package cn.soundcore.instrument
import app.cash.paparazzi.Paparazzi
import app.cash.paparazzi.DeviceConfig
import org.junit.Rule
import org.junit.Test
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.material3.Text

class NaturalPitchSnapshotsTest {
    @get:Rule val paparazzi=Paparazzi(deviceConfig=DeviceConfig.PIXEL_5.copy(softButtons=false),theme="android:style/Theme.Material.NoActionBar")
    @Test fun chromaticKeyboard()=paparazzi.snapshot {SoundcoreTheme{
        Column(Modifier.fillMaxSize().background(Navy).padding(20.dp)){
            StudioCard {
                Text("完整十二音 · F调",color=White)
                ChromaticKeys(2,5,true){_,_->}
                HintLine("按住发声 · 多指触控 · 保留准确升降音")
            }
        }
    }}
    @Test fun naturalKeyConfiguration()=paparazzi.snapshot {SoundcoreTheme{
        val view=BleView(connected=true,pitchLayout=PitchLayoutState(6,7),layoutSupported=true,
            state=DeviceState(2,1,16,false,0,0,0,7,true,vibratoDepth=4,bend=128,realtimeNotes=true))
        StudioScreen(view,{},{},{},{_,_->})
    }}
}
