package cn.soundcore.instrument

import kotlin.math.*

/** Validate a repeated-note register alias from independent PCM evidence.
 * A timbre change alone must NOT turn a real low fundamental into an octave.
 * Harmonic phase locking vetoes that error even with a weak fundamental and
 * wide common vibrato. No key, lyrics, template or file identity is an input.
 */
internal object VocalOctaveValidation {
    private class Fft(val size:Int) {
        val real=DoubleArray(size);val imag=DoubleArray(size)
        private val bits=Integer.numberOfTrailingZeros(size)
        private val reverse=IntArray(size){Integer.reverse(it) ushr (32-bits)}
        private val cosine=DoubleArray(size/2){cos(2*PI*it/size)}
        private val sine=DoubleArray(size/2){sin(2*PI*it/size)}
        fun run(inverse:Boolean=false) {
            for(i in 0 until size){val j=reverse[i];if(i<j){var t=real[i];real[i]=real[j];real[j]=t;t=imag[i];imag[i]=imag[j];imag[j]=t}}
            var length=2
            while(length<=size) {
                val half=length/2;val stride=size/length;var start=0
                while(start<size){for(j in 0 until half){val a=start+j;val b=a+half;val wr=cosine[j*stride];val wi=if(inverse)sine[j*stride] else -sine[j*stride]
                    val tr=wr*real[b]-wi*imag[b];val ti=wr*imag[b]+wi*real[b];real[b]=real[a]-tr;imag[b]=imag[a]-ti;real[a]+=tr;imag[a]+=ti};start+=length}
                length*=2
            }
            if(inverse)for(i in real.indices){real[i]/=size;imag[i]/=size}
        }
    }
    internal data class Parity(val ratio:Double,val concentration:Double)
    private class Probe {
        private val fft=Fft(8192)
        private val hann=DoubleArray(2048){.5-.5*cos(2*PI*it/2047)}
        private val window=DoubleArray(1024)
        private val beta=DoubleArray(100){i->
            fun cdf(x:Double)=1-(1-x).pow(18)*(1+18*x)
            cdf((i+1)/100.0)-cdf(i/100.0)
        }
        private fun lookup(a:DoubleArray,hz:Double):Double {
            val x=hz*8192/16000;val i=x.toInt();if(i<0 || i>=a.lastIndex)return 0.0
            return a[i]+(a[i+1]-a[i])*(x-i)
        }
        fun parity(pcm:FloatArray,ms:Int,note:Int):Parity {
            fft.real.fill(0.0);fft.imag.fill(0.0);var mean=0.0
            for(j in hann.indices)mean+=pcm.getOrElse(ms*16-1024+j){0f};mean/=2048
            for(j in hann.indices)fft.real[j]=(pcm.getOrElse(ms*16-1024+j){0f}-mean)*hann[j]
            fft.run();val mag=DoubleArray(4097){hypot(fft.real[it],fft.imag[it])};val total=mag.sumOf{it*it}
            var best=-1.0;var odd=0.0
            for(step in -15..15){val f=440*2.0.pow((note+step*.04-69)/12);var ev=0.0;var od=0.0
                for(h in intArrayOf(2,4,6,8))ev+=lookup(mag,h*f).pow(2)
                for(h in intArrayOf(1,3,5,7))od+=lookup(mag,h*f).pow(2)
                if(ev>best){best=ev;odd=od}
            }
            return Parity(odd/max(best,1e-12),best/max(total,1e-12))
        }
        /** Scalar pYIN candidate mass, before its temporally constrained path.
         * Direct finite-window differences avoid sharing mutable tracker state.
         */
        fun candidates(pcm:FloatArray,ms:Int,note:Int):Pair<Double,Double> {
            for(j in window.indices)window[j]=pcm.getOrElse(ms*16-512+j){0f}.toDouble()
            val difference=DoubleArray(246);var cumulative=0.0;val yin=DoubleArray(239)
            for(lag in 1..245){var sum=0.0;for(j in 0 until 1024-lag){val d=window[j]-window[j+lag];sum+=d*d};difference[lag]=sum;cumulative+=sum
                if(lag>=7)yin[lag-7]=sum/max(1e-300,cumulative/lag)}
            val troughs=mutableListOf<Int>();if(yin[0]<yin[1])troughs+=0
            for(j in 1 until yin.lastIndex)if(yin[j]<yin[j-1] && yin[j]<=yin[j+1])troughs+=j
            if(troughs.isEmpty())return 0.0 to 0.0
            val mass=DoubleArray(troughs.size);var missed=0.0
            for(t in 0..99){val under=troughs.indices.filter{yin[troughs[it]]<(t+1)/100.0}
                if(under.isEmpty())missed+=beta[t]
                else {val norm=(1-exp(-2.0))/(1-exp(-2.0*under.size));for((rank,k) in under.withIndex())mass[k]+=exp(-2.0*rank)*norm*beta[t]}
            }
            mass[troughs.indices.minBy{yin[troughs[it]]}]+=.01*missed
            var lo=0.0;var hi=0.0
            for(k in troughs.indices){val j=troughs[k];var shift=0.0
                if(j>0 && j<yin.lastIndex){val a=yin[j+1]+yin[j-1]-2*yin[j];val b=(yin[j+1]-yin[j-1])/2;if(abs(b)<abs(a))shift=-b/a}
                val pitch=69+12*log2(16000/(7+j+shift)/440)
                if(abs(pitch-note)<.9)lo=max(lo,mass[k])
                if(abs(pitch-note-12)<.9)hi=max(hi,mass[k])
            }
            return lo to hi
        }
    }
    internal data class Lock(val coherence:Double,val amplitudeRatio:Double)
    /** Analytic band envelopes preserve phase through wide pitch modulation.
     * A fixed-frequency STFT phase comparison does not have this invariance.
     */
    internal fun phaseLock(pcm:FloatArray,note:MelodyNote,cancelled:()->Boolean={false}):Lock? {
        val start=note.startMs*16;val end=(note.startMs+note.durationMs)*16;val margin=1600
        if(start<margin || end+margin>pcm.size || end-start<1600)return null
        val begin=start-margin;val finish=end+margin;val length=finish-begin
        var size=1;while(size<length)size*=2
        val fft=Fft(size);val window=DoubleArray(length)
        for(j in 0 until length) {
            if(j%4096==0 && cancelled())throw InterruptedException("已取消识别")
            val value=pcm[begin+j].toDouble();if(!value.isFinite())return null
            val taper=when {
                j<margin->sin(PI/2*j/(margin-1)).pow(2)
                j>=length-margin->sin(PI/2*(length-1-j)/(margin-1)).pow(2)
                else->1.0
            }
            window[j]=value*taper;fft.real[j]=window[j]
        }
        fft.run();val real=fft.real.copyOf();val imag=fft.imag.copyOf()
        val f=440*2.0.pow((note.midi-69)/12.0)
        // One broad upper-partial analytic phase carries the common FM.
        // Never isolate odd7 first with a fixed narrow band: its FM excursion
        // is seven times wider than the fundamental's excursion.
        for(bin in 0 until size) {
            val hz=if(bin<size/2)bin*16000.0/size else -1.0
            val distance=abs(hz-2*f)/f
            val gain=if(hz<=0)0.0 else ((.6-distance)/.2).coerceIn(0.0,1.0)
            fft.real[bin]=real[bin]*gain;fft.imag[bin]=imag[bin]*gain
        }
        fft.run(true);val upperReal=fft.real.copyOf();val upperImag=fft.imag.copyOf()
        val phase=DoubleArray(length)
        var previous=atan2(upperImag[0],upperReal[0]);var unwrapped=previous;phase[0]=unwrapped/2
        for(j in 1 until length) {
            val angle=atan2(upperImag[j],upperReal[j]);var delta=angle-previous
            while(delta>PI)delta-=2*PI;while(delta< -PI)delta+=2*PI
            unwrapped+=delta;phase[j]=unwrapped/2;previous=angle
        }
        val trim=min(640,(end-start)/6);val s=start-begin+trim;val e=end-begin-trim
        val indices=(s until e step 16).toList()
        if(indices.size<8)return null
        val amplitude=DoubleArray(indices.size){i->hypot(upperReal[indices[i]],upperImag[indices[i]])}
        fun median(a:DoubleArray):Double {val b=a.sortedArray();return if(b.size%2==1)b[b.size/2] else (b[b.size/2-1]+b[b.size/2])/2}
        val threshold=max(1e-7,median(amplitude)*.1)
        val good=indices.indices.filter{amplitude[it]>threshold}
        if(good.size<8 || good.size<indices.size*.8)return null
        val cutoff=min(40.0,f*.2)
        val lowpass=DoubleArray(size){bin->
            val hz=min(bin,size-bin)*16000.0/size
            ((cutoff-hz)/(cutoff*.25)).coerceIn(0.0,1.0)
        }
        var best=Lock(0.0,0.0)
        for(odd in intArrayOf(1,3,5,7)) {
            if(cancelled())throw InterruptedException("已取消识别")
            fft.real.fill(0.0);fft.imag.fill(0.0)
            for(j in 0 until length) {
                val angle=odd*phase[j]
                fft.real[j]=window[j]*cos(angle);fft.imag[j]=-window[j]*sin(angle)
            }
            fft.run()
            for(bin in 0 until size){fft.real[bin]*=lowpass[bin];fft.imag[bin]*=lowpass[bin]}
            fft.run(true)
            val ratios=DoubleArray(good.size);var squareReal=0.0;var squareImag=0.0;var mass=0.0
            for((k,index) in good.withIndex()) {
                val j=indices[index];val zr=fft.real[j];val zi=fft.imag[j];val amp=hypot(zr,zi)
                ratios[k]=amp/amplitude[index];mass+=amp
                // z has phase phiOdd-odd*phi2/2. Its amplitude-weighted
                // UNIT PHASE SQUARED preserves 2*phiOdd-odd*phi2 (the
                // conjugate of the old q), including the half-phase sign.
                // mean(z) would instead test the ambiguous half-angle.
                val weight=max(amp,1e-15)
                squareReal+=(zr*zr-zi*zi)/weight;squareImag+=2*zr*zi/weight
            }
            val ratio=median(ratios)
            val coherence=hypot(squareReal,squareImag)/max(mass,1e-15)
            if(ratio>=.02 && coherence>best.coherence)best=Lock(coherence,ratio)
        }
        return best
    }

