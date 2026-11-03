package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test

class TonalBoundaryCoalescingTest {
    private val original=listOf(MelodyNote(0,300,64,.9f),MelodyNote(300,300,63,.7f))
    private val revised=original.map{it.copy(midi=64)}
    private val quiet=DoubleArray(61)
    private val rms=DoubleArray(61){.25}
    @Test fun refinementOnlyBoundaryCanBecomeOneContinuousNote() {
        val out=TonalBoundaryCoalescing.apply(original,revised,quiet,quiet,rms)
        assertEquals(1,out.size);assertEquals(0,out.first().startMs);assertEquals(600,out.first().durationMs)
    }
    @Test fun originalSamePitchRepeatAlwaysRemainsSeparate() {
        val a=original.map{it.copy(midi=64)};val b=a.map{it.copy(midi=63)}
        assertEquals(2,TonalBoundaryCoalescing.apply(a,b,quiet,quiet,rms).size)
    }
    @Test fun spectralOnsetProtectsBoundary() {
        val onset=quiet.copyOf();onset[30]=.31
        assertEquals(2,TonalBoundaryCoalescing.apply(original,revised,quiet,onset,rms).size)
    }
    @Test fun independentPhoneticChangeProtectsBoundary() {
        val phonetic=quiet.copyOf();phonetic[30]=.2
        assertEquals(2,TonalBoundaryCoalescing.apply(original,revised,phonetic,quiet,rms).size)
    }
    @Test fun zeroEnergyBoundaryIsNeverFilled() {
        val energy=rms.copyOf();energy[30]=0.0
        assertEquals(2,TonalBoundaryCoalescing.apply(original,revised,quiet,quiet,energy).size)
    }
    @Test fun evenATenMillisecondUnmeasuredGapRemains() {
        val a=listOf(original[0],original[1].copy(startMs=310));val b=a.map{it.copy(midi=64)}
        assertEquals(2,TonalBoundaryCoalescing.apply(a,b,quiet,quiet,rms).size)
    }
    @Test fun unavailableEvidenceKeepsBoundary() {
        assertEquals(2,TonalBoundaryCoalescing.apply(original,revised,null,quiet,rms).size)
    }
    @Test fun aValidatedRecoveredBoundaryOutranksWeakTonality() {
        val protected=booleanArrayOf(false,true)
        assertEquals(2,TonalBoundaryCoalescing.apply(original,revised,quiet,quiet,rms,protected,{false}).size)
    }
}
