package cn.soundcore.instrument

import kotlin.math.*

/** Weak, recording-inferred tonal evidence for an ambiguous pitch only.
 * No song, target key, lyrics, reference score or file identity is an input.
 * Stable chromatic notes, small pitch-class inventories and short contexts
 * remain unchanged; time boundaries and event count are never changed here.
 * Profile values: Krumhansl-Schmuckler/Kessler, verified against music21's
 * official analysis.discrete.getWeights implementation:
 * https://music21.org/music21docs/_modules/music21/analysis/discrete.html
 */
internal object TonalPitchRefinement {
    private val major=doubleArrayOf(6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88)
    private val minor=doubleArrayOf(6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17)
    private val degrees=intArrayOf(0,2,4,5,7,9,11)
    internal data class Prior(val membership:DoubleArray,val strongestCorrelation:Double)
    private fun correlation(a:DoubleArray,b:DoubleArray):Double {
        val am=a.average();val bm=b.average();var xy=0.0;var xx=0.0;var yy=0.0
        for(i in a.indices){val x=a[i]-am;val y=b[i]-bm;xy+=x*y;xx+=x*x;yy+=y*y}
        return if(xx*yy>1e-12)xy/sqrt(xx*yy) else 0.0
    }
    internal fun infer(notes:List<MelodyNote>):Prior? {
        if(notes.sumOf{it.durationMs}<5000)return null
        val histogram=DoubleArray(12)
        for(n in notes)histogram[Math.floorMod(n.midi,12)]+=n.durationMs*max(.1,n.confidence.toDouble())
        val peak=histogram.maxOrNull()?:return null
        if(peak<=0 || histogram.count{it>peak*.025}<5)return null
        val scores=DoubleArray(12){tonic->
            max(correlation(histogram,DoubleArray(12){pc->major[Math.floorMod(pc-tonic,12)]}),
                correlation(histogram,DoubleArray(12){pc->minor[Math.floorMod(pc-tonic-9,12)]}))
        }
        val best=scores.max();if(best<.65)return null
        val posterior=DoubleArray(12){exp((scores[it]-best)*8)};val total=posterior.sum()
        val membership=DoubleArray(12)
        for(tonic in 0..11)for(degree in degrees)membership[(tonic+degree)%12]+=posterior[tonic]/total
        for(i in membership.indices)membership[i]=max(.05,membership[i])
        return Prior(membership,best)
    }
    private fun quantile(sorted:DoubleArray,fraction:Double):Double {
        val x=(sorted.size-1)*fraction;val i=x.toInt()
        return sorted[i]*(1-(x-i))+sorted[min(i+1,sorted.lastIndex)]*(x-i)
    }
    internal fun core(p:DoubleArray,note:Int):Pair<Int,Double> {
        if(p.isEmpty())return 0 to 0.0
        val q=DoubleArray(p.size){i->
            val a=doubleArrayOf(p[max(0,i-1)],p[i],p[min(p.lastIndex,i+1)])
            if(a.any{!it.isFinite()})p[i] else {a.sort();a[1]}
        }
        var run=0;var longest=0;var near=0
        for(i in q.indices) {
            val close=q[i].isFinite() && abs(q[i]-note)<.45
            if(close)near++
            val flat=abs(q[min(q.lastIndex,i+3)]-q[max(0,i-3)])<.32
            run=if(close && flat)run+1 else 0;longest=max(longest,run)
        }
        return longest*10 to near.toDouble()/q.size
    }
    /** A clearly periodic vibrato around its existing note is expression,
     * including a slightly detuned chromatic note, not evidence of a wrong key.
     */
    private fun periodic(p:DoubleArray,note:Int):Boolean {
        val indices=p.indices.filter{p[it].isFinite()}
        if(indices.size<48)return false
        val span=indices.last()-indices.first()+1
        if(span<60)return false
        val midpoint=(indices.first()+indices.last())*.005
        val count=indices.size;var st=0.0;var sy=0.0;var stt=0.0;var sty=0.0
        for(i in indices){val t=i*.01-midpoint;st+=t;sy+=p[i];stt+=t*t;sty+=t*p[i]}
        val slope=(sty-st*sy/count)/(stt-st*st/count);val intercept=(sy-slope*st)/count
        val variance=indices.sumOf{i->(p[i]-intercept-slope*(i*.01-midpoint)).pow(2)}
        if(variance<count*.04)return false
        for(frequency in 0..14) {
            val f=2+frequency*.5;if(f*span*.01<1.8)continue
            // Solve DC + linear trend + sine/cosine jointly, with ORIGINAL
            // sample times. Dropping NaNs must not compress the time axis or
            // turn a missing vibrato phase into a different apparent pitch.
            val gram=Array(4){DoubleArray(5)}
            for(i in indices) {
                val t=i*.01-midpoint
                val x=doubleArrayOf(1.0,t,cos(2*PI*f*t),sin(2*PI*f*t))
                for(a in 0..3){for(b in 0..3)gram[a][b]+=x[a]*x[b];gram[a][4]+=x[a]*p[i]}
            }
            var valid=true
            for(column in 0..3) {
                val pivot=(column..3).maxBy{abs(gram[it][column])}
                if(abs(gram[pivot][column])<1e-9){valid=false;break}
                val row=gram[column];gram[column]=gram[pivot];gram[pivot]=row
                val scale=gram[column][column];for(j in column..4)gram[column][j]/=scale
                for(other in 0..3)if(other!=column) {
                    val factor=gram[other][column]
                    for(j in column..4)gram[other][j]-=factor*gram[column][j]
                }
            }
            if(!valid)continue
            val model=DoubleArray(4){gram[it][4]}
            var error=0.0
            for(i in indices) {
                val t=i*.01-midpoint
                val d=p[i]-model[0]-model[1]*t-model[2]*cos(2*PI*f*t)-model[3]*sin(2*PI*f*t)
                error+=d*d
            }
            if(1-error/variance>=.75 && abs(model[0]-note)<.45)return true
        }
        return false
    }
    fun apply(notes:List<MelodyNote>,track:StablePitchTracker.Track,cancelled:()->Boolean={false}):List<MelodyNote> =
        apply(notes,track,null,cancelled)

