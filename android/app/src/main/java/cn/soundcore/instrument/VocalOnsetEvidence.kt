package cn.soundcore.instrument

import kotlin.math.*

/** Gain-normalized broad-band spectral change, independent of note/song labels.
 * Input is mono 16kHz PCM. Output frame i represents time i*10ms and contains
 * the maximum positive mel-envelope flux from i-80ms through i+100ms.
 * It is evidence for an onset, not a word recognizer or a hard truth label.
 */
internal object VocalOnsetEvidence {
    private const val FFT_SIZE=1024
    private const val WINDOW=512
    private const val HOP=160
    private const val BANDS=20
    private val hann=DoubleArray(WINDOW){.5-.5*cos(2*PI*it/(WINDOW-1))}
    private val reverse=IntArray(FFT_SIZE){Integer.reverse(it) ushr 22}
    private val cosine=DoubleArray(FFT_SIZE/2){cos(2*PI*it/FFT_SIZE)}
    private val sine=DoubleArray(FFT_SIZE/2){sin(2*PI*it/FFT_SIZE)}
    private val filters=run {
        fun mel(hz:Double)=2595*log10(1+hz/700)
        val low=mel(100.0);val high=mel(7500.0)
        val bounds=DoubleArray(BANDS+2){700*(10.0.pow((low+(high-low)*it/(BANDS+1))/2595)-1)}
        Array(BANDS){band->DoubleArray(FFT_SIZE/2+1){bin->
            val hz=bin*16000.0/FFT_SIZE
            max(0.0,min((hz-bounds[band])/(bounds[band+1]-bounds[band]),
                (bounds[band+2]-hz)/(bounds[band+2]-bounds[band+1])))
        }}
    }
    private fun fft(real:DoubleArray,imag:DoubleArray) {
        for(i in real.indices) {val j=reverse[i];if(i<j) {
            var a=real[i];real[i]=real[j];real[j]=a
            a=imag[i];imag[i]=imag[j];imag[j]=a
        }}
        var length=2
        while(length<=FFT_SIZE) {
            val half=length/2;val stride=FFT_SIZE/length;var start=0
            while(start<FFT_SIZE) {
                for(j in 0 until half) {
                    val a=start+j;val b=a+half;val wr=cosine[j*stride];val wi=-sine[j*stride]
                    val tr=wr*real[b]-wi*imag[b];val ti=wr*imag[b]+wi*real[b]
                    real[b]=real[a]-tr;imag[b]=imag[a]-ti;real[a]+=tr;imag[a]+=ti
                }
                start+=length
            }
            length*=2
        }
    }
    @JvmOverloads
    fun onsetEvidence(pcm16k:FloatArray,cancelled:()->Boolean={false}):DoubleArray {
        val frames=pcm16k.size/HOP+1
        val raw=DoubleArray(frames);val previous=DoubleArray(BANDS)
        val real=DoubleArray(FFT_SIZE);val imag=DoubleArray(FFT_SIZE)
        val power=DoubleArray(FFT_SIZE/2+1);val envelope=DoubleArray(BANDS)
        for(frame in 0 until frames) {
            if(frame%16==0 && cancelled())throw InterruptedException("已取消识别")
            real.fill(0.0);imag.fill(0.0)
            for(j in 0 until WINDOW)real[j]=pcm16k.getOrElse(frame*HOP-WINDOW/2+j){0f}*hann[j]
            fft(real,imag)
            for(bin in power.indices)power[bin]=real[bin]*real[bin]+imag[bin]*imag[bin]
            var total=0.0
            for(band in 0 until BANDS) {
                var energy=0.0
                for(bin in power.indices)energy+=power[bin]*filters[band][bin]
                envelope[band]=energy;total+=energy
            }
            var flux=0.0
            for(band in 0 until BANDS) {
                envelope[band]/=total+1e-12
                flux+=max(0.0,envelope[band]-previous[band]);previous[band]=envelope[band]
            }
            if(frame>0)raw[frame]=flux
        }
        return DoubleArray(frames){i->
            var peak=0.0
            for(j in max(0,i-8)..min(frames-1,i+10))peak=max(peak,raw[j])
            peak
        }
    }
}
