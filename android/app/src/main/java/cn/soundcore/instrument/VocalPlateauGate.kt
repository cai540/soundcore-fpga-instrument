package cn.soundcore.instrument

import kotlin.math.*

/** Acoustic event validation, not a syllable/lyric lookup. Long genuine notes
 * are protected; a short state is not a note merely because it survived DWELL.
 * All rejection decisions use the original event list, preventing cascading
 * deletion from lengthening/protecting a second transitional event.
 */
internal object VocalPlateauGate {
    internal data class Evidence(val coreMs:Int,val nearFraction:Double,val span:Double)
    private fun quantile(values:DoubleArray,fraction:Double):Double {
        if(values.isEmpty())return 0.0
        values.sort();val x=fraction*(values.size-1);val i=x.toInt()
        return values[i]*(1-(x-i))+values[min(i+1,values.lastIndex)]*(x-i)
    }
    private fun trend(raw:DoubleArray):Pair<Double,Double> {
        var count=0;var sx=0.0;var sy=0.0;var sxx=0.0;var syy=0.0;var sxy=0.0
        raw.forEachIndexed {i,y->if(y.isFinite()) {
            val x=i.toDouble();count++;sx+=x;sy+=y;sxx+=x*x;syy+=y*y;sxy+=x*y
        }}
        val xx=sxx-sx*sx/max(1,count);val yy=syy-sy*sy/max(1,count)
        val xy=sxy-sx*sy/max(1,count)
        if(count<4 || xx<1e-9 || yy<1e-9)return 0.0 to 0.0
        return xy/xx*100 to xy/sqrt(xx*yy) // semi/s and correlation
    }
    internal fun evidence(raw:DoubleArray,note:Int):Evidence {
        if(raw.isEmpty())return Evidence(0,0.0,0.0)
        var p=raw.copyOf()
        fun close(shift:Int)=p.count{it.isFinite() && abs(it+shift-note)<.45}.toDouble()/p.size
        // Respect a prior short-register repair; do not mistake its raw octave
        // for zero support for an otherwise valid decoded note.
        for(shift in intArrayOf(-12,12))if(close(0)<.1 && close(shift)>.6) {
            for(i in p.indices)if(p[i].isFinite())p[i]+=shift
            break
        }
        val smooth=DoubleArray(p.size){i->
            val a=doubleArrayOf(p[max(0,i-1)],p[i],p[min(p.lastIndex,i+1)])
            if(a.any{!it.isFinite()})p[i] else {a.sort();a[1]}
        }
        val core=BooleanArray(p.size){i->smooth[i].isFinite() && abs(smooth[i]-note)<.45 &&
            abs(smooth[min(p.lastIndex,i+3)]-smooth[max(0,i-3)])<.32}
        for(i in 1 until core.lastIndex)if(!core[i] && core[i-1] && core[i+1])core[i]=true
        var longest=0;var run=0
        for(value in core) { run=if(value)run+1 else 0;longest=max(longest,run) }
        val finite=smooth.filter{it.isFinite()}.toDoubleArray()
        return Evidence(longest*10,smooth.count{it.isFinite() && abs(it-note)<.45}.toDouble()/smooth.size,
            quantile(finite.copyOf(),.9)-quantile(finite,.1))
    }

