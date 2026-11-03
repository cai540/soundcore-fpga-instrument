package cn.soundcore.instrument

import kotlin.math.*

/** Perceptual main-note projection for expressive monophonic singing.
 * It is deliberately separate from measured F0. An ambiguous, unsteady note
 * can have a scooped attack or an unequal vibrato, so its mean need not be the
 * intended piano-key centre. Context is inferred from this recording only.
 * No score, lyric, filename, absolute song clock or melody template is read.
 * Stable cores, real rests and supported periodic repeated notes win over the
 * contour hypothesis. An intentional irregular detuned repeat can remain
 * ambiguous: this is a reversible listening model, not acoustic ground truth.
 */
internal object VocalContourProjection {
    data class Change(val startMs:Int,val before:Int,val after:Int,val reason:String)
    data class Result(val notes:List<MelodyNote>,val changes:List<Change>)
    private fun quantile(a:DoubleArray,f:Double):Double {
        val s=a.sortedArray();val x=(s.size-1)*f;val i=x.toInt()
        return s[i]+(s[min(i+1,s.lastIndex)]-s[i])*(x-i)
    }
    private fun center(a:DoubleArray):Double {
        val s=a.filter{it.isFinite()}.sorted();if(s.isEmpty())return Double.NaN
        val lo=(s.size*.1).toInt();val hi=max(lo+1,(s.size*.9).toInt())
        return s.subList(lo,hi).average()
    }
    /** A literal plateau is protected even if both sides contain glides. */
    private fun stable(p:DoubleArray,n:Int,frames:Int=14):Boolean {
        if(p.size<frames)return false
        for(a in 0..p.size-frames) {
            val q=p.copyOfRange(a,a+frames)
            if(q.all{it.isFinite() && abs(it-n)<.45} && q.max()-q.min()<.32)return true
        }
        return false
    }
    private fun peak(a:DoubleArray,k:Int):Double =
        (max(0,k-5)..min(a.lastIndex,k+5)).maxOfOrNull{a[it].takeIf{v->v.isFinite()}?:0.0}?:0.0
    private fun correlation(x:DoubleArray,y:DoubleArray):Double {
        if(x.size<2)return 0.0
        val xm=x.average();val ym=y.average();var xy=0.0;var xx=0.0;var yy=0.0
        for(i in x.indices){val a=x[i]-xm;val b=y[i]-ym;xy+=a*b;xx+=a*a;yy+=b*b}
        return if(xx*yy>1e-12)xy/sqrt(xx*yy) else 0.0
    }
    /** Two observed complete oscillations protect an expressive repeated note.
     * Original frame times are retained across missing samples. */
    private fun periodic(p:DoubleArray,n:Int):Boolean {
        val ids=p.indices.filter{p[it].isFinite()};if(ids.size<30)return false
        val mean=ids.map{p[it]}.average()
        if(abs(mean-n)>.45)return false
        val variance=ids.sumOf{(p[it]-mean).pow(2)}
        if(variance<ids.size*.015)return true
        for(step in 0..12) {
            val f=3+step*.5;if(f*(ids.last()-ids.first())*.01<2)continue
            val g=Array(3){DoubleArray(4)}
            for(i in ids){val t=i*.01;val x=doubleArrayOf(1.0,sin(2*PI*f*t),cos(2*PI*f*t))
                for(a in 0..2){for(b in 0..2)g[a][b]+=x[a]*x[b];g[a][3]+=x[a]*p[i]}}
            var ok=true
            for(c in 0..2){val k=(c..2).maxBy{abs(g[it][c])};val row=g[c];g[c]=g[k];g[k]=row
                val v=g[c][c];if(abs(v)<1e-9){ok=false;break};for(j in c..3)g[c][j]/=v
                for(a in 0..2)if(a!=c){val v2=g[a][c];for(j in c..3)g[a][j]-=v2*g[c][j]}}
            if(!ok)continue
            val error=ids.sumOf{i->(p[i]-g[0][3]-g[1][3]*sin(2*PI*f*i*.01)-g[2][3]*cos(2*PI*f*i*.01)).pow(2)}
            if(1-error/variance>.8 && abs(g[0][3]-n)<.45)return true
        }
        return false
    }
    fun apply(notes:List<MelodyNote>,track:StablePitchTracker.Track,onset:DoubleArray,
        novelty:DoubleArray,cancelled:()->Boolean={false}):List<MelodyNote> =
        analyze(notes,track,onset,novelty,cancelled).notes

