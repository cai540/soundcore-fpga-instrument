package cn.soundcore.instrument

import app.cash.paparazzi.Paparazzi
import app.cash.paparazzi.DeviceConfig
import org.junit.Rule
import org.junit.Test

class HandpanSnapshotsTest {
    @get:Rule val paparazzi=Paparazzi(deviceConfig=DeviceConfig.PIXEL_5.copy(softButtons=false),theme="android:style/Theme.Material.NoActionBar")
    private fun view(tone:Int=2)=BleView(connected=true,pitchLayout=PitchLayoutState(0,7),layoutSupported=true,
        state=DeviceState(1,tone,16,false,0,0,0,7,true,vibratoDepth=4,bend=128,ledMode=0,oledContrast=160,padMask=0,effectMask=0,songExtended=true,realtimeNotes=true))
    @Test fun sound()=paparazzi.snapshot {SoundcoreTheme{StudioScreen(view(),{},{},{},{_,_->},initialTab=3)}}
    @Test fun performance()=paparazzi.snapshot {SoundcoreTheme{StudioScreen(view(),{},{},{},{_,_->})}}
    @Test fun metal()=paparazzi.snapshot {SoundcoreTheme{StudioScreen(view(3),{},{},{},{_,_->})}}
}
