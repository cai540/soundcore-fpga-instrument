package cn.soundcore.instrument

/** Preserve original source samples for replay; local recognition uses a 16k clock. */
data class NativeMelodyPcm(val samples:FloatArray,val rate:Int) {
    init {require(rate in listOf(16000,22050,24000,32000,44100,48000))}
    fun clip(range:MelodyRange):FloatArray=range.samples(samples,rate)
    fun local16k():FloatArray {
        if(rate==16000)return samples
        val out=FloatArray(((samples.size.toLong()*16000+rate-1)/rate).toInt());var used=0
        val sampler=PcmResampler(rate){out[used++]=it}
        samples.forEach(sampler::push);sampler.finish();check(used==out.size);return out
    }
}

/** Grow only as decoding needs it; a short import must not reserve three minutes. */
internal class NativePcmBuffer(private val rate:Int,expectedFrames:Int) {
    private val limit=rate*180
    private var data=FloatArray(expectedFrames.coerceIn(rate/4,limit))
    private var used=0
    fun push(sample:Float){require(sample.isFinite() && used<limit){"音频超过3分钟或含无效采样"}
        if(used==data.size)data=data.copyOf(minOf(limit,data.size*2))
        data[used++]=sample}
    fun finish()=NativeMelodyPcm(if(used==data.size)data else data.copyOf(used),rate)
}
