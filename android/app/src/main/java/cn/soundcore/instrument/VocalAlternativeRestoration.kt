package cn.soundcore.instrument

import kotlin.math.*

/** Recover changes hidden by derivative-weighted decoding without moving or
 * merging an accepted event. The secondary decoder has the same dwell, onset,
 * vibrato and gate model; only derivative weighting is disabled. A hypothesis
 * is still rejected unless original measured F0 and a phonetic cut support it.
 * No score, lyric, song identity, file name or reference time is an input.
 */
internal object VocalAlternativeRestoration {
    data class Proposal(val parent:MelodyNote,val children:List<MelodyNote>)
    data class Result(val notes:List<MelodyNote>,val proposals:List<Proposal>)
    private data class Core(val duration:Int,val fraction:Double)
    private fun core(raw:DoubleArray,note:Int):Core {
        if(raw.isEmpty())return Core(0,0.0)
        val smooth=raw.copyOf()
        for(i in 1 until raw.lastIndex)if(raw[i-1].isFinite() && raw[i].isFinite() && raw[i+1].isFinite()) {
            val a=doubleArrayOf(raw[i-1],raw[i],raw[i+1]);a.sort();smooth[i]=a[1]
        }
        var near=0;var longest=0;var run=0
        for(i in smooth.indices) {
            val close=smooth[i].isFinite() && abs(smooth[i]-note)<.45
            if(close)near++
            val a=smooth[max(0,i-3)];val b=smooth[min(smooth.lastIndex,i+3)]
            run=if(close && a.isFinite() && b.isFinite() && abs(a-b)<.32)run+1 else 0
            longest=max(longest,run)
        }
        return Core(longest*10,near.toDouble()/raw.size)
    }
    private fun peaks(values:DoubleArray):List<Int> {
        val candidates=mutableListOf<Int>();var i=1
        while(i<values.lastIndex) {
            if(values[i]>values[i-1]) {
                var end=i;while(end<values.lastIndex && values[end+1]==values[i])end++
                if(end<values.lastIndex && values[end]>values[end+1])candidates+=(i+end)/2
                i=end
            };i++
        }
        val accepted=mutableListOf<Int>()
        for(k in candidates.sortedByDescending{values[it]})if(accepted.none{abs(k-it)<4})accepted+=k
        return accepted.filter { k ->
            var left=values[k];var right=values[k];var j=k-1
            while(j>=0 && values[j]<=values[k]){left=min(left,values[j]);j--}
            j=k+1;while(j<values.size && values[j]<=values[k]){right=min(right,values[j]);j++}
            values[k]-max(left,right)>=.35
        }.sorted()
    }
    /** Directly observed peak-trough-peak or inverse. NaN runs retain their
     * original time axis; neither interpolated turns nor f*duration qualifies.
     */
    internal fun observedCycle(raw:DoubleArray):Boolean {
        val turns=mutableListOf<Pair<Int,Int>>();var start=0
        while(start<raw.size) {
            if(!raw[start].isFinite()){start++;continue}
            var end=start;while(end<raw.size && raw[end].isFinite())end++
            if(end-start>=8) {
                val q=raw.copyOfRange(start,end)
                for(i in peaks(q))if(i>=2 && q.size-i>=3)turns+=start+i to 1
                for(i in peaks(DoubleArray(q.size){-q[it]}))if(i>=2 && q.size-i>=3)turns+=start+i to -1
            }
            start=end+1
        }
        turns.sortBy{it.first}
        for(i in 0 until turns.size-2) {
            val a=turns[i];val b=turns[i+1];val c=turns[i+2]
            if(a.second==c.second && a.second!=b.second && b.first-a.first>=4 && c.first-b.first>=4 &&
                (a.first..c.first).all{raw[it].isFinite()})return true
        }
        return false
    }
    private fun trend(raw:DoubleArray):Pair<Double,Double> {
        var count=0;var sx=0.0;var sy=0.0;var xx=0.0;var yy=0.0;var xy=0.0
        for(i in raw.indices)if(raw[i].isFinite()) {
            val x=i*.01;val y=raw[i];count++;sx+=x;sy+=y;xx+=x*x;yy+=y*y;xy+=x*y
        }
        if(count<4)return 0.0 to 0.0
        xx-=sx*sx/count;yy-=sy*sy/count;xy-=sx*sy/count
        return if(xx<=1e-12 || yy<=1e-12)0.0 to 0.0 else xy/xx to xy/sqrt(xx*yy)
    }
    private fun loss(pitch:DoubleArray,probability:DoubleArray,start:Int,end:Int,note:Int):Double {
        var total=0.0
        for(i in start until end)if(pitch[i].isFinite()) {
            val d=abs(pitch[i]-note)
            total+=min(4.0,if(d<=.75)d*d else 1.5*d-.5625)*(.6+.4*probability[i])
        }
        return total
    }
    fun apply(trusted:List<MelodyNote>,alternative:List<MelodyNote>,track:StablePitchTracker.Track,
        phonetic:DoubleArray,cancelled:()->Boolean={false}):List<MelodyNote> = analyze(trusted,alternative,track,phonetic,cancelled).notes

