package cn.soundcore.instrument
import kotlin.math.*

/** Band-limited streaming 16k PCM, aligned to the original source clock.
 * Call finish() at end of input to emit the lookahead/tail. Storage is bounded
 * by the filter, never the recording length. Native 16k input passes through.
 */
internal class PcmResampler(private val rate: Int, private val emit: (Float) -> Unit) {
    init { require(rate in 8000..192000) }
    private val radius=ceil(24.0*max(1.0,rate/16000.0)).toInt()
    private val taps=2*radius+1
    private val history=FloatArray(2*radius+4)
    private val phases=256
    private val kernels=if(rate==16000)DoubleArray(0) else DoubleArray((phases+1)*taps).also { coefficients ->
        val cutoff=.45*min(1.0,16000.0/rate)
        for(phase in 0..phases){var total=0.0
            for(k in 0 until taps){val d=k-radius-phase.toDouble()/phases
                val window=if(abs(d)>radius)0.0 else .42+.5*cos(PI*d/radius)+.08*cos(2*PI*d/radius)
                val sinc=if(abs(d)<1e-12)2*cutoff else sin(2*PI*cutoff*d)/(PI*d)
                val value=sinc*window;coefficients[phase*taps+k]=value;total+=value}
            for(k in 0 until taps)coefficients[phase*taps+k]/=total
        }
    }
    private var index=-1L
    private var output=0L
    private var finished=false

    fun push(sample:Float) {
        require(sample.isFinite());check(!finished)
        index++
        if(rate==16000){emit(sample);output++;return}
        history[(index%history.size).toInt()]=sample
        while(output*rate/16000+radius<=index)emitNext()
    }

    fun finish() {
        if(finished)return
        finished=true
        val count=((index+1)*16000+rate-1)/rate
        while(output<count)emitNext()
    }

    private fun emitNext() {
        val position=output*rate
        val center=position/16000
        val phase=(position%16000)*phases/16000.0
        val lower=phase.toInt();val fraction=phase-lower
        var absolute=center-radius
        var ring=((absolute%history.size+history.size)%history.size).toInt()
        var sum=0.0
        for(k in 0 until taps){
            if(absolute in 0..index){
                check(absolute>=index-history.size+1)
                val first=kernels[lower*taps+k];val second=kernels[(lower+1)*taps+k]
                sum+=history[ring]*(first+(second-first)*fraction)
            }
            absolute++;ring++;if(ring==history.size)ring=0
        }
        emit(sum.toFloat());output++
    }
}
