package cn.soundcore.instrument

import kotlin.math.*

/** Soft before/after phonetic-envelope change, independent of F0 or lyrics.
 * It may propose a note-change location without a loudness trough. It does NOT
 * force same-pitch reattacks: breath and consonant evidence can overlap.
 * 16kHz mono PCM, 10ms output grid. Meant for offline <=40s recognition.
 */
internal object VocalBoundaryEvidence {
    private const val SIZE=1024
    private const val WINDOW=512
    private const val HOP=160
    private const val BANDS=20
    private val hann=DoubleArray(WINDOW){.5-.5*cos(2*PI*it/(WINDOW-1))}
    private val reverse=IntArray(SIZE){Integer.reverse(it) ushr 22}
    private val cosine=DoubleArray(SIZE/2){cos(2*PI*it/SIZE)}
    private val sine=DoubleArray(SIZE/2){sin(2*PI*it/SIZE)}
    private val filters=run {
        fun mel(hz:Double)=2595*log10(1+hz/700)
        val low=mel(100.0);val high=mel(7500.0)
        val edges=DoubleArray(BANDS+2){700*(10.0.pow((low+(high-low)*it/(BANDS+1))/2595)-1)}
        Array(BANDS){band->DoubleArray(SIZE/2+1){bin->
            val hz=bin*16000.0/SIZE
            max(0.0,min((hz-edges[band])/(edges[band+1]-edges[band]),
                (edges[band+2]-hz)/(edges[band+2]-edges[band+1])))
        }}
    }
    data class Result(val strength:DoubleArray,val novelty:DoubleArray,val candidates:IntArray)

    private fun fft(real:DoubleArray,imag:DoubleArray,inverse:Boolean=false) {
        for(i in real.indices) {val j=reverse[i];if(i<j) {
            var a=real[i];real[i]=real[j];real[j]=a
            a=imag[i];imag[i]=imag[j];imag[j]=a
        }}
        var length=2
        while(length<=SIZE) {
            val half=length/2;val stride=SIZE/length;var start=0
            while(start<SIZE) {
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
        if(inverse)for(i in real.indices){real[i]/=SIZE;imag[i]/=SIZE}
    }
    private fun peaks(x:DoubleArray):IntArray {
        val possible=mutableListOf<Int>();var i=1
        while(i<x.lastIndex) {
            if(x[i]>x[i-1]) {
                var end=i;while(end<x.lastIndex && x[end+1]==x[i])end++
                if(end<x.lastIndex && x[end]>x[end+1]) {
                    val k=(i+end)/2;val high=x[k]
                    if(high>=.04) {
                        var left=high;var right=high;var j=k-1
                        while(j>=0 && x[j]<=high){left=min(left,x[j]);j--}
                        j=k+1
                        while(j<x.size && x[j]<=high){right=min(right,x[j]);j++}
                        if(high-max(left,right)>=.025)possible+=k
                    }
                }
                i=end
            }
            i++
        }
        val accepted=mutableListOf<Int>()
        for(k in possible.sortedByDescending{x[it]})if(accepted.none{abs(it-k)<18})accepted+=k
        return accepted.sorted().toIntArray()
    }
    @JvmOverloads
    fun analyze(pcm:FloatArray,rms:DoubleArray?=null,cancelled:()->Boolean={false}):Result {
        val frames=pcm.size/HOP+1
        require(rms==null || rms.size==frames)
        val energy=rms?:DoubleArray(frames){frame->
            var power=0.0
            for(j in -HOP until HOP){val v=pcm.getOrElse(frame*HOP+j){0f}.toDouble();power+=v*v}
            sqrt(power/(HOP*2))
        }
        val envelope=Array(frames){DoubleArray(BANDS)}
        val real=DoubleArray(SIZE);val imag=DoubleArray(SIZE)
        for(frame in 0 until frames) {
            if(frame%16==0 && cancelled())throw InterruptedException("已取消识别")
            real.fill(0.0);imag.fill(0.0)
            for(j in 0 until WINDOW)real[j]=pcm.getOrElse(frame*HOP-WINDOW/2+j){0f}*hann[j]
            fft(real,imag)
            for(bin in 0..SIZE/2)real[bin]=ln(real[bin]*real[bin]+imag[bin]*imag[bin]+1e-12)
            for(bin in SIZE/2+1 until SIZE)real[bin]=real[SIZE-bin]
            imag.fill(0.0);fft(real,imag,true)
            // Remove pitch-period harmonics while retaining broad vocal formants.
            for(bin in 25 until SIZE-24)real[bin]=0.0
            imag.fill(0.0);fft(real,imag)
            for(bin in 0..SIZE/2)real[bin]=exp(real[bin])
            var total=0.0
            for(b in 0 until BANDS) {
                var value=0.0
                for(bin in 0..SIZE/2)value+=real[bin]*filters[b][bin]
                envelope[frame][b]=value;total+=value
            }
            for(b in 0 until BANDS)envelope[frame][b]/=total+1e-12
        }
        val prefix=Array(frames+1){DoubleArray(BANDS)}
        for(i in 0 until frames)for(b in 0 until BANDS)prefix[i+1][b]=prefix[i][b]+envelope[i][b]
        val floor=max(.0025,energy.max()*.035);val count=IntArray(frames+1)
        for(i in 0 until frames)count[i+1]=count[i]+if(energy[i]>floor)1 else 0
        val novelty=DoubleArray(frames)
        for(i in 0 until frames) {
            if(i%128==0 && cancelled())throw InterruptedException("已取消识别")
            val ls=max(0,i-18);val le=max(0,i-3)
            val rs=min(frames,i+4);val re=min(frames,i+19)
            if(le-ls<7 || re-rs<7 || count[min(frames,i+13)]-count[max(0,i-12)]<.45*25)continue
            val a=DoubleArray(BANDS){(prefix[le][it]-prefix[ls][it])/(le-ls)}
            val b=DoubleArray(BANDS){(prefix[re][it]-prefix[rs][it])/(re-rs)}
            val sa=a.sum()+1e-12;val sb=b.sum()+1e-12;var js=0.0
            for(band in 0 until BANDS) {
                val x=a[band]/sa;val y=b[band]/sb;val middle=(x+y)/2
                js+=.5*x*ln((x+1e-12)/(middle+1e-12))+.5*y*ln((y+1e-12)/(middle+1e-12))
            }
            novelty[i]=max(0.0,js)
        }
        val candidates=peaks(novelty);val strength=DoubleArray(frames)
        for(k in candidates) {
            val value=((novelty[k]-.025)/.10).coerceIn(0.0,.9)
            for(j in max(0,k-16)..min(frames-1,k+16))
                strength[j]=max(strength[j],value*exp(-.5*((j-k)/8.0).pow(2)))
        }
        return Result(strength,novelty,candidates)
    }
}
