package cn.soundcore.instrument

import kotlin.math.*

/** Restore acoustically supported changes INSIDE conservative seed notes.
 * Seed boundaries and all existing short notes are immutable. No song names,
 * lyrics, reference scores, keys or fingerprints are inputs to this model.
 */
internal object VocalEventRestoration {
    data class Proposal(val seed:MelodyNote,val children:List<MelodyNote>,val childIndices:List<Int>,val centers:List<Double>)
    data class Result(val notes:List<MelodyNote>,val proposals:List<Proposal>)
    private data class Run(val start:Int,val end:Int,val value:Int)
    private data class Fit(val cost:Double,val midi:Int)
    private data class Stats(val mean:Double,val near:Double,val drift:Double,val rho:Double,
        val vibratoExplained:Double,val cycles:Double)
    private fun runs(a:IntArray):List<Run> {
        if(a.isEmpty())return emptyList()
        val out=mutableListOf<Run>();var s=0
        for(i in 1..a.size)if(i==a.size || a[i]!=a[s]){out+=Run(s,i,a[s]);s=i}
        return out
    }
    private fun median(a:DoubleArray):Double {a.sort();return if(a.size%2==1)a[a.size/2] else (a[a.size/2-1]+a[a.size/2])/2}
    private fun filtered(a:DoubleArray,radius:Int)=DoubleArray(a.size){i->median(DoubleArray(radius*2+1){j->a[(i+j-radius).coerceIn(a.indices)]})}
    private fun average(a:DoubleArray,start:Int,end:Int):Double {var s=0.0;for(i in start until end)s+=a[i];return s/(end-start)}
    private fun prepared(track:StablePitchTracker.Track):DoubleArray {
        val p=track.pitch.copyOf();val prob=track.probability;val rms=track.rms
        val floor=max(.0025,(rms.maxOrNull()?:0.0)*.035)
        val active=IntArray(p.size){if(p[it].isFinite() && rms[it]>floor)1 else 0}
        for(i in p.indices)if(active[i]==0)p[i]=Double.NaN
        val labels=IntArray(p.size){if(active[it]==1)Math.rint(p[it]).toInt() else -1}
        val smooth=IntArray(p.size){i->val q=IntArray(9){j->labels[(i+j-4).coerceIn(labels.indices)]};q.sort();if(active[i]==1)q[4] else -1}
        val original=p.copyOf()
        for(r in runs(smooth)) {
            if(r.value<0 || r.end-r.start>45 || average(prob,r.start,r.end)>=.45)continue
            val left=original.sliceArray(max(0,r.start-50) until r.start).filter{it.isFinite() && abs(it-r.value)>6}.toDoubleArray()
            val right=original.sliceArray(r.end until min(p.size,r.end+50)).filter{it.isFinite() && abs(it-r.value)>6}.toDoubleArray()
            if(left.size<8 || right.size<8)continue
            val a=median(left);val b=median(right)
            for(delta in intArrayOf(-12,12))if(abs(r.value+delta-a)<=3 && abs(r.value+delta-b)<=3 && abs(a-b)<=4) {
                for(i in r.start until r.end)if(p[i].isFinite())p[i]+=delta
                break
            }
        }
        for(r in runs(active))if(r.value==0 && r.start>0 && r.end<p.size && r.end-r.start<=16 &&
            active[r.start-1]==1 && active[r.end]==1 && (r.start until r.end).all{rms[it]>floor*1.5}) {
            val a=p[r.start-1];val b=p[r.end];val width=r.end-r.start+1
            for(i in r.start until r.end)p[i]=a+(b-a)*(i-r.start+1)/width
        }
        return p
    }
    /** Positive local maxima, height-ranked spacing, then prominence. */
    private fun peaks(v:DoubleArray,height:Double,prominence:Double,distance:Int):List<Int> {
        val candidates=mutableListOf<Int>();var i=1
        while(i<v.lastIndex) {
            if(v[i]>v[i-1]) {
                var end=i;while(end<v.lastIndex && v[end+1]==v[i])end++
                if(end<v.lastIndex && v[end]>v[end+1] && v[i]>=height)candidates+=(i+end)/2
                i=end
            };i++
        }
        val accepted=mutableListOf<Int>()
        for(k in candidates.sortedByDescending{v[it]})if(accepted.none{abs(k-it)<distance})accepted+=k
        return accepted.filter{k->
            var left=v[k];var right=v[k];var j=k-1
            while(j>=0 && v[j]<=v[k]){left=min(left,v[j]);j--}
            j=k+1;while(j<v.size && v[j]<=v[k]){right=min(right,v[j]);j++}
            v[k]-max(left,right)>=prominence
        }.sorted()
    }
    private data class Oscillation(val explained:Double,val frequency:Double,val projection:Double,val amplitudeSquared:Double)
    private fun oscillations(y:DoubleArray,mean:Double):List<Oscillation> {
        val finite=y.indices.filter{y[it].isFinite()};val count=finite.size
        if(count<2)return emptyList()
        var scatter=0.0;for(i in finite)scatter+=(y[i]-mean).pow(2)
        return (0..12).map { k ->
            val f=3+k*.5;var c=0.0;var s=0.0;var cc=0.0;var ss=0.0;var cs=0.0;var yc=0.0;var ys=0.0
            for(i in finite) {
                val co=cos(2*PI*f*i*.01);val si=sin(2*PI*f*i*.01);val z=y[i]-mean
                c+=co;s+=si;cc+=co*co;ss+=si*si;cs+=co*si;yc+=z*co;ys+=z*si
            }
            cc-=c*c/count;ss-=s*s/count;cs-=c*s/count
            val det=cc*ss-cs*cs
            if(det<=1e-12)Oscillation(0.0,f,0.0,Double.POSITIVE_INFINITY)
            else {
                val a=(yc*ss-ys*cs)/det;val b=(ys*cc-yc*cs)/det;val projection=max(0.0,a*yc+b*ys)
                Oscillation(projection/max(scatter,1e-12),f,projection,a*a+b*b)
            }
        }
    }
    private fun fit(y:DoubleArray,fixed:Int?=null):Fit {
        val finite=y.filter{it.isFinite()};val count=finite.size
        if(count<12)return Fit(Double.POSITIVE_INFINITY,0)
        val mean=finite.average();val n=fixed?:Math.rint(mean).toInt()
        val scatter=finite.sumOf{(it-mean).pow(2)};val quant=count*(mean-n).pow(2)
        var cost=scatter+quant
        if(count>=30)for(o in oscillations(y,mean))if(o.amplitudeSquared<=2.2.pow(2))
            cost=min(cost,scatter-o.projection+quant+2*ln(count.toDouble()))
        return Fit(cost,n)
    }
    private fun stats(y:DoubleArray,note:Int):Stats? {
        val indices=y.indices.filter{y[it].isFinite()};val count=indices.size
        if(count<8)return null
        var sx=0.0;var sy=0.0;var sxx=0.0;var syy=0.0;var sxy=0.0;var near=0
        for(i in indices) {
            val x=i*.01;val v=y[i];sx+=x;sy+=v;sxx+=x*x;syy+=v*v;sxy+=x*v
            if(abs(v-note)<.45)near++
        }
        val mean=sy/count;val xx=sxx-sx*sx/count;val yy=syy-sy*sy/count;val xy=sxy-sx*sy/count
        val drift=if(xx>1e-12)xy/xx else 0.0;val rho=if(xx*yy>1e-12)xy/sqrt(xx*yy) else 0.0
        val best=oscillations(y,mean).maxByOrNull{it.explained}
        val cycles=(best?.frequency?:0.0)*(indices.last()-indices.first()+1)*.01
        return Stats(mean,near.toDouble()/count,drift,rho,best?.explained?:0.0,cycles)
    }
    fun refine(notes:List<MelodyNote>,track:StablePitchTracker.Track,phonetic:DoubleArray,
        cancelled:()->Boolean={false}):List<MelodyNote> = analyze(notes,track,phonetic,cancelled).notes
    fun analyze(notes:List<MelodyNote>,track:StablePitchTracker.Track,phonetic:DoubleArray,
        cancelled:()->Boolean={false}):Result {
        if(notes.isEmpty())return Result(notes,emptyList())
        require(phonetic.size==track.pitch.size)
        val p=prepared(track);val out=mutableListOf<MelodyNote>();val proposals=mutableListOf<Proposal>();var checks=0
        fun checkCancelled(){if(cancelled())throw InterruptedException("已取消识别")}
        for(seed in notes) {
            checkCancelled()
            val start=(seed.startMs/10).coerceIn(0,p.size);val end=((seed.startMs+seed.durationMs)/10).coerceIn(start,p.size)
            val y=p.copyOfRange(start,end);val length=y.size
            if(length<40 || y.count{it.isFinite()}<length*.85 ||
                y.count{it.isFinite() && abs(it-seed.midi)<=6}<length*.9){out+=seed;continue}
            val v=phonetic.copyOfRange(start,end)
            val delta=DoubleArray(length){i->
                val a=y.sliceArray(max(0,i-15) until i).filter{it.isFinite()}
                val b=y.sliceArray(i until min(length,i+15)).filter{it.isFinite()}
                if(a.size>=8 && b.size>=8)abs(a.average()-b.average()) else 0.0
            }
            val initial=(peaks(v,.04,.02,12)+peaks(delta,1.1,.5,12)).filter{it>=15 && length-it>=15}
            var candidates=initial.flatMap{k->listOf(k-3,k,k+3)}.filter{it>=15 && length-it>=15}.distinct().sorted()
            if(candidates.size>24)candidates=candidates.sortedByDescending{max(v[it],delta[it]*.08)}.take(24).sorted()
            var best=fit(y,seed.midi).cost;var proposal:List<MelodyNote>?=null;var proposalCenters:List<Double> = emptyList()
            val fits=mutableMapOf<Pair<Int,Int>,Fit>();val centers=mutableMapOf<Pair<Int,Int>,Int>();val statistics=mutableMapOf<Triple<Int,Int,Int>,Stats?>()
            fun center(a:Int,b:Int)=centers.getOrPut(a to b){val finite=y.sliceArray(a until b).filter{it.isFinite()};if(finite.size<12)0 else Math.rint(finite.average()).toInt()}
            fun interval(a:Int,b:Int)=fits.getOrPut(a to b){fit(y.copyOfRange(a,b))}
            fun intervalStats(a:Int,b:Int,n:Int)=statistics.getOrPut(Triple(a,b,n)){stats(y.copyOfRange(a,b),n)}
            fun consider(cuts:List<Int>) {
                if(++checks%16==0)checkCancelled()
                val bounds=listOf(0)+cuts+listOf(length)
                if(bounds.zipWithNext().any{it.second-it.first<15})return
                val segments=bounds.zipWithNext();val pitches=segments.map{center(it.first,it.second)}
                if(seed.midi !in pitches || pitches.distinct().size==1 || pitches.zipWithNext().any{it.first==it.second} ||
                    pitches.any{abs(it-seed.midi)>4})return
                val ss=segments.indices.map{i->intervalStats(segments[i].first,segments[i].second,pitches[i])?:return}
                if(ss.zipWithNext().any{abs(it.first.mean-it.second.mean)<.55})return
                // A newly invented adjacent-semitone return needs an identifiable
                // middle centre, not merely a slow narrow bend of the seed.
                if(pitches.size==3 && pitches[0]==seed.midi && pitches[2]==seed.midi &&
                    abs(pitches[1]-seed.midi)==1 && abs(ss[1].mean-pitches[1])>.30 && ss[1].near<.65)return
                for(i in segments.indices) {
                    val (a,b)=segments[i];val n=pitches[i];val st=ss[i]
                    val count=b-a
                    var finite=0;var measured=0
                    for(k in start+a until start+b)if(track.pitch[k].isFinite()) {
                        finite++;if(track.probability[k]>.02)measured++
                    }
                    if(finite<count*.65 || measured<min(6.0,max(1.0,count*.3)))return
                    if(abs(st.drift)>3 && abs(st.rho)>.6)return
                    if(n==seed.midi)continue
                    if(count<40 && st.near<.65 && !(st.vibratoExplained>=.65 && st.cycles>=1.5 && abs(st.mean-n)<=.4))return
                }
                for(i in cuts.indices) {
                    val threshold=if(abs(pitches[i]-pitches[i+1])==1).06 else .04
                    if(v[cuts[i]]<threshold && !(ss[i].near>.85 && ss[i+1].near>.85))return
                }
                val penalty=cuts.sumOf{8*(1-.65*min(1.0,v[it]/.15))}
                val cost=segments.sumOf{interval(it.first,it.second).cost}+penalty
                if(cost+2<best) {
                    best=cost;proposalCenters=ss.map{it.mean}
                    proposal=segments.indices.map{i->
                        val (a,b)=segments[i];val begin=if(a==0)seed.startMs else (start+a)*10
                        val finish=if(b==length)seed.startMs+seed.durationMs else (start+b)*10
                        MelodyNote(begin,finish-begin,pitches[i],average(track.probability,start+a,start+b).toFloat())
                    }
                }
            }
            for(k in candidates)consider(listOf(k))
            for(i in candidates.indices)for(j in i+1 until candidates.size)consider(listOf(candidates[i],candidates[j]))
            if(proposal!=null) {
                val children=proposal!!;val indices=(out.size until out.size+children.size).toList()
                proposals+=Proposal(seed,children,indices,proposalCenters);out+=children
            } else out+=seed
        }
        checkCancelled();return Result(out,proposals)
    }
}
