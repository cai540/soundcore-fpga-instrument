package cn.soundcore.instrument

import app.cash.paparazzi.Paparazzi
import app.cash.paparazzi.DeviceConfig
import org.junit.Rule
import org.junit.Test

class OfflineRecognitionSnapshotsTest {
    @get:Rule val paparazzi=Paparazzi(deviceConfig=DeviceConfig.PIXEL_5.copy(softButtons=false),theme="android:style/Theme.Material.NoActionBar")
    @Test fun phoneRecordingWithoutConnection()=paparazzi.snapshot {SoundcoreTheme{
        StudioScreen(BleView(),{},{},{},{_,_->},initialTab=2,melodyContent={
            MelodyPanel(MelodyView(),BleView(),{},{},{},{},{},{},{},{},{})
        })
    }}
    @Test fun phoneSheetWithoutConnection()=paparazzi.snapshot {SoundcoreTheme{
        StudioScreen(BleView(),{},{},{},{_,_->},initialTab=2,melodyContent={
            SheetPanel(SheetView(),false,true,{},{},{},{},{},{},{},{})
        })
    }}
}
