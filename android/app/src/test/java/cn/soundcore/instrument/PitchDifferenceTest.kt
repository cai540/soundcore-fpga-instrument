package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class PitchDifferenceTest {
    @Test fun finiteWindowMatchesDirectSquaredDifferencesForChangingAmplitude() {
        val x=DoubleArray(1024){i->(.05+.35*i/1024)*sin(2*PI*233*i/16000)+.04}
        val correlation=DoubleArray(246){lag->(0 until x.size-lag).sumOf{i->x[i]*x[i+lag]}}
        val output=DoubleArray(correlation.size)
        StablePitchTracker.fillDifference(x,correlation,x.sumOf{it*it},output,true)
        for(lag in 1..output.lastIndex) {
            val direct=(0 until x.size-lag).sumOf{i->(x[i]-x[i+lag]).pow(2)}
            assertEquals("lag=$lag",direct,output[lag],1e-9)
        }
    }
    @Test fun periodicToneHasZeroDifferenceAtItsActualPeriod() {
        val x=DoubleArray(1024){sin(2*PI*it/40)}
        val correlation=DoubleArray(81){lag->(0 until x.size-lag).sumOf{i->x[i]*x[i+lag]}}
        val output=DoubleArray(81)
        StablePitchTracker.fillDifference(x,correlation,x.sumOf{it*it},output,true)
        assertEquals(0.0,output[40],1e-9)
        assertEquals(0.0,output[80],1e-9)
    }
}
