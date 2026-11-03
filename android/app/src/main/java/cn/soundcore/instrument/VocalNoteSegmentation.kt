package cn.soundcore.instrument

import kotlin.math.*

enum class MelodyInput { VOCAL, INSTRUMENT }

/** Stable note events, with explicit rests and fresh attacks on repeated notes. */
internal object VocalNoteSegmentation {
    private data class Run(val start:Int,val end:Int,val note:Int)
    private fun runs(a:IntArray):List<Run> {
        val out=mutableListOf<Run>();var s=0
        for(i in 1..a.size)if(i==a.size || a[i]!=a[s]){out+=Run(s,i,a[s]);s=i}
        return out
    }
    private fun median(values:DoubleArray):Double { values.sort();return values[values.size/2] }
    private fun medianFilter(a:DoubleArray,radius:Int)=DoubleArray(a.size) { i ->
        median(DoubleArray(radius*2+1){j->a[(i+j-radius).coerceIn(a.indices)]}) }

    fun segment(track:StablePitchTracker.Track,duration:Int,mode:MelodyInput,cancelled:()->Boolean={false},
        onsetEvidence:DoubleArray?=null,minimumVocalDwell:Int=15):MelodyScore {
        if(mode==MelodyInput.VOCAL)return VocalMainNoteSegmentation.segment(track,duration,cancelled,onsetEvidence,minimumVocalDwell)
        val pitch=track.pitch;val rms=track.rms;val prob=track.probability
        val floor=max(.0025,(rms.maxOrNull()?:0.0)*.035)
        val labels=IntArray(pitch.size){i->if(pitch[i].isFinite() && rms[i]>floor)pitch[i].roundToInt() else -1}
        for(r in runs(labels))if(r.note<0 && r.start>0 && r.end<labels.size) {
            val left=labels[r.start-1];val right=labels[r.end]
            if(left>=0 && left==right && r.end-r.start<=if(mode==MelodyInput.VOCAL)12 else 2)
                for(i in r.start until r.end)labels[i]=left
            else if(left>=0 && right>=0 && r.end-r.start<=8 &&
                (r.start until r.end).all{rms[it]>floor*1.5})
                for(i in r.start until r.end)labels[i]=if(i<(r.start+r.end)/2)left else right
        }
        val smoothed=IntArray(labels.size) { i ->
            val values=IntArray(7){j->labels[(i+j-3).coerceIn(labels.indices)]};values.sort()
            if(labels[i]<0)-1 else values[3]
        }
        smoothed.copyInto(labels)
        val minimum=if(mode==MelodyInput.VOCAL)9 else 6
        for(r in runs(labels))if(r.note>=0 && r.end-r.start<minimum) {
            val left=labels.getOrElse(r.start-1){-1};val right=labels.getOrElse(r.end){-1}
            val replacement=when {
                left>=0 && left==right->left
                left>=0 && abs(left-r.note)<=2->left
                right>=0 && abs(right-r.note)<=2->right
                else->-1
            }
            for(i in r.start until r.end)labels[i]=replacement
        }
        var notes=runs(labels).filter{it.note>=0 && it.end-it.start>=minimum}.map { r ->
            MelodyNote(r.start*10,min(r.end*10,duration)-r.start*10,r.note,
                prob.sliceArray(r.start until r.end).average().toFloat())
        }.filter{it.durationMs>=minimum*10}.toMutableList()
        if(mode==MelodyInput.VOCAL) {
            val original=notes.toList()
            notes=notes.mapIndexed { i,n ->
                if(n.durationMs>360)return@mapIndexed n
                val a=original.getOrNull(i-1);val b=original.getOrNull(i+1)
                val values=pitch.sliceArray(n.startMs/10 until (n.startMs+n.durationMs)/10).filter{it.isFinite()}.toDoubleArray()
                if(values.isEmpty())return@mapIndexed n
                val center=median(values)
                val replacement=when {
                    a!=null && b!=null && a.midi==b.midi && abs(a.midi-n.midi)==1 && abs(center-a.midi)<.8->a.midi
                    a!=null && n.durationMs<=300 && a.durationMs>=400 && abs(a.midi-n.midi)==1 &&
                        n.startMs-a.startMs-a.durationMs<=20 && abs(center-a.midi)<.8->a.midi
                    n.durationMs<140->listOfNotNull(a,b).filter{abs(it.midi-n.midi)<=1 &&
                        (it.durationMs>=600 || i==0 && it.durationMs>=300)}.minByOrNull{abs(it.midi-center)}?.midi
                    else->null
                }
                n.copy(midi=replacement?:n.midi)
            }.toMutableList()
        }
        val merged=mutableListOf<MelodyNote>()
        for(n in notes) {
            val prev=merged.lastOrNull()
            if(prev!=null && n.midi==prev.midi && n.startMs-prev.startMs-prev.durationMs<=20)
                merged[merged.lastIndex]=prev.copy(durationMs=n.startMs+n.durationMs-prev.startMs)
            else merged+=n
        }
        if(mode==MelodyInput.VOCAL && merged.size>1) {
            val a=merged[0];val b=merged[1]
            if(a.durationMs<140 && a.midi==b.midi && b.startMs-a.startMs-a.durationMs<250) {
                merged[1]=b.copy(startMs=a.startMs,durationMs=b.startMs+b.durationMs-a.startMs);merged.removeAt(0)
            }
        }
        val energy=medianFilter(rms,2)
        val valleys=valleys(energy)
        val output=mutableListOf<MelodyNote>()
        for(n in merged) {
            val s=n.startMs/10;val e=(n.startMs+n.durationMs)/10
            val cuts=mutableListOf(s)
            val spacing=if(mode==MelodyInput.VOCAL)18 else 8
            if(e-s>=if(mode==MelodyInput.VOCAL)65 else 25)for(k in valleys) {
                if(k<=s+spacing || k>=e-spacing || k-cuts.last()<spacing)continue
                val low=energy[k]
                val before=(max(s,k-12) until k).maxOf{energy[it]}
                val after=(k+1 until min(e,k+13)).maxOf{energy[it]}
                if(before>low*1.75 && after>low*1.75)cuts+=k
            }
            cuts+=e
            for((a,b) in cuts.zipWithNext())if(b-a>=minimum)
                output+=MelodyNote(a*10,(b-a)*10,n.midi,prob.sliceArray(a until b).average().toFloat())
        }
        require(output.isNotEmpty()){"没有找到稳定旋律，请选择清晰人声或逐个音的独奏"}
        return MelodyScore(output,duration)
    }

    /** Local log-energy valleys, prominence >=0.65, at least 200ms apart. */
    internal fun valleys(energy:DoubleArray):List<Int> {
        val x=DoubleArray(energy.size){-ln(max(1e-5,energy[it]))}
        val candidates=mutableListOf<Int>();var i=1
        while(i<x.lastIndex) {
            if(x[i]>x[i-1]) {
                var end=i
                while(end<x.lastIndex && x[end+1]==x[i])end++
                if(end<x.lastIndex && x[end]>x[end+1]) {
                    val k=(i+end)/2;var left=x[k];var right=x[k]
                    var j=k-1
                    while(j>=0 && x[j]<=x[k]){left=min(left,x[j]);j--}
                    j=k+1
                    while(j<x.size && x[j]<=x[k]){right=min(right,x[j]);j++}
                    if(x[k]-max(left,right)>=.65)candidates+=k
                }
                i=end
            }
            i++
        }
        val accepted=mutableListOf<Int>()
        for(k in candidates.sortedByDescending{x[it]})if(accepted.none{abs(it-k)<20})accepted+=k
        return accepted.sorted()
    }
}
