package cn.soundcore.instrument

import kotlin.math.*

data class ScopePeak(val hz:Float,val dbFs:Float)
data class LiveAudioFrame(
    val samples:FloatArray,val spectrum:FloatArray,val rmsDb:Float,val number:Long,
    val sampleRate:Int=16000,val capturedNs:Long=0,val timestampReliable:Boolean=false,
    val analysisMs:Float=0f,val peak:Float=0f,val dc:Float=0f,
    val peaks:List<ScopePeak> = emptyList(),val fftSize:Int=samples.size
)

/** Microphone amplitudes are relative to digital full scale, never volts or SPL. */
data class ScopeSettings(
    val msPerDiv:Float=2f,val fsPerDiv:Float=.25f,val trigger:Float=0f,
    val rising:Boolean=true,val ac:Boolean=true,val highResolution:Boolean=false,
    val state:Int=0, // 0 run, 1 frozen, 2 single armed, 3 single held
    val focusedSpectrum:Boolean=false,val xyDelayMs:Float=0f // 0 = quarter period of dominant peak
)

internal object ScopeAnalysis {
    const val RATE=16000
    const val SIZE=1024
    private class Plan(val n:Int) {
        val window=DoubleArray(n){.5-.5*cos(2*PI*it/(n-1))}
        val sum=window.sum()
        val bits=Integer.numberOfTrailingZeros(n)
        val reverse=IntArray(n){Integer.reverse(it) ushr (32-bits)}
        val cosines=DoubleArray(n/2){cos(-2*PI*it/n)}
        val sines=DoubleArray(n/2){sin(-2*PI*it/n)}
        val re=DoubleArray(n);val im=DoubleArray(n)
    }
    private val plans=object:LinkedHashMap<Int,Plan>(4,.75f,true){
        override fun removeEldestEntry(eldest:MutableMap.MutableEntry<Int,Plan>?)=size>4
    }
    fun frame(samples:FloatArray,number:Long,sampleRate:Int=RATE,capturedNs:Long=0,
              timestampReliable:Boolean=false,fftSize:Int=samples.size):LiveAudioFrame {
        require(fftSize in 256..16384 && fftSize and (fftSize-1)==0 && samples.size>=fftSize)
        require(sampleRate>=8000 && samples.all{it.isFinite()})
        val began=System.nanoTime()
        val p=synchronized(plans){plans.getOrPut(fftSize){Plan(fftSize)}}
        val offset=samples.size-fftSize
        val dc=(offset until samples.size).sumOf{samples[it].toDouble()}/fftSize
        val spectrum=synchronized(p){
            for(i in 0 until fftSize){p.re[p.reverse[i]]=(samples[offset+i]-dc)*p.window[i];p.im[i]=0.0}
            var length=2
            while(length<=fftSize){val half=length/2;val step=fftSize/length
                for(base in 0 until fftSize step length)for(j in 0 until half){
                    val a=base+j;val b=a+half;val k=j*step
                    val r=p.cosines[k]*p.re[b]-p.sines[k]*p.im[b]
                    val im=p.cosines[k]*p.im[b]+p.sines[k]*p.re[b]
                    p.re[b]=p.re[a]-r;p.im[b]=p.im[a]-im;p.re[a]+=r;p.im[a]+=im
                };length*=2
            }
            FloatArray(fftSize/2){i->(20*log10(max(1e-6,hypot(p.re[i],p.im[i])*(if(i==0)1 else 2)/p.sum))).toFloat()}
        }
        val maxima=(2 until spectrum.lastIndex).filter{i->spectrum[i]>spectrum[i-1] && spectrum[i]>=spectrum[i+1] && i*sampleRate/fftSize>=40 && spectrum[i]>-85}
        val peaks=maxima.sortedByDescending{spectrum[it]}.take(40).map{i->
            val a=spectrum[i-1];val b=spectrum[i];val c=spectrum[i+1]
            val d=(.5f*(a-c)/(a-2*b+c)).let{if(it.isFinite())it.coerceIn(-.5f,.5f)else 0f}
            ScopePeak((i+d)*sampleRate/fftSize,b-.25f*(a-c)*d)
        }
        val rms=sqrt((offset until samples.size).sumOf{samples[it].toDouble()*samples[it]}/fftSize)
        return LiveAudioFrame(samples.copyOf(),spectrum,(20*log10(max(1e-6,rms))).toFloat(),number,
            sampleRate,capturedNs,timestampReliable,(System.nanoTime()-began)/1e6f,
            (offset until samples.size).maxOf{abs(samples[it])},dc.toFloat(),peaks,fftSize)
    }
}

internal data class ScopeWindow(val start:Int,val count:Int,val triggered:Boolean) {
    fun milliseconds(rate:Int)=(count-1)*1000f/rate
}
internal object ScopeMath {
    /** Latest complete triggered window. No interpolation or manufactured samples. */
    fun window(frame:LiveAudioFrame,s:ScopeSettings):ScopeWindow {
        val a=frame.samples;val count=(s.msPerDiv*10*frame.sampleRate/1000).roundToInt().coerceIn(16,a.size)
        val pre=count/5;val bias=if(s.ac)frame.dc else 0f
        // AUTO mode must not keep showing a trigger from hundreds of ms ago.
        val oldest=max(max(1,pre),a.size-2*count+pre)
        for(i in a.size-count+pre downTo oldest){
            val left=a[i-1]-bias;val right=a[i]-bias
            if(if(s.rising)left<s.trigger && right>=s.trigger else left>s.trigger && right<=s.trigger)
                return ScopeWindow(i-pre,count,true)
        }
        return ScopeWindow(a.size-count,count,false)
    }
    fun triggerTimeNs(frame:LiveAudioFrame,w:ScopeWindow):Long =
        frame.capturedNs-(frame.samples.lastIndex-(w.start+w.count/5))*1_000_000_000L/frame.sampleRate
    fun auto(frame:LiveAudioFrame,current:ScopeSettings):ScopeSettings {
        val values=listOf(.01f,.02f,.05f,.1f,.2f,.25f,.5f)
        val gain=values.firstOrNull{it*3.2f>=frame.peak}?:.5f
        val hz=frame.peaks.firstOrNull()?.hz?:200f
        val time=listOf(.2f,.5f,1f,2f,5f,10f,20f).minBy{abs(it-400f/hz)}
        return current.copy(fsPerDiv=gain,msPerDiv=time,trigger=0f)
    }
    fun delay(frame:LiveAudioFrame,s:ScopeSettings):Int {
        val ms=if(s.xyDelayMs>0)s.xyDelayMs else 250f/(frame.peaks.firstOrNull()?.hz?:250f)
        return (ms*frame.sampleRate/1000).roundToInt().coerceIn(1,frame.samples.size/4)
    }
}