    fun analyze(notes:List<MelodyNote>,track:StablePitchTracker.Track,onset:DoubleArray,
        novelty:DoubleArray,cancelled:()->Boolean={false}):Result {
        require(onset.size==track.pitch.size && novelty.size==track.pitch.size)
        if(cancelled())throw InterruptedException("已取消识别")
        val prior=TonalPitchRefinement.infer(notes)
        val result=notes.toMutableList();val changes=mutableListOf<Change>()
        fun raw(n:MelodyNote):DoubleArray = track.pitch.copyOfRange(
            (n.startMs/10).coerceIn(0,track.pitch.size),
            ((n.startMs+n.durationMs)/10).coerceIn(0,track.pitch.size))
        // First project individual pitches. Neighbours are the immutable input,
        // preventing a changed note from cascading down an otherwise valid run.
        for(i in notes.indices) {
            if(i%8==0 && cancelled())throw InterruptedException("已取消识别")
            val n=notes[i];val next=notes.getOrNull(i+1)?:continue
            val p=raw(n);val finite=p.filter{it.isFinite()}.toDoubleArray()
            if(finite.size<10 || finite.size<p.size*.8 || stable(p,n.midi))continue
            val c=center(p);val prev=notes.getOrNull(i-1)
            if(prior!=null && prev!=null && n.midi==prev.midi && n.midi-next.midi in 2..5 &&
                n.durationMs in 250..650 && n.startMs-prev.startMs-prev.durationMs in 0..50 &&
                next.startMs-n.startMs-n.durationMs in 0..100 && c>n.midi-1.5 && c<n.midi-.25 &&
                !periodic(p,n.midi)) {
                val start=n.startMs/10
                val articulation=peak(onset,start)>=.3 || peak(novelty,start)>=.04
                val nextCenter=center(raw(next))
                val candidate=(n.midi-1 downTo max(n.midi-2,next.midi+1)).firstOrNull {
                    prior.membership[Math.floorMod(it,12)]>=.5 }
                if(articulation && candidate!=null && abs(nextCenter-next.midi)<.4 &&
                    candidate>=quantile(finite,.1)-1.0 &&
                    abs((prev.midi-candidate)-(candidate-next.midi))<=1) {
                    result[i]=n.copy(midi=candidate)
                    changes+=Change(n.startMs,n.midi,candidate,"ambiguous_falling_rearticulation")
                    continue
                }
            }
            // A short articulated arch followed by a separately attacked, long
            // same-key anchor: use its supported upper turn, not the glide mean.
            if(prior!=null && n.durationMs in 250..500 && next.midi==n.midi && next.durationMs>=650 &&
                next.startMs-n.startMs-n.durationMs in 0..50 &&
                (i==0 || n.startMs-notes[i-1].let{it.startMs+it.durationMs}>=20) &&
                peak(onset,next.startMs/10)>=.4 && !periodic(p,n.midi)) {
                val high=quantile(finite,.95);val candidate=high.roundToInt()
                val top=p.indices.maxBy{p[it].takeIf{v->v.isFinite()}?:Double.NEGATIVE_INFINITY}
                val edge=max(1,p.size/5)
                val left=center(p.copyOfRange(0,edge));val right=center(p.copyOfRange(p.size-edge,p.size))
                var run=0;var longest=0
                for(k in p.indices){val absolute=n.startMs/10+k
                    run=if(p[k].isFinite() && abs(p[k]-candidate)<.55 &&
                        track.probability.getOrElse(absolute){0.0}>=.5)run+1 else 0
                    longest=max(longest,run)}
                if(candidate-n.midi in 1..2 && prior.membership[Math.floorMod(candidate,12)]>=.5 &&
                    top>=p.size/4 && top<=p.size*3/4 && high-left>=1.5 && high-right>=.8 &&
                    longest>=5 && abs(center(raw(next))-next.midi)<.35) {
                    result[i]=n.copy(midi=candidate)
                    changes+=Change(n.startMs,n.midi,candidate,"articulated_arch_upper_turn")
                }
            }
        }
        // A monotonic attack without a new syllable/onset must not become an
        // extra low key. Never fill a rest, cross a supported plateau or erase a
        // separately articulated legato note.
        val merged=mutableListOf<MelodyNote>();var i=0
        while(i<result.size) {
            if(i%8==0 && cancelled())throw InterruptedException("已取消识别")
            val n=result[i];val next=result.getOrNull(i+1)
            if(next!=null && n.durationMs in 150..350 && next.durationMs>=350 &&
                next.startMs==n.startMs+n.durationMs && next.midi-n.midi in 1..4) {
                val p=raw(n);val ids=p.indices.filter{p[it].isFinite()}
                if(ids.size>=p.size*.8 && ids.size>=10 && !stable(p,n.midi) &&
                    p[ids.last()]-p[ids.first()]>1.2 &&
                    correlation(ids.map{it.toDouble()}.toDoubleArray(),ids.map{p[it]}.toDoubleArray())>.9 &&
                    peak(novelty,next.startMs/10)<.04 && peak(onset,next.startMs/10)<.25) {
                    merged+=next.copy(startMs=n.startMs,durationMs=next.startMs+next.durationMs-n.startMs)
                    changes+=Change(n.startMs,n.midi,next.midi,"unarticulated_rising_attack")
                    i+=2;continue
                }
            }
            merged+=n;i++
        }
        return Result(merged,changes)
    }
}