    fun apply(notes:List<MelodyNote>,track:StablePitchTracker.Track,cancelled:()->Boolean={false}):List<MelodyNote> {
        if(notes.size<2)return notes
        val pitch=track.pitch;val probability=track.probability;val rms=track.rms
        val floor=max(.0025,(rms.maxOrNull()?:0.0)*.035)
        fun checkCancelled(){if(cancelled())throw InterruptedException("已取消识别")}
        fun slice(n:MelodyNote)=pitch.copyOfRange((n.startMs/10).coerceIn(0,pitch.size),
            ((n.startMs+n.durationMs)/10).coerceIn(0,pitch.size))
        fun connected(a:MelodyNote,b:MelodyNote):Boolean {
            val start=((a.startMs+a.durationMs)/10).coerceIn(0,rms.size)
            val end=(b.startMs/10).coerceIn(0,rms.size)
            return end<=start || end-start<=20 && (start until end).all{rms[it]>floor*1.5}
        }
        val marked=BooleanArray(notes.size)
        val drifting=BooleanArray(notes.size)
        val drifts=DoubleArray(notes.size)
        for(i in notes.indices) {
            if(i%16==0)checkCancelled()
            val n=notes[i];val raw=slice(n);val e=evidence(raw,n.midi)
            if(e.coreMs>=min(120.0,n.durationMs*.7) || e.nearFraction>=.75 && e.coreMs>=100)continue
            val a=notes.getOrNull(i-1);val b=notes.getOrNull(i+1)
            if(a==null && b==null || a?.midi==n.midi || b?.midi==n.midi)continue
            val between=a!=null && b!=null && n.midi>min(a.midi,b.midi) && n.midi<max(a.midi,b.midi)
            val returning=a!=null && b!=null && a.midi==b.midi
            val drift=trend(raw).first
            drifting[i]=n.durationMs<=700 && e.span>=.5 && abs(drift)>=3
            drifts[i]=drift
            // Longer A-B-A ornaments need stronger evidence than a short glide.
            // Do not automatically flatten a longer A-B-C intermediate: a true
            // broad-vibrato note can have the same frame-level shape.
            val maximum=if(returning && e.nearFraction<.35 && e.span>1.8)900 else 240
            if(n.durationMs>maximum || e.span<(if(between).5 else .9))continue
            if(slice(n).count{it.isFinite()}<4)continue
            marked[i]=true
        }
        // A continuous glide can slow near several semitones and exceed the
        // short-event threshold. Require a whole ordered contour and drift in
        // EVERY intermediate event, not simply a descending note sequence.
        var cursor=0
        while(cursor<notes.size) {
            if(!drifting[cursor]) {cursor++;continue}
            val first=cursor;var last=cursor
            while(last+1<notes.size && drifting[last+1] && connected(notes[last],notes[last+1]))last++
            cursor=last+1
            if(last-first+1<2 || first==0 || last==notes.lastIndex)continue
            val a=notes[first-1];val b=notes[last+1];val direction=(b.midi-a.midi).sign
            if(abs(b.midi-a.midi)<5 || notes[last].startMs+notes[last].durationMs-notes[first].startMs>1200 ||
                !connected(a,notes[first]) || !connected(notes[last],b))continue
            var previous=a.midi;var ordered=true
            for(i in first..last) {
                if((notes[i].midi-previous)*direction<=0 || drifts[i]*direction<3)ordered=false
                previous=notes[i].midi
            }
            if((b.midi-previous)*direction<=0 || !ordered)continue
            val s=(notes[first].startMs/10).coerceIn(0,pitch.size)
            val e=((notes[last].startMs+notes[last].durationMs)/10).coerceIn(s,pitch.size)
            val contour=pitch.copyOfRange(s,e);val correlation=trend(contour).second
            var same=0.0;var movement=0.0;var previousPitch=Double.NaN
            for(value in contour)if(value.isFinite()) {
                if(previousPitch.isFinite()) {val d=(value-previousPitch)*direction;same+=max(0.0,d);movement+=abs(d)}
                previousPitch=value
            }
            if(correlation*direction>=.85 && movement>0 && same/movement>=.8)
                for(i in first..last)marked[i]=true
        }
        val groups=mutableListOf<MutableList<Int>>()
        for(i in notes.indices)if(marked[i]) {
            if(groups.isNotEmpty() && i==groups.last().last()+1 && connected(notes[i-1],notes[i]))groups.last()+=i
            else groups+=mutableListOf(i)
        }
        val starts=IntArray(notes.size){notes[it].startMs}
        val ends=IntArray(notes.size){notes[it].startMs+notes[it].durationMs}
        val removed=BooleanArray(notes.size)
        val parent=IntArray(notes.size){it}
        fun representative(index:Int):Int {
            var r=index
            while(parent[r]!=r)r=parent[r]
            var k=index
            while(parent[k]!=k) {val next=parent[k];parent[k]=r;k=next}
            return r
        }
        for(group in groups) {
            checkCancelled()
            val first=group.first();val last=group.last();val a=notes.getOrNull(first-1);val b=notes.getOrNull(last+1)
            val left=a!=null && connected(a,notes[first]);val right=b!=null && connected(notes[last],b)
            if(!left && !right)continue
            val start=notes[first].startMs;val end=notes[last].startMs+notes[last].durationMs
            if(left && right && a!!.midi==b!!.midi) {
                ends[first-1]=max(ends[first-1],b.startMs+b.durationMs)
                parent[representative(last+1)]=representative(first-1)
            } else if(left && right) {
                val s=(start/10).coerceIn(0,pitch.size);val e=(end/10).coerceIn(0,pitch.size)
                var totalRight=0.0
                for(k in s until e)if(pitch[k].isFinite())totalRight+=min(abs(pitch[k]-b!!.midi),4.0)
                var cost=totalRight;var best=cost;var cut=s
                for(k in s until e) {
                    if(pitch[k].isFinite())cost+=min(abs(pitch[k]-a!!.midi),4.0)-min(abs(pitch[k]-b!!.midi),4.0)
                    if(cost<best) {best=cost;cut=k+1}
                }
                val handover=(cut*10).coerceIn(start,end)
                ends[first-1]=max(ends[first-1],handover);starts[last+1]=min(starts[last+1],handover)
            } else if(right)starts[last+1]=min(starts[last+1],start)
            else ends[first-1]=max(ends[first-1],end)
            for(i in group)removed[i]=true
        }
        checkCancelled()
        for(i in notes.indices)if(!removed[i]) {
            val r=representative(i)
            starts[r]=min(starts[r],starts[i]);ends[r]=max(ends[r],ends[i])
        }
        return notes.mapIndexedNotNull { i,n ->
            if(removed[i] || representative(i)!=i)null else {
                val s=(starts[i]/10).coerceIn(0,probability.size);val e=(ends[i]/10).coerceIn(s,probability.size)
                var p=0.0;for(k in s until e)p+=probability[k]
                n.copy(startMs=starts[i],durationMs=ends[i]-starts[i],confidence=if(e>s)(p/(e-s)).toFloat() else n.confidence)
            }
        }
    }
}
