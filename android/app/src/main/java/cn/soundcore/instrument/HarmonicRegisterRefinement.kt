package cn.soundcore.instrument

import kotlin.math.*

/** Independent spectral evidence for register (period-multiple) errors only.
 * The pYIN Track.probability is TOTAL VOICED MASS, not confidence that the
 * selected pitch/register is correct. It must not veto this comparison.
 * No song, key, target note, lyrics or reference data is an input.
 */
internal object HarmonicRegisterRefinement {
    private val shifts=doubleArrayOf(-12*log2(3.0),-12.0,0.0,12.0,12*log2(3.0))
    private const val STEP=5 // 50 ms on the existing 10 ms track
    data class Evidence(val shift:Double,val pitch:Double,val score:Double)

    private class Spectrum {
        private val size=8192;private val count=size/2+1
        private val real=DoubleArray(size);private val imag=DoubleArray(size)
        private val reverse=IntArray(size){Integer.reverse(it) ushr 19}
        private val cosine=DoubleArray(size/2){cos(2*PI*it/size)}
        private val sine=DoubleArray(size/2){sin(2*PI*it/size)}
        private val hann=DoubleArray(2048){.5-.5*cos(2*PI*it/2047)}
        private fun fft() {
            for(i in 0 until size) { val j=reverse[i];if(i<j) {
                var t=real[i];real[i]=real[j];real[j]=t;t=imag[i];imag[i]=imag[j];imag[j]=t
            } }
            var length=2
            while(length<=size) {
                val half=length/2;val stride=size/length;var start=0
                while(start<size) {
                    for(j in 0 until half) {
                        val a=start+j;val b=a+half;val wr=cosine[j*stride];val wi=-sine[j*stride]
                        val tr=wr*real[b]-wi*imag[b];val ti=wr*imag[b]+wi*real[b]
                        real[b]=real[a]-tr;imag[b]=imag[a]-ti;real[a]+=tr;imag[a]+=ti
                    };start+=length
                };length*=2
            }
        }
        private fun box(a:DoubleArray,radius:Int):DoubleArray {
            val prefix=DoubleArray(a.size+1);for(i in a.indices)prefix[i+1]=prefix[i]+a[i]
            return DoubleArray(a.size){i->
                val lo=max(0,i-radius);val hi=min(a.size,i+radius+1)
                (prefix[hi]-prefix[lo])/(hi-lo)
            }
        }
        fun evidence(pcm:FloatArray,sample:Int,pitch:Double):List<Evidence> {
            real.fill(0.0);imag.fill(0.0)
            var mean=0.0
            for(j in hann.indices)mean+=pcm.getOrElse(sample+j-1024){0f}
            mean/=hann.size
            for(j in hann.indices)real[j]=(pcm.getOrElse(sample+j-1024){0f}-mean)*hann[j]
            fft()
            val mag=DoubleArray(count){hypot(real[it],imag[it])}
            val peak=mag.max();if(peak<1e-8)return shifts.map{Evidence(it,pitch+it,0.0)}
            // Three running-mean passes approximate a ~62Hz Gaussian spectral
            // envelope, retaining narrow harmonic peaks and reducing formants.
            var smooth=mag
            repeat(3){smooth=box(smooth,32)}
            val white=DoubleArray(count){ln1p(mag[it]/max(smooth[it],peak*.01))}
            fun lookup(hz:Double):Double {
                val x=hz*size/16000;val p=x.toInt()
                if(p<0 || p>=white.lastIndex)return 0.0
                return white[p]+(white[p+1]-white[p])*(x-p)
            }
            return shifts.map { shift ->
                val center=pitch+shift
                if(center !in 36.0..96.0)Evidence(shift,center,Double.NEGATIVE_INFINITY)
                else {
                    var best=Double.NEGATIVE_INFINITY;var bestPitch=center
                    for(step in -15..15) {
                        val n=center+step*.04;val hz=440*2.0.pow((n-69)/12)
                        var harmonic=0.0;var interleaved=0.0;var norm=0.0
                        for(h in 1..8) {
                            val weight=1/sqrt(h.toDouble());norm+=weight
                            harmonic+=weight*lookup(h*hz)
                            interleaved+=weight*lookup((h+.5)*hz)
                        }
                        val score=(harmonic-.5*interleaved)/norm
                        if(score>best){best=score;bestPitch=n}
                    }
                    Evidence(shift,bestPitch,best)
                }
            }
        }
    }

