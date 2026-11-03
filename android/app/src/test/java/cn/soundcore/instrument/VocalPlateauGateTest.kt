package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class VocalPlateauGateTest {
    private fun track(ms:Int,p:(Int)->Double,r:(Int)->Double={.25})=
        StablePitchTracker.Track(DoubleArray(ms/10){p(it*10)},DoubleArray(ms/10){.9},DoubleArray(ms/10){r(it*10)})
    private fun n(start:Int,length:Int,pitch:Int)=MelodyNote(start,length,pitch,.9f)
    private fun apply(notes:List<MelodyNote>,t:StablePitchTracker.Track)=VocalPlateauGate.apply(notes,t)
    @Test fun genuineFastAscendingNotesRemain() {
        val t=track(600,{intArrayOf(60,62,64,65)[min(3,it/150)].toDouble()})
        val n=List(4){n(it*150,150,intArrayOf(60,62,64,65)[it])}
        assertEquals(n,apply(n,t))
    }
    @Test fun genuineChromaticAndOctavePlateausRemain() {
        for(pitches in listOf(listOf(60,61,62),listOf(72,60,72))) {
            val t=track(1050,{pitches[min(2,it/350)].toDouble()})
            val n=List(3){n(it*350,350,pitches[it])}
            assertEquals(n,apply(n,t))
        }
    }
    @Test fun alreadyRepairedShortOctaveRemains() {
        val t=track(900,{if(it in 400..549)64.0 else 76.0})
        val n=listOf(n(0,400,76),n(400,150,76),n(550,350,76))
        assertEquals(n,apply(n,t))
    }
    @Test fun transientGlideIsNotASeparateNote() {
        val t=track(1200,{when {it<400->60.0;it<600->60.6+(it-400)*.014;else->64.0}})
        val result=apply(listOf(n(0,400,60),n(400,200,62),n(600,600,64)),t)
        assertEquals(listOf(60,64),result.map{it.midi})
        assertEquals(0,result.first().startMs)
        assertEquals(1200,result.last().startMs+result.last().durationMs)
        assertEquals(result[0].startMs+result[0].durationMs,result[1].startMs)
    }
    @Test fun consecutivePassingStatesAreDecidedTogether() {
        val t=track(1300,{when {it<400->60.0;it<700->60+(it-400)*.013333;else->64.0}})
        val result=apply(listOf(n(0,400,60),n(400,150,61),n(550,150,62),n(700,600,64)),t)
        assertEquals(listOf(60,64),result.map{it.midi})
    }
    @Test fun unsupportedLongReturnGlideCanMerge() {
        val t=track(1400,{when {it<400 || it>=900->60.0;it<650->60+(it-400)*.016;else->64-(it-650)*.016}})
        val result=apply(listOf(n(0,400,60),n(400,500,62),n(900,500,60)),t)
        assertEquals(listOf(n(0,1400,60)),result)
    }
    @Test fun genuineLongVibratoNoteIsProtected() {
        val t=track(1400,{if(it in 400..899)62+.3*sin(2*PI*5*it/1000) else 60.0})
        val n=listOf(n(0,400,60),n(400,500,62),n(900,500,60))
        assertEquals(n,apply(n,t))
    }
    @Test fun trueBreathBeforeFalseAttackRemainsSilent() {
        val t=track(1300,{when {it<400->60.0;it<500->Double.NaN;it<700->59.5+(it-500)*.0225;else->64.0}},
            {if(it in 400..499)0.0 else .25})
        val result=apply(listOf(n(0,400,60),n(500,200,62),n(700,600,64)),t)
        assertEquals(listOf(60,64),result.map{it.midi})
        assertEquals(100,result[1].startMs-result[0].startMs-result[0].durationMs)
    }
    @Test fun repeatedSamePitchEventsAreNotCoalescedByThePitchGate() {
        val t=track(1000,{67.0})
        val n=listOf(n(0,500,67),n(500,500,67))
        assertEquals(n,apply(n,t))
    }
    @Test fun longContinuousDescentDoesNotBecomeAStaircase() {
        val t=track(1600,{when {it<400->74.0;it<1080->74-(it-400)*8.0/680;else->66.0}})
        val n=listOf(n(0,400,74),n(400,200,73),n(600,180,71),n(780,300,67),n(1080,520,66))
        val result=apply(n,t)
        assertEquals(listOf(74,66),result.map{it.midi})
        assertEquals(1600,result.last().startMs+result.last().durationMs)
    }
    @Test fun realFastDescendingScaleIsNotAContinuousGlide() {
        val pitches=intArrayOf(74,73,71,69,67,66)
        val t=track(900,{pitches[min(5,it/150)].toDouble()})
        val n=pitches.mapIndexed {i,p->n(i*150,150,p)}
        assertEquals(n,apply(n,t))
    }
    @Test fun cancelledGateStopsBeforeReturning() {
        val t=track(1000,{67.0});var calls=0
        try {VocalPlateauGate.apply(listOf(n(0,500,67),n(500,500,67)),t,{++calls>1});fail("ignored cancellation")}
        catch(_:InterruptedException){assertTrue(calls<=3)}
    }
}