    fun analyze(trusted:List<MelodyNote>,alternative:List<MelodyNote>,track:StablePitchTracker.Track,
        phonetic:DoubleArray,cancelled:()->Boolean={false}):Result {
        fun checkCancelled(){if(cancelled())throw InterruptedException("已取消识别")}
        checkCancelled()
        require(phonetic.size==track.pitch.size && track.probability.size==track.pitch.size)
        val out=mutableListOf<MelodyNote>();val proposals=mutableListOf<Proposal>()
        for(parent in trusted) {
            checkCancelled()
            val start=parent.startMs;val end=start+parent.durationMs;val old=parent.midi
            if(parent.durationMs<650){out+=parent;continue}
            val children=mutableListOf<MelodyNote>()
            for(n in alternative) {
                val a=max(start,n.startMs);val b=min(end,n.startMs+n.durationMs)
                if(b-a<150)continue
                val previous=children.lastOrNull()
                if(previous!=null && previous.midi==n.midi && previous.startMs+previous.durationMs==a)
                    children[children.lastIndex]=previous.copy(durationMs=previous.durationMs+b-a)
                else children+=n.copy(startMs=a,durationMs=b-a)
            }
            if(children.size !in 2..3 || children.none{it.midi==old} || children.any{abs(it.midi-old)>3} ||
                children.sumOf{it.durationMs}<parent.durationMs*.95 ||
                children.zipWithNext().any{it.first.startMs+it.first.durationMs!=it.second.startMs}) {out+=parent;continue}
            val first=children.first();children[0]=first.copy(startMs=start,durationMs=first.durationMs+first.startMs-start)
            val last=children.last();children[children.lastIndex]=last.copy(durationMs=end-last.startMs)
            if(children.any{it.durationMs<200}){out+=parent;continue}
            var valid=true;var newCost=0.0
            for(i in children.indices) {
                val child=children[i];val a=(child.startMs/10).coerceIn(0,track.pitch.size)
                val b=((child.startMs+child.durationMs)/10).coerceIn(a,track.pitch.size)
                val raw=track.pitch.copyOfRange(a,b);val count=b-a
                if(count==0){valid=false;break}
                var finite=0;var measured=0;var probability=0.0
                for(k in a until b) {
                    probability+=track.probability[k]
                    if(track.pitch[k].isFinite()){finite++;if(track.probability[k]>.02)measured++}
                }
                if(finite<count*.65 || measured<min(6.0,max(1.0,count*.3)))valid=false
                val core=core(raw,child.midi);val cycle=observedCycle(raw);val (drift,rho)=trend(raw)
                if(abs(drift)>3 && abs(rho)>.6 && !cycle)valid=false
                var best=child.midi-1;var cost=Double.POSITIVE_INFINITY
                for(n in child.midi-1..child.midi+1) {
                    val candidate=loss(track.pitch,track.probability,a,b,n)
                    if(candidate<cost){cost=candidate;best=n}
                }
                if(best!=child.midi)valid=false
                if(child.midi!=old && core.duration<max(120.0,count*6.0) && !cycle)valid=false
                children[i]=child.copy(confidence=(probability/count).toFloat())
                newCost+=loss(track.pitch,track.probability,a,b,child.midi)
            }
            val cuts=children.drop(1).map{it.startMs/10}
            if(cuts.any{it !in phonetic.indices || !phonetic[it].isFinite() || !(phonetic[it]>=.04)})valid=false
            val a=(start/10).coerceIn(0,track.pitch.size);val b=(end/10).coerceIn(a,track.pitch.size)
            val oldCost=loss(track.pitch,track.probability,a,b,old)
            val penalty=cuts.sumOf{if(it in phonetic.indices)6*(1-.65*min(1.0,phonetic[it]/.15)) else 6.0}
            if(oldCost-newCost<=penalty)valid=false
            if(valid){out+=children;proposals+=Proposal(parent,children.toList())}else out+=parent
        }
        checkCancelled();return Result(out,proposals)
    }
}
