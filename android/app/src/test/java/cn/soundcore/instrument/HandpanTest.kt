package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test

class HandpanTest {
    @Test fun airyAndMetalHaveDistinctProductNamesAndScenes() {
        assertEquals("空灵手碟",InstrumentTone.name(2))
        assertEquals("金属电音",InstrumentTone.name(3))
        assertTrue(InstrumentTone.isMetal(3))
        assertFalse(InstrumentTone.isMetal(2))
        assertEquals(1,InstrumentScene.presets.count{it.timbre==2})
        assertEquals(1,InstrumentScene.presets.count{it.timbre==3})
    }
    @Test fun allKeysStayPlayableAndKeepTheVoicingIntervals() {
        for(bank in 0..4)for(key in 0..11) {
            val notes=(0..6).map{InstrumentTone.handpanIndex(bank,it,key)}
            assertTrue(notes.all{it in 0..71})
            assertEquals(listOf(0,2,4,7,9,12,14),notes.map{it-notes[0]})
        }
        assertEquals(listOf("C4","D4","E4","G4","A4","C5","D5"),InstrumentTone.handpanLabels(2,0))
        assertEquals(listOf(60,62,64,65,67,69,71),(0..6).map{PitchLayout.midi(2,it)})
    }
    @Test fun thirdInstrumentRoundTripsInExistingProtocolAndScenes() {
        for(id in 0..3) {
            val payload=byteArrayOf(2,id.toByte(),16,0,0,0,0,7,1,4,128.toByte(),0,160.toByte(),0)
            val s=DeviceState.from(payload)!!
            assertEquals(id,s.timbre)
            Protocol.encodeCommand(Protocol.SET_TIMBRE,1,byteArrayOf(id.toByte()))
            val scene=InstrumentScene.fromState("保存",s)!!
            assertEquals(scene,InstrumentScene.fromStored("保存",scene.storedValue()))
            Protocol.encodeCommand(Protocol.SET_SCENE,2,scene.payload())
            assertTrue(scene.matches(s))
        }
        assertNull(DeviceState.from(byteArrayOf(2,4,16,0,0,0,0,7,1)))
    }
}