    /** Independent note-model/phonetic evidence can lock a recovered child.
     * The mask refers to this event list; it must not come from song identity.
     * Preserve the existing three-argument entry for callers and JVM harnesses.
     */
    fun apply(notes:List<MelodyNote>,track:StablePitchTracker.Track,protectedNotes:BooleanArray?,
        cancelled:()->Boolean):List<MelodyNote> {
        require(protectedNotes==null || protectedNotes.size==notes.size)
        if(cancelled())throw InterruptedException("已取消识别")
        val prior=infer(notes)?:return notes
        return notes.mapIndexed { index,n ->
            if(index%8==0 && cancelled())throw InterruptedException("已取消识别")
            if(protectedNotes?.get(index)==true)return@mapIndexed n
            if(prior.membership[Math.floorMod(n.midi,12)]>=.25)return@mapIndexed n
            val start=(n.startMs/10).coerceIn(0,track.pitch.size)
            val end=((n.startMs+n.durationMs)/10).coerceIn(start,track.pitch.size)
            val raw=track.pitch.copyOfRange(start,end)
            if(end>track.rms.size || (start until end).any{!track.rms[it].isFinite() || track.rms[it]<=1e-8})return@mapIndexed n
            val observed=DoubleArray(raw.size){i->if(raw[i].isFinite() && abs(raw[i]-n.midi)<4)raw[i] else Double.NaN}
            val finite=observed.filter{it.isFinite()}.toDoubleArray()
            if(finite.size<10 || finite.size<ceil(raw.size*.8).toInt())return@mapIndexed n
            val (duration,support)=core(observed,n.midi)
            if(duration>=140 || support>=.7)return@mapIndexed n
            val sorted=finite.sortedArray();val low=(sorted.size*.1).toInt()
            val high=max((sorted.size*.9).toInt(),low+1)
            var sum=0.0;for(i in low until high)sum+=sorted[i]
            val center=sum/(high-low);val offset=abs(center-n.midi)
            if(offset<.25 || offset>.85)return@mapIndexed n
            val span=quantile(sorted,.9)-quantile(sorted,.1)
            if(span<.55 || periodic(observed,n.midi))return@mapIndexed n
            val uncertainty=min(1.0,span/1.2)
            var chosen=n.midi;var best=Double.POSITIVE_INFINITY
            for(candidate in n.midi-1..n.midi+1) {
                val cost=(candidate-center).pow(2)-.6*uncertainty*ln(prior.membership[Math.floorMod(candidate,12)])
                if(cost<best){best=cost;chosen=candidate}
            }
            n.copy(midi=chosen)
        }
    }
}
