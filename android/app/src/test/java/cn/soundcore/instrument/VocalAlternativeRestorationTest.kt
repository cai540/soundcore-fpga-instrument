package cn.soundcore.instrument
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class VocalAlternativeRestorationTest {
 private fun note(start:Int,duration:Int,pitch:Int)=MelodyNote(start,duration,pitch,.8f)
 private fun run(p:DoubleArray,alt:List<MelodyNote>,old:Int=74,cue:Boolean=true,prob:DoubleArray=DoubleArray(p.size){.8}):List<MelodyNote> {
  val v=DoubleArray(p.size)
  if(cue)for(n in alt.drop(1))for(i in v.indices)v[i]+=.15*exp(-.5*((i-n.startMs/10)/3.0).pow(2))
  return VocalAlternativeRestoration.apply(listOf(note(0,p.size*10,old)),alt,StablePitchTracker.Track(p,prob,DoubleArray(p.size){.25}),v)
 }
 @Test fun aStableMissingPlateauCanBeRestored() {
  val p=DoubleArray(95){if(it<60)74.0 else 76.0}
  assertEquals(listOf(74,76),run(p,listOf(note(0,600,74),note(600,350,76))).map{it.midi})
 }
 @Test fun observedWideVibratoRetainsRealNewMainNotes() {
  for(phase in listOf(0.0,.6,1.7,2.9)) {
   val p=DoubleArray(105){if(it<60)74.0 else 76+.8*sin(2*PI*5.3*(it-60)*.01+phase)}
   assertEquals(listOf(74,76),run(p,listOf(note(0,600,74),note(600,450,76))).map{it.midi})
  }
 }
 @Test fun singleArchesNeverBecomeInventedPlateaus() {
  for(length in listOf(25,30,35,39,45,50,60,70))for(amp in listOf(2.0,2.6,3.0,3.4))for(head in listOf(false,true)) {
   val arch=DoubleArray(length){74+amp*sin(PI*it/(length-1))};val n=Math.rint(arch.average()).toInt()
   val p=if(head)arch+DoubleArray(60){74.0}else DoubleArray(60){74.0}+arch
   val alt=if(head)listOf(note(0,length*10,n),note(length*10,600,74))else listOf(note(0,600,74),note(600,length*10,n))
   assertEquals("len=$length amp=$amp head=$head",listOf(note(0,p.size*10,74)),run(p,alt))
  }
 }
 @Test fun aContinuousMonotoneGlideIsNotANewMainNote() {
  for(length in listOf(25,35,50,70))for(direction in listOf(-1,1)) {
   val ramp=DoubleArray(length){74+direction*4.0*it/(length-1)}
   val p=DoubleArray(60){74.0}+ramp;val n=Math.rint(ramp.average()).toInt()
   assertEquals(listOf(note(0,p.size*10,74)),run(p,listOf(note(0,600,74),note(600,length*10,n))))
  }
 }
 @Test fun aSingleZeroMeanVibratoCannotBeSplitByAnAlternativeLabel() {
  for(phase in listOf(0.0,.6,1.7,2.9))for(f in listOf(3.0,5.3,7.0))for(amp in listOf(.6,.9,1.1)) {
   val p=DoubleArray(180){74+amp*sin(2*PI*f*it*.01+phase)}
   assertEquals(listOf(note(0,1800,74)),run(p,listOf(note(0,600,74),note(600,600,75),note(1200,600,74))))
  }
 }
 @Test fun missingPhoneticEvidenceKeepsTheTrustedEvent() {
  val p=DoubleArray(95){if(it<60)74.0 else 76.0}
  assertEquals(listOf(note(0,950,74)),run(p,listOf(note(0,600,74),note(600,350,76)),cue=false))
 }
 @Test fun nonfinitePhoneticEvidenceCannotAuthorizeACut() {
  val p=DoubleArray(95){if(it<60)74.0 else 76.0};val v=DoubleArray(95){.15}
  val trusted=listOf(note(0,950,74));val alt=listOf(note(0,600,74),note(600,350,76))
  val track=StablePitchTracker.Track(p,DoubleArray(95){.8},DoubleArray(95){.25})
  for(value in listOf(Double.NaN,Double.POSITIVE_INFINITY,Double.NEGATIVE_INFINITY)) {
   v[60]=value;assertEquals(trusted,VocalAlternativeRestoration.apply(trusted,alt,track,v))
  }
 }
 @Test fun aHypothesisDoesNotOverrideAnUnchangedMeasuredPitch() {
  val p=DoubleArray(95){74.0}
  assertEquals(listOf(note(0,950,74)),run(p,listOf(note(0,600,74),note(600,350,76))))
 }
 @Test fun fallbackOnlyNewPitchIsInsufficientEvidence() {
  val p=DoubleArray(95){if(it<60)74.0 else 76.0};val prob=DoubleArray(95){if(it<60).8 else .01}
  assertEquals(listOf(note(0,950,74)),run(p,listOf(note(0,600,74),note(600,350,76)),prob=prob))
 }
 @Test fun interpolationCannotInventACompletedCycle() {
  val p=DoubleArray(105){if(it<60)74.0 else 76+.8*sin(2*PI*5.3*(it-60)*.01+1.7)}
  for(i in 64..101 step 3)p[i]=Double.NaN
  assertFalse(VocalAlternativeRestoration.observedCycle(p.copyOfRange(60,105)))
  assertEquals(listOf(note(0,1050,74)),run(p,listOf(note(0,600,74),note(600,450,76))))
 }
 @Test fun aMonotoneAnchorCannotJustifyANarrowReturn() {
  val p=DoubleArray(123){i->when {i<30->68.0+1.5*i/29;i<78->70+.8*sin(2*PI*5.3*(i-30)*.01);else->69+.8*sin(2*PI*5.3*(i-78)*.01)}}
  assertEquals(listOf(note(0,1230,69)),run(p,listOf(note(0,300,69),note(300,480,70),note(780,450,69)),old=69))
 }
 @Test fun anExistingRapidChromaticSequenceIsImmutable() {
  val old=(0..3).map{note(it*150,150,60+it)};val t=StablePitchTracker.Track(DoubleArray(60){60.0},DoubleArray(60){.8},DoubleArray(60){.25})
  assertEquals(old,VocalAlternativeRestoration.apply(old,listOf(note(0,600,60)),t,DoubleArray(60){.15}))
 }
 @Test fun nonGridEndsAndRealGapsRemainExact() {
  val p=DoubleArray(220){74.0};for(i in 61..105)p[i]=76.0
  val trusted=listOf(note(3,1050,74),note(1203,600,74));val alt=listOf(note(3,600,74),note(603,450,76),note(1203,600,74))
  val v=DoubleArray(220){.15};val t=StablePitchTracker.Track(p,DoubleArray(220){.8},DoubleArray(220){.25})
  val out=VocalAlternativeRestoration.apply(trusted,alt,t,v)
  assertEquals(3,out.first().startMs);assertEquals(1053,out[1].startMs+out[1].durationMs);assertEquals(trusted[1],out.last())
 }
 @Test fun aRealGapInTheAlternativeIsNotFilled() {
  val p=DoubleArray(100){if(it<60)74.0 else 76.0}
  assertEquals(listOf(note(0,1000,74)),run(p,listOf(note(0,600,74),note(610,390,76))))
 }
 @Test fun cancellationIsHonoured() {
  val t=StablePitchTracker.Track(DoubleArray(100){74.0},DoubleArray(100){.8},DoubleArray(100){.25})
  try {VocalAlternativeRestoration.apply(listOf(note(0,1000,74)),emptyList(),t,DoubleArray(100),{true});fail("ignored cancellation")}
  catch(_:InterruptedException) { }
 }
}
