package cn.soundcore.instrument

import kotlin.math.*

/** Analysis-only DC/quiet-input conditioning. Original replay samples are untouched. */
internal object RecognitionSignal {
    fun prepare(pcm:FloatArray,cancelled:()->Boolean={false}):FloatArray {
        require(pcm.size in 4000..640000)
        var sum=0.0
        for(i in pcm.indices){
            if(i%4096==0 && cancelled())throw InterruptedException("已取消识别")
            require(pcm[i].isFinite());sum+=pcm[i]
        }
        val mean=sum/pcm.size;var peak=0.0
        for(i in pcm.indices)peak=max(peak,abs(pcm[i]-mean))
        require(peak>=1e-6){"录音里没有可识别的声音，请靠近麦克风再试"}
        // Byte-identical pass-through for ordinary recordings: this stage must
        // not retune a good clip or repeatedly normalize each syllable.
        if(abs(mean)<.005 && peak>=.05)return pcm
        val gain=min(32.0,max(1.0,.2/peak))
        return FloatArray(pcm.size){i->
            if(i%4096==0 && cancelled())throw InterruptedException("已取消识别")
            ((pcm[i]-mean)*gain).toFloat()
        }
    }
}
