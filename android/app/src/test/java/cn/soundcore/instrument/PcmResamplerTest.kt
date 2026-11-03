package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class PcmResamplerTest {
    private fun resample(input:FloatArray,rate:Int):FloatArray {
        val output=ArrayList<Float>();val r=PcmResampler(rate){output.add(it)}
        input.forEach(r::push);r.finish();r.finish()
        return output.toFloatArray()
    }
    private fun amplitude(input:FloatArray,hz:Double):Double {
        var real=0.0;var imaginary=0.0;val start=input.size/4;val end=input.size*3/4
        for(i in start until end){val angle=2*PI*hz*i/16000;real+=input[i]*cos(angle);imaginary-=input[i]*sin(angle)}
        return 2*hypot(real,imaginary)/(end-start)
    }
    @Test fun rejects_high_frequency_alias_that_was_a_false_low_note() {
        for(rate in listOf(44100,48000)){
            val input=FloatArray(rate){sin(2*PI*15600*it/rate).toFloat()}
            val output=resample(input,rate)
            assertTrue("$rate alias amplitude ${amplitude(output,400.0)}",amplitude(output,400.0)<.0003)
        }
    }
    @Test fun preserves_normal_fundamentals_and_harmonics() {
        for(rate in listOf(44100,48000))for(hz in listOf(220.0,440.0,1000.0,3000.0)){
            val input=FloatArray(rate){sin(2*PI*hz*it/rate).toFloat()}
            val gain=amplitude(resample(input,rate),hz)
            assertTrue("$rate $hz amplitude $gain",gain in .98..1.02)
        }
    }
    @Test fun preserves_duration_and_flushes_short_tails() {
        for(rate in listOf(8000,11025,16000,22050,44100,48000,96000,192000)){
            for(count in listOf(0,1,7,rate/100,rate+3)){
                val output=resample(FloatArray(count){.2f},rate)
                assertEquals(((count.toLong()*16000+rate-1)/rate).toInt(),output.size)
                assertTrue(output.all{it.isFinite()})
            }
        }
    }
    @Test fun keeps_source_time_alignment_without_filter_delay() {
        for(rate in listOf(44100,48000,96000)){
            val input=FloatArray(rate);input[rate/2]=1f
            val output=resample(input,rate)
            val peak=output.indices.maxBy{abs(output[it])}
            assertTrue("peak at $peak",abs(peak-8000)<=1)
        }
    }
    @Test fun native_16k_is_bit_identical_and_invalid_values_fail() {
        val input=FloatArray(1001){sin(it*.1).toFloat()}
        assertArrayEquals(input,resample(input,16000),0f)
        val r=PcmResampler(44100){}
        assertTrue(runCatching{r.push(Float.NaN)}.isFailure)
        r.push(0f);r.finish()
        assertTrue(runCatching{r.push(0f)}.isFailure)
    }
    @Test fun batch_and_streaming_use_one_resampling_path() {
        val input=FloatArray(13003){sin(it*.037).toFloat()}
        assertArrayEquals(resample(input,44100),MelodyRecognition.resample(input,44100),0f)
    }
}