    fun refine(pcm:FloatArray,notes:List<MelodyNote>,cancelled:()->Boolean={false}):List<MelodyNote> {
        val probe=Probe()
        return notes.mapIndexed{i,n->
            if(cancelled())throw InterruptedException("已取消识别")
            val prev=notes.getOrNull(i-1)
            if(prev==null || prev.midi!=n.midi || n.startMs-prev.startMs-prev.durationMs>50 || n.durationMs<250 || n.midi+12>96)return@mapIndexed n
            var valid=0;var strong=0;var parity=0;val after=mutableListOf<Double>()
            for(ms in n.startMs+30 until n.startMs+n.durationMs-20 step 50){if(cancelled())throw InterruptedException("已取消识别")
                val p=probe.parity(pcm,ms,n.midi);if(p.concentration<=.025)continue
                val (lo,hi)=probe.candidates(pcm,ms,n.midi);valid++;after+=p.ratio
                if(hi>=.25 && hi>=lo*1.15)strong++;if(p.ratio<.1)parity++
            }
            if(valid<4 || strong<3 || strong<valid*.35 || parity<valid*.7)return@mapIndexed n
            val before=mutableListOf<Double>()
            for(ms in max(prev.startMs,n.startMs-300) until n.startMs-20 step 50)before+=probe.parity(pcm,ms,n.midi).ratio
            if(before.isEmpty())return@mapIndexed n;before.sort();after.sort()
            fun median(a:List<Double>)=if(a.size%2==1)a[a.size/2] else (a[a.size/2-1]+a[a.size/2])/2
            if(median(before)<=median(after)*8)return@mapIndexed n
            val lock=phaseLock(pcm,n,cancelled)?:return@mapIndexed n
            // The maximum of several harmonic-family tests must show strong
            // phase coherence; moderate random coherence is not a veto.
            if(lock.coherence>=.8 && lock.amplitudeRatio>=.02)return@mapIndexed n
            n.copy(midi=n.midi+12)
        }
    }
}
