package cn.soundcore.instrument

import kotlin.math.*

/** pYIN-style candidate probabilities and sparse Viterbi tracking, on device.
 * The candidate/transition equations follow librosa 0.11 (ISC license).
 * No recording fingerprints, song templates, network calls or stored melodies.
 */
internal object StablePitchTracker {
    private const val RATE = 16000
    private const val HOP = 160
    private const val WINDOW = 1024
    private const val FMIN = 65.4
    private const val FMAX = 2100.0
    private const val BINS_PER_SEMITONE = 10
    private val bins = floor(120 * log2(FMAX / FMIN)).toInt() + 1
    private val minLag = floor(RATE / FMAX).toInt()
    private val maxLag = ceil(RATE / FMIN).toInt()
    private val beta = DoubleArray(100) { i ->
        fun cdf(x: Double) = 1 - (1 - x).pow(18) * (1 + 18 * x)
        cdf((i + 1) / 100.0) - cdf(i / 100.0)
    }
    private val expRank=DoubleArray(maxLag+1){exp(-2.0*it)}
    private val rankNorm=DoubleArray(maxLag+1){n->if(n==0)0.0 else (1-exp(-2.0))/(1-exp(-2.0*n))}
    private class Autocorrelation {
        private val size=2048
        private val real=DoubleArray(size);private val imag=DoubleArray(size)
        private val reverse=IntArray(size){Integer.reverse(it) ushr 21}
        private val cosine=DoubleArray(size/2){cos(2*PI*it/size)}
        private val sine=DoubleArray(size/2){sin(2*PI*it/size)}
        private fun fft(inverse:Boolean) {
            for(i in 0 until size) { val j=reverse[i];if(i<j) {
                var t=real[i];real[i]=real[j];real[j]=t;t=imag[i];imag[i]=imag[j];imag[j]=t } }
            var length=2
            while(length<=size) {
                val half=length/2;val stride=size/length
                var start=0
                while(start<size) {
                    for(j in 0 until half) {
                        val a=start+j;val b=a+half;val wr=cosine[j*stride]
                        val wi=if(inverse)sine[j*stride] else -sine[j*stride]
                        val tr=wr*real[b]-wi*imag[b];val ti=wr*imag[b]+wi*real[b]
                        real[b]=real[a]-tr;imag[b]=imag[a]-ti;real[a]+=tr;imag[a]+=ti
                    }
                    start+=length
                }
                length*=2
            }
        }
        fun compute(window:DoubleArray):DoubleArray {
            real.fill(0.0);imag.fill(0.0);window.copyInto(real)
            fft(false)
            for(i in 0 until size){real[i]=real[i]*real[i]+imag[i]*imag[i];imag[i]=0.0}
            fft(true)
            for(i in 0..maxLag)real[i]/=size
            return real
        }
    }
    data class Track(val pitch: DoubleArray, val probability: DoubleArray, val rms: DoubleArray)

    /** Finite-window squared differences require BOTH endpoint energies.
     * Legacy instrument tracking is retained for the existing instrument mode.
     */
    internal fun fillDifference(window:DoubleArray,correlation:DoubleArray,totalEnergy:Double,
        output:DoubleArray,exactWindow:Boolean) {
        var prefix=0.0;var suffix=0.0
        for(lag in 1..output.lastIndex) {
            prefix+=window[lag-1]*window[lag-1]
            suffix+=window[window.size-lag]*window[window.size-lag]
            val value=2*(totalEnergy-correlation[lag])-prefix-(if(exactWindow)suffix else 0.0)
            output[lag]=if(exactWindow)max(0.0,value) else value
        }
    }