    /** Scores in order: /3, /2, current, x2, x3. Useful for acoustic tests. */
    fun evidence(pcm:FloatArray,sample:Int,pitch:Double):List<Evidence> = Spectrum().evidence(pcm,sample,pitch)

    fun refine(pcm:FloatArray,track:StablePitchTracker.Track,cancelled:()->Boolean={false}):StablePitchTracker.Track {
        val pitch=track.pitch.copyOf();val samples=(pitch.size+STEP-1)/STEP
        if(samples<3)return track
        val spectrum=Spectrum();val scores=Array(samples){DoubleArray(shifts.size){Double.NEGATIVE_INFINITY}}
        val valid=BooleanArray(samples);val floor=max(.0025,(track.rms.maxOrNull()?:0.0)*.035)
        for(k in 0 until samples) {
            if(cancelled())throw InterruptedException("已取消识别")
            val i=min(pitch.lastIndex,k*STEP)
            if(!pitch[i].isFinite() || track.rms[i]<floor)continue
            val evidence=spectrum.evidence(pcm,i*160,pitch[i])
            for(s in shifts.indices)scores[k][s]=evidence[s].score
            valid[k]=scores[k][2]>=.35
        }
        val stateCount=shifts.size;var previous=DoubleArray(stateCount){if(it==2)0.0 else .3}
        val back=IntArray(samples*stateCount)
        for(k in 0 until samples) {
            if(cancelled())throw InterruptedException("已取消识别")
            val base=scores[k][2]
            val now=DoubleArray(stateCount)
            for(s in 0 until stateCount) {
                val benefit=if(valid[k] && scores[k][s].isFinite())scores[k][s]-base else if(s==2)0.0 else -.08
                val emission=-benefit+(if(s==2)0.0 else .04)
                var source=s;var best=previous[s]
                for(q in 0 until stateCount)if(q!=s && previous[q]+.45<best){best=previous[q]+.45;source=q}
                now[s]=best+emission;back[k*stateCount+s]=source
            }
            previous=now
        }
        var state=previous.indices.minBy{previous[it]};val decoded=IntArray(samples)
        for(k in samples-1 downTo 0){decoded[k]=state;state=back[k*stateCount+state]}
        var start=0
        while(start<samples) {
            var end=start+1;while(end<samples && decoded[end]==decoded[start])end++
            val s=decoded[start]
            if(s!=2 && end-start>=3) {
                val good=(start until end).filter{valid[it]}
                val support=good.count { scores[it][s]>=.65 && scores[it][s]-scores[it][2]>=.12 && scores[it][s]>=scores[it][2]*1.12 }
                // At least three agreeing spectral observations, plus temporal
                // evidence accumulated by DP. Keep uncertain cases unchanged.
                if(support>=3 && support>=ceil(good.size*.6).toInt()) {
                    val begin=max(0,start*STEP-STEP/2);val finish=min(pitch.size,end*STEP-STEP/2)
                    val corrected=(begin until finish).mapNotNull{ i ->
                        track.pitch[i].takeIf{it.isFinite()}?.plus(shifts[s])
                    }.sorted()
                    val center=corrected.getOrNull(corrected.size/2)
                    fun context(a:Int,b:Int):Double? {
                        val values=(a until b).mapNotNull{track.pitch[it].takeIf{p->p.isFinite()}}.sorted()
                        return if(values.size>=8)values[values.size/2] else null
                    }
                    val left=context(max(0,begin-100),begin)
                    val right=context(finish,min(pitch.size,finish+100))
                    val sideSupport=center!=null && (left?.let{abs(it-center)<=4}==true || right?.let{abs(it-center)<=4}==true)
                    // Residual bass/second voices can win a spectral comb in
                    // vocal-separated files. Require register continuity, or
                    // an almost unanimous whole-clip register hypothesis.
                    val globalSupport=good.size>=12 && good.size>=valid.count{it}*.8
                    if(sideSupport || globalSupport)
                        for(i in begin until finish)if(pitch[i].isFinite())pitch[i]+=shifts[s]
                }
            }
            start=end
        }
        return StablePitchTracker.Track(pitch,track.probability,track.rms)
    }
}
