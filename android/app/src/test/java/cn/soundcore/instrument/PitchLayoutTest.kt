package cn.soundcore.instrument
import org.junit.Assert.*
import org.junit.Test

class PitchLayoutTest {
    @Test fun everyNaturalDegreeRoundTripsInAllKeysAndOctaves() {
        val offsets=listOf(0,2,4,5,7,9,11)
        for(key in 0..11)for(bank in 0..4)for(pad in 0..6){
            val n=PitchLayout.index(bank,pad,key)
            assertEquals(bank*12+key+offsets[pad],n)
            assertEquals(bank,PitchLayout.bank(n,key));assertEquals(pad,PitchLayout.degree(n,key))
        }
        assertEquals(listOf(60,62,64,65,67,69,71),(0..6).map{PitchLayout.midi(2,it)})
    }
    @Test fun exactUploadRetainsEveryChromaticPitchAndRestWithoutQuantization() {
        for(index in 0..71){val word=ScoreEvent(500,index).word();assertEquals(index,word and 127);assertEquals(500,word ushr 7)}
        assertEquals(127,ScoreEvent(200,null).word() and 127)
        val notes=listOf(36,37,60,61,70,71,106,107).mapIndexed{i,n->MelodyNote(i*300,200,n,1f)}
        val score=MelodyScore(notes,2400)
        assertEquals(0,score.suggestedTranspose)
        assertEquals(notes.map{it.midi},score.events(0).mapNotNull{it.note?.plus(36)})
    }
    @Test fun capabilityAndSchemaPreventOldFirmwareMisinterpretation() {
        assertNotNull(PitchLayoutState.from(byteArrayOf(1,2,36,107,5,0,7)))
        assertNull(PitchLayoutState.from(byteArrayOf(1,1,60,94,5,0,7)))
        Protocol.encodeCommand(Protocol.SCORE_ABSOLUTE_BEGIN,1,byteArrayOf(1,0,1,0,0,0,1,5))
        val transfer=ScoreTransfer(listOf(ScoreEvent(300,24)),1,1);transfer.next()
        try{transfer.acknowledge(Protocol.SCORE_ABSOLUTE_BEGIN,UploadedScoreState(2,0,0,0,7,0,1,0,1));fail("V1 ACK accepted")}catch(_:IllegalArgumentException){}
    }
    @Test fun chromaticMailboxIsBoundedAndReleaseCancelsUnsentTaps() {
        val notes=RealtimeNotes()
        notes.downAbsolute(24,200);notes.downAbsolute(25,200);notes.downAbsolute(70,200)
        val packet=notes.peek(0)!!;assertEquals(Protocol.REALTIME_ABSOLUTE,packet.type)
        assertEquals(listOf(24,25,70),packet.pitches!!.take(3))
        Protocol.encodeCommand(packet.type,1,packet.payload())
        notes.upAbsolute(25);assertEquals(5,notes.peek(0)!!.held)
        notes.release();assertEquals(0,notes.peek(0)!!.attacks);assertEquals(0,notes.peek(0)!!.held)
        notes.sent(notes.peek(0)!!,0);assertNull(notes.peek(1000))
        repeat(12){notes.downAbsolute(it,176)};assertEquals(127,notes.held)
    }
    @Test fun savedSceneMigratesWithoutDiscardingActualKey() {
        val scene=InstrumentScene("test",2,1,16,true,4,0,127,5)
        assertEquals(scene,InstrumentScene.fromStored("test",scene.storedValue()))
        val old=InstrumentScene.fromStored("old","0,1,16,0,4,0,127")!!
        assertEquals(2,old.bank);assertEquals(0,old.key)
    }
}
