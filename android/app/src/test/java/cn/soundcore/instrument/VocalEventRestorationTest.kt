package cn.soundcore.instrument
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class VocalEventRestorationTest {
 private data class Fixture(val track:StablePitchTracker.Track,val novelty:DoubleArray)
 private fun fixture(notes:List<Int>,durations:List<Int>,amp:Double,phase:Double):Fixture {
  val count=durations.sum()/10;val p=DoubleArray(count);val q=DoubleArray(count);val r=DoubleArray(count){.25};val novelty=DoubleArray(count)
  var at=0
  for(i in notes.indices) {
   val length=durations[i]/10
   for(j in 0 until length) {
    p[at+j]=notes[i]+amp*sin(2*PI*5.3*j*.01+phase+i*.73)
    q[at+j]=.8-.6*max(0.0,sin((at+j)*.01*2*PI*5.3+phase))
   }
   at+=length
   if(i<notes.lastIndex)for(j in novelty.indices)novelty[j]+=.14*exp(-.5*((j-at)/4.0).pow(2))
  }
  return Fixture(StablePitchTracker.Track(p,q,r),novelty)
 }
 private fun restores(notes:List<Int>,durations:List<Int>,seed:Int) {
  for(phase in listOf(0.0,.6,1.7,2.9)) {
   val f=fixture(notes,durations,1.0,phase)
   val n=MelodyNote(0,durations.sum(),seed,.5f)
   val out=VocalEventRestoration.refine(listOf(n),f.track,f.novelty)
   assertEquals("phase=$phase",notes,out.map{it.midi})
   assertEquals(0,out.first().startMs);assertEquals(n.durationMs,out.last().startMs+out.last().durationMs)
  }
 }
 @Test fun realSemitoneChangesSurviveWideVibratoAndBiasedProbability()=restores(listOf(70,69),listOf(450,450),69)
 @Test fun realWholeToneChangesSurviveWideVibrato()=restores(listOf(79,77),listOf(450,450),79)
 @Test fun realReturningPlateausSurviveWideVibrato()=restores(listOf(79,81,79),listOf(300,300,300),79)
 @Test fun aSingleWideVibratoNoteIsNotSplitByFalseSpectralCues() {
  for(n in listOf(60,70,79)) {
   val f=fixture(listOf(n),listOf(1800),1.1,.8)
   for(k in listOf(25,60,110,150))for(j in f.novelty.indices)f.novelty[j]+=.15*exp(-.5*((j-k)/3.0).pow(2))
   val seed=MelodyNote(0,1800,n,.5f)
   assertEquals(listOf(seed),VocalEventRestoration.refine(listOf(seed),f.track,f.novelty))
  }
 }
 @Test fun existingRapidChromaticNotesAndBoundariesAreImmutable() {
  val f=fixture(listOf(60,61,62,63),List(4){150},.1,.8)
  val seeds=(0..3).map{MelodyNote(it*150,150,60+it,.9f)}
  assertEquals(seeds,VocalEventRestoration.refine(seeds,f.track,f.novelty))
 }
 @Test fun restoredChildrenNeedMeasuredVoicedEvidenceNotInterpolation() {
  val f=fixture(listOf(70,69),listOf(450,450),1.0,.6)
  for(i in 45 until 90)f.track.probability[i]=.01
  val seed=MelodyNote(0,900,69,.5f)
  assertEquals(listOf(seed),VocalEventRestoration.refine(listOf(seed),f.track,f.novelty))
 }
 @Test fun clearSemitoneReturnIsNotMistakenForAnAmbiguousBend()=restores(listOf(60,61,60),listOf(400,400,400),60)
 @Test fun nonFrameAlignedSeedEdgesAndRealGapArePreserved() {
  val f=fixture(listOf(70,69),listOf(450,450),1.0,.6)
  val p=DoubleArray(300){Double.NaN};val q=DoubleArray(300){.01};val r=DoubleArray(300);val novelty=DoubleArray(300)
  for(i in 0..99){p[i]=60.0;q[i]=.9;r[i]=.25}
  for(i in f.track.pitch.indices){p[i+150]=f.track.pitch[i];q[i+150]=f.track.probability[i];r[i+150]=.25;novelty[i+150]=f.novelty[i]}
  val before=MelodyNote(0,1001,60,.9f);val seed=MelodyNote(1503,903,69,.5f)
  val out=VocalEventRestoration.refine(listOf(before,seed),StablePitchTracker.Track(p,q,r),novelty)
  assertEquals(before,out.first());assertEquals(70,out[1].midi)
  assertEquals(1503,out[1].startMs);assertEquals(2406,out.last().startMs+out.last().durationMs)
  assertTrue(out.zipWithNext().all{it.first.startMs+it.first.durationMs<=it.second.startMs})
 }
 @Test fun cancellationStopsRestoration() {
  val f=fixture(listOf(70,69),listOf(450,450),1.0,.6)
  try {VocalEventRestoration.refine(listOf(MelodyNote(0,900,69,.5f)),f.track,f.novelty,{true});fail("ignored cancellation")}
  catch(_:InterruptedException) { }
 }
}