    @JvmOverloads
    fun track(pcm: FloatArray, progress: (Int) -> Unit, cancelled: () -> Boolean,
        exactWindow:Boolean=true): Track {
        val frames = pcm.size / HOP + 1
        val stateCount = bins * 2
        // 40 seconds: under 10MB for all backpointers, not a dense HMM matrix.
        val back = ShortArray(frames * stateCount)
        val probability = DoubleArray(frames)
        val rms = DoubleArray(frames)
        var previous = DoubleArray(stateCount) { -ln(stateCount.toDouble()) }
        var next = DoubleArray(stateCount)
        val obs = DoubleArray(bins)
        val window = DoubleArray(WINDOW)
        val diff = DoubleArray(maxLag + 1)
        val yin = DoubleArray(maxLag - minLag + 1)
        val troughs = IntArray(yin.size)
        val candidate = DoubleArray(yin.size)
        val troughHeight=DoubleArray(yin.size)
        val autocorrelation=Autocorrelation()
        // max_transition_rate=20 oct/s -> width 21 in librosa at 10ms hops.
        val halfWidth = 10
        val transitionNorm = DoubleArray(bins) { p ->
            (max(0,p-halfWidth)..min(bins-1,p+halfWidth)).sumOf { q -> (halfWidth+1-abs(p-q)).toDouble() }
        }
        val logTransition = Array(bins) { dest -> DoubleArray(halfWidth*2+1) { d ->
            val src=dest+d-halfWidth
            if(src in 0 until bins) ln((halfWidth+1-abs(src-dest))/transitionNorm[src]) else Double.NEGATIVE_INFINITY
        } }
        val logStay=ln(.99);val logSwitch=ln(.01)
        for (frame in 0 until frames) {
            if (cancelled()) throw InterruptedException("已取消识别")
            var power=0.0
            for(j in -HOP until HOP) { val x=pcm.getOrElse(frame*HOP+j){0f}.toDouble();power+=x*x }
            rms[frame]=sqrt(power/(HOP*2))
            var totalEnergy=0.0
            for(j in window.indices) { val x=pcm.getOrElse(frame*HOP-WINDOW/2+j){0f}.toDouble()
                window[j]=x;totalEnergy+=x*x }
            obs.fill(0.0)
            if(totalEnergy>1e-12) {
                val correlation=autocorrelation.compute(window)
                fillDifference(window,correlation,totalEnergy,diff,exactWindow)
                var cumulative=0.0
                for(lag in 1..maxLag) {
                    cumulative+=diff[lag]
                    if(lag>=minLag) yin[lag-minLag]=diff[lag]/max(1e-300,cumulative/lag)
                }
                var count=0
                if(yin[0]<yin[1])troughs[count++]=0
                for(j in 1 until yin.lastIndex) if(yin[j]<yin[j-1] && yin[j]<=yin[j+1])troughs[count++]=j
                if(count>0) {
                    candidate.fill(0.0)
                    for(k in 0 until count) {
                        val j=troughs[k];var height=yin[j]
                        // At very high pitches, a whole-sample period grid
                        // can overstate the first trough and select its octave.
                        // Refine only this coarse-grid range, not vocal troughs.
                        if(minLag+j<12 && j>0 && j<yin.lastIndex) {
                            val a=yin[j+1]+yin[j-1]-2*yin[j];val b=(yin[j+1]-yin[j-1])/2
                            if(a>0 && abs(b)<abs(a))height=max(0.0,height-b*b/(2*a))
                        }
                        troughHeight[k]=height
                    }
                    var minimum=0
                    for(k in 1 until count)if(troughHeight[k]<troughHeight[minimum])minimum=k
                    var missedMass=0.0
                    for(t in 0 until 100) {
                        val threshold=(t+1)/100.0
                        var under=0
                        for(k in 0 until count)if(troughHeight[k]<threshold)under++
                        if(under==0)missedMass+=beta[t]
                        else {
                            val norm=rankNorm[under];var rank=0
                            for(k in 0 until count)if(troughHeight[k]<threshold)
                                candidate[k]+=expRank[rank++]*norm*beta[t]
                        }
                    }
                    candidate[minimum]+=.01*missedMass
                    for(k in 0 until count) {
                        val j=troughs[k]
                        var shift=0.0
                        if(j>0 && j<yin.lastIndex) {
                            val a=yin[j+1]+yin[j-1]-2*yin[j];val b=(yin[j+1]-yin[j-1])/2
                            if(abs(b)<abs(a))shift=-b/a
                        }
                        val hz=RATE/(minLag+j+shift)
                        val bin=(120*log2(hz/FMIN)).roundToInt().coerceIn(0,bins-1)
                        if(exactWindow)obs[bin]+=candidate[k] else obs[bin]=candidate[k]
                    }
                }
            }
            probability[frame]=obs.sum().coerceIn(0.0,1.0)
            val unvoicedLog=ln(max(1e-300,(1-probability[frame])/bins))
            var frameMax=Double.NEGATIVE_INFINITY
            for(dest in 0 until bins) {
                var bestV=Double.NEGATIVE_INFINITY;var bestU=Double.NEGATIVE_INFINITY
                var fromV=0;var fromU=0
                for(d in -halfWidth..halfWidth) {
                    val src=dest+d;if(src !in 0 until bins)continue
                    val trans=logTransition[dest][d+halfWidth]
                    var value=previous[src]+trans
                    if(value>bestV){bestV=value;fromV=src}
                    value=previous[src+bins]+trans
                    if(value>bestU){bestU=value;fromU=src+bins}
                }
                val vStay=bestV+logStay;val vSwitch=bestU+logSwitch
                val uStay=bestU+logStay;val uSwitch=bestV+logSwitch
                val fromVoiced=if(vStay>=vSwitch)fromV else fromU
                val fromUnvoiced=if(uStay>=uSwitch)fromU else fromV
                val emit=ln(max(1e-300,obs[dest]))
                // Initialization emits directly, matching uniform p_init.
                next[dest]=if(frame==0)emit else max(vStay,vSwitch)+emit
                next[dest+bins]=if(frame==0)unvoicedLog else max(uStay,uSwitch)+unvoicedLog
                back[frame*stateCount+dest]=fromVoiced.toShort();back[frame*stateCount+dest+bins]=fromUnvoiced.toShort()
                frameMax=max(frameMax,max(next[dest],next[dest+bins]))
            }
            for(s in next.indices)next[s]-=frameMax
            val swap=previous;previous=next;next=swap
            if(frame%20==0)progress(frame*85/frames)
        }
        val pitch=DoubleArray(frames){Double.NaN}
        var state=previous.indices.maxByOrNull{previous[it]}!!
        for(frame in frames-1 downTo 0) {
            if(cancelled())throw InterruptedException("已取消识别")
            if(state<bins)pitch[frame]=69+12*log2(FMIN/440)+state.toDouble()/BINS_PER_SEMITONE
            state=back[frame*stateCount+state].toInt()
        }
        progress(88)
        return Track(pitch,probability,rms)
    }
}
