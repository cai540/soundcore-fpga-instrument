package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class ScopeAnalysisTest {
    @Test fun calibratedAmplitudeAndFrequencyAtEverySupportedRate(){
        for(rate in listOf(16000,44100,48000))for(n in listOf(1024,4096,16384)){
            val f=ScopeAnalysis.frame(FloatArray(n){(.4*sin(2*PI*997*it/rate)+.05).toFloat()},1,rate)
            assertEquals(997f,f.peaks.first().hz,rate/n*.08f+1f)
            assertEquals(-7.96f,f.peaks.first().dbFs,.4f)
            // A finite non-integer-period observation has a bounded residual mean.
            assertEquals(.05f,f.dc,(.4*rate/(PI*997*n)+.0001).toFloat())
            assertTrue(f.spectrum.all{it.isFinite()})
        }
    }
    @Test fun highResolutionSeparatesTheActual32DiagnosticFundamentals(){
        val frequencies=(60..91).map{440*2.0.pow((it-69)/12.0)}
        val a=FloatArray(16384){i->frequencies.sumOf{.012*sin(2*PI*it*i/48000)}.toFloat()}
        val frame=ScopeAnalysis.frame(a,7,48000)
        frequencies.forEach{hz->assertTrue("missing $hz",frame.peaks.any{abs(it.hz-hz)<2.0})}
        assertEquals(32,frame.peaks.count{p->frequencies.any{abs(p.hz-it)<2.0}})
    }
    @Test fun triggerAlignsDifferentInputPhasesWithoutAlteringSamples(){
        for(phase in listOf(.0,.35,1.7,3.4)){
            val f=ScopeAnalysis.frame(FloatArray(4096){(.2*sin(2*PI*440*it/48000+phase)).toFloat()},1,48000)
            val settings=ScopeSettings(msPerDiv=1f,ac=false)
            val window=ScopeMath.window(f,settings);assertTrue(window.triggered)
            val crossing=window.start+window.count/5
            assertTrue(f.samples[crossing-1]<0 && f.samples[crossing]>=0)
            assertTrue(window.start>=0 && window.start+window.count<=f.samples.size)
            assertEquals(480,window.count)
        }
    }
    @Test fun silenceDoesNotFalselyTriggerOrProducePitch(){
        val f=ScopeAnalysis.frame(FloatArray(4096),9,48000)
        assertTrue(f.peaks.isEmpty());assertFalse(ScopeMath.window(f,ScopeSettings()).triggered)
        assertEquals(-120f,f.rmsDb,0f);assertTrue(f.spectrum.all{it==-120f})
    }
    @Test fun oldTriggersCannotMakeAQuietInputLookLikeDelayedPlayback(){
        val a=FloatArray(16384){i->if(i<12000)(.3*sin(2*PI*440*i/48000)).toFloat()else 0f}
        val f=ScopeAnalysis.frame(a,6,48000,capturedNs=1_000_000_000L)
        val w=ScopeMath.window(f,ScopeSettings(msPerDiv=2f))
        assertFalse(w.triggered)
        assertTrue((w.start until w.start+w.count).all{f.samples[it]==0f})
        val tone=ScopeAnalysis.frame(FloatArray(4096){(.3*sin(2*PI*440*it/48000)).toFloat()},7,48000,capturedNs=1_000_000_000L)
        val triggered=ScopeMath.window(tone,ScopeSettings(msPerDiv=1f))
        val instant=ScopeMath.triggerTimeNs(tone,triggered)
        assertTrue(instant<tone.capturedNs)
        assertTrue(instant>tone.capturedNs-20_000_000L)
    }
    @Test fun invalidDataCannotEnterTheFft(){
        assertThrows(IllegalArgumentException::class.java){ScopeAnalysis.frame(FloatArray(1000),1)}
        assertThrows(IllegalArgumentException::class.java){ScopeAnalysis.frame(FloatArray(1024){Float.NaN},1)}
    }
    @Test fun normalAndFineFftUseOnlyLatestWindowWithNoOldSignalTail(){
        val a=FloatArray(16384){if(it<12288)(.2*sin(2*PI*400*it/48000)).toFloat()else (.2*sin(2*PI*1000*it/48000)).toFloat()}
        assertEquals(1000f,ScopeAnalysis.frame(a,2,48000,fftSize=4096).peaks.first().hz,1f)
    }
    @Test fun rapidReleasedTapsDoNotQueueALateMelody(){
        val notes=RealtimeNotes(intervalMs=0) // Actual BleController uses only the byte-aware UART pacer.
        repeat(300){notes.down(it%7,180);notes.up(it%7)}
        val p=notes.peek(0)!!;assertEquals(0,p.held);assertEquals(0,p.attacks)
        notes.sent(p,0);notes.down(2,180);assertNotNull(notes.peek(0))
        val pacer=BleWritePacer();pacer.started(9,0);assertEquals(12L,pacer.delayMs(0));pacer.completed(3);assertEquals(12L,pacer.delayMs(0))
    }
}
