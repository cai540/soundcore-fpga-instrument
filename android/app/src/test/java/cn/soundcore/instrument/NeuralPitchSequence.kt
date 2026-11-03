package cn.soundcore.instrument

import kotlin.math.*

/** One sequence of joint learned/acoustic hypotheses, not per-frame argmax.
 * Neither score, lyric text, song identity nor an intended key is an input.
 * Kept separate for ablation before enabling in the production recognizer.
 */
internal object NeuralPitchSequence {
    private const val LOW=24
    private const val HIGH=96
    private const val STATES=HIGH-LOW+1
    private fun bin(midi:Double)=((midi-69-12*log2(10.0/440))*100-1997.3794084376191)/20
    fun decode(track:StablePitchTracker.Track,neural:Array<FloatArray>,
        neuralWeight:Double=.6,cancelled:()->Boolean={false}):StablePitchTracker.Track {
        require(neuralWeight in 0.0..1.0)
        require(neural.isNotEmpty() && neural.all{it.size==360})
        val n=track.pitch.size;val count=(n+1)/2
        val back=ByteArray(count*STATES)
        var previous=DoubleArray(STATES)
        val likelihood=DoubleArray(STATES)
        val centers=DoubleArray(STATES){LOW+it.toDouble()}
        val states=IntArray(count);val energy=max(.0025,(track.rms.maxOrNull()?:0.0)*.035)
        var wasSilent=true
        for(f in 0 until count){
            if(f%32==0 && cancelled())throw InterruptedException("已取消识别")
            val at=min(n-1,f*2);val p=track.pitch[at];val row=neural[min(neural.lastIndex,f)]
            val peak=(row.maxOrNull()?:0f).toDouble()
            val silent=track.rms[at]<=energy || peak<.12 && track.probability[at]<.1
            for(s in 0 until STATES){
                val center=bin(centers[s]).roundToInt();var learned=0.0
                for(k in max(0,center-2)..min(359,center+2))learned=max(learned,row[k].toDouble())
                val physical=if(p.isFinite())exp(-.5*((p-centers[s])/.45).pow(2)) else 0.0
                val weight=if(p.isFinite())neuralWeight else 1.0
                likelihood[s]=ln(max(1e-8,weight*learned/max(.01,peak)+(1-weight)*physical))
            }
            val next=DoubleArray(STATES)
            for(s in 0 until STATES){
                var best=Double.NEGATIVE_INFINITY;var from=s
                for(q in max(0,s-12)..min(STATES-1,s+12)){
                    val distance=abs(s-q)
                    val penalty=if(silent || wasSilent)0.0 else if(distance==0)0.0 else .65+.08*distance
                    val value=previous[q]-penalty
                    if(value>best){best=value;from=q}
                }
                next[s]=best+(if(silent)0.0 else likelihood[s]);back[f*STATES+s]=from.toByte()
            }
            val offset=next.max();for(s in next.indices)next[s]-=offset
            previous=next;wasSilent=silent
        }
        var state=previous.indices.maxBy{previous[it]}
        for(f in count-1 downTo 0){states[f]=state+LOW;state=back[f*STATES+state].toInt() and 255}
        val pitch=track.pitch.copyOf();val probability=track.probability.copyOf()
        for(i in pitch.indices){
            if(i%64==0 && cancelled())throw InterruptedException("已取消识别")
            val f=min(count-1,i/2);val row=neural[min(neural.lastIndex,f)];val peak=row.maxOrNull()?:0f
            if(track.rms[i]<=energy || peak<.12 && probability[i]<.1){pitch[i]=Double.NaN;probability[i]=0.0;continue}
            val selected=states[f].toDouble();val physical=pitch[i]
            if(physical.isFinite() && abs(physical-selected)<.7)continue
            val b=bin(selected).roundToInt();var sum=0.0;var weighted=0.0;var localPeak=0.0
            for(k in max(0,b-3)..min(359,b+3)){
                val w=row[k].toDouble();sum+=w;weighted+=w*(1997.3794084376191+k*20);localPeak=max(localPeak,w)
            }
            if(sum>1e-8 && localPeak>=.12){
                pitch[i]=69+12*log2(10.0/440)+weighted/sum/100;probability[i]=max(probability[i],localPeak)
            }
        }
        return StablePitchTracker.Track(pitch,probability,track.rms)
    }
}
