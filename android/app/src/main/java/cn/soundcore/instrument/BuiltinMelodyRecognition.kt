package cn.soundcore.instrument

import kotlin.math.*

/** One acoustic evidence path and one event decoder. No lyric/song lookup or cloud fallback. */
internal object BuiltinMelodyRecognition {
    const val ALGORITHM="builtin-crepe-project-note-support-v1"
    const val VERSION=10
    fun recognize(pcm:FloatArray,observer:CrepePitchObserver,mode:MelodyInput,
        progress:(Int,String)->Unit={_,_->},cancelled:()->Boolean={false}):MelodyScore {
        require(pcm.size in 4000..2880000 && pcm.all{it.isFinite()})
        // Bound Viterbi history and native inference memory independently of song length.
        // Overlap is reconciled on the source clock; only the middle of each window is kept.
        if(pcm.size>480000){
            val notes=mutableListOf<MelodyNote>();val length=pcm.size/16
            for(a in 0 until length step 28000){
                if(cancelled())throw InterruptedException("已取消识别")
                val left=max(0,a-1000);val right=min(length,a+29000)
                val part=recognize(pcm.copyOfRange(left*16,min(pcm.size,right*16)),observer,mode,
                    {v,text->progress(((a.toLong()*100+v*min(28000,length-a))/length).toInt().coerceAtMost(99),text)},cancelled)
                val keepEnd=min(length,a+28000)
                part.notes.forEach { n ->
                    val start=max(a,left+n.startMs);val end=min(keepEnd,left+n.startMs+n.durationMs)
                    if(end-start>=20){
                        val prior=notes.lastOrNull()
                        if(prior!=null && start==a && prior.startMs+prior.durationMs==a && prior.midi==n.midi)
                            notes[notes.lastIndex]=prior.copy(durationMs=end-prior.startMs)
                        else notes+=n.copy(startMs=start,durationMs=end-start)
                    }
                }
            }
            progress(100,"整段旋律识别完成")
            return MelodyWorkspace.validated(MelodyScore(notes,length))
        }
        val analysis=RecognitionSignal.prepare(pcm,cancelled)
        progress(0,"在手机分析基频…")
        val raw=StablePitchTracker.track(analysis,{progress(it*30/100,"分析周期与停顿")},cancelled,exactWindow=mode==MelodyInput.VOCAL)
        val periodic=if(mode==MelodyInput.VOCAL)HarmonicRegisterRefinement.refine(analysis,raw,cancelled) else raw
        val neural=observer.observe(analysis,{progress(30+it*55/100,"内置模型校核音高与八度")},cancelled)
        val track=fuse(periodic,neural,cancelled)
        progress(88,"整理主音与句间停顿")
        val decoded=MelodyRecognition.decode(analysis,track,pcm.size/16,{progress(88+it*10/100,"整理主音与句间停顿")},cancelled,mode,refineHarmonics=false,minimumVocalDwell=6)
        val score=if(mode==MelodyInput.VOCAL)decoded.copy(notes=AcousticNoteConsensus.resolve(decoded.notes,track,neural,cancelled)) else decoded
        if(cancelled())throw InterruptedException("已取消识别")
        progress(100,"本地识别完成")
        return MelodyWorkspace.validated(score)
    }

    /** A learned observation may reject unsupported periodic noise, but cannot
     * overwrite a well-supported physical pitch. Short holes are recovered only
     * with strong neural evidence AND agreeing physical neighbours on both sides.
     * This keeps a real octave leap intact and does not fill phrase silence.
     */
    internal fun fuse(periodic:StablePitchTracker.Track,neural:Array<FloatArray>,cancelled:()->Boolean={false}):StablePitchTracker.Track {
        val frames=periodic.pitch.size
        require(neural.isNotEmpty() && neural.all{it.size==360 && it.all{v->v.isFinite() && v in 0f..1f}})
        val result=periodic.pitch.copyOf();val probability=periodic.probability.copyOf()
        val energyFloor=max(.0025,(periodic.rms.maxOrNull()?:0.0)*.035)
        for(f in 0 until frames){
            if(f%64==0 && cancelled())throw InterruptedException("已取消识别")
            val a=neural[min(neural.lastIndex,f/2)];val b=neural[min(neural.lastIndex,(f+1)/2)]
            fun activation(bin:Int)=if(f%2==0)a[bin].toDouble() else (a[bin]+b[bin])*.5
            val peak=(0 until 360).maxBy{activation(it)};val strength=activation(peak)
            var mass=0.0;var cents=0.0
            for(k in max(0,peak-4)..min(359,peak+4)){val w=activation(k);mass+=w;cents+=w*(1997.3794084376191+k*20)}
            val center=if(mass>1e-9)69+12*log2(10.0/440)+cents/mass/100 else Double.NaN
            if(periodic.rms[f]<=energyFloor || strength<.12 && probability[f]<.1){
                result[f]=Double.NaN;probability[f]=0.0;continue
            }
            if(!result[f].isFinite() && strength>=.85 && periodic.rms[f]>energyFloor*1.5 && center.isFinite()){
                val left=(f-1 downTo max(0,f-12)).firstOrNull{periodic.pitch[it].isFinite() && periodic.probability[it]>=.45}
                val right=(f+1 until min(frames,f+13)).firstOrNull{periodic.pitch[it].isFinite() && periodic.probability[it]>=.45}
                if(left!=null && right!=null && abs(periodic.pitch[left]-center)<.5 && abs(periodic.pitch[right]-center)<.5){
                    result[f]=center;probability[f]=strength
                }
            }
        }
        return StablePitchTracker.Track(result,probability,periodic.rms)
    }
}
