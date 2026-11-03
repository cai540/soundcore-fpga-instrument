package cn.soundcore.instrument

import kotlin.math.*

/** Optional, conservative perceptual projection of an uncertain release bend.
 * This is NOT an F0 correction: the bend may exist in the voice, but need not
 * become a separately retriggered instrument note. All existing pitch cores,
 * clear note centres, real gaps, ongoing passages and energetic attacks remain.
 * No song, lyrics, target score, key or specific source time enters this helper.
 * Intentionally detuned, weak expressive ending notes remain a known ambiguity.
 */
internal object ReleaseContourProjection {
    private fun median(a:DoubleArray):Double {a.sort();return if(a.size%2==1)a[a.size/2] else (a[a.size/2-1]+a[a.size/2])/2}
    private fun quantile(a:DoubleArray,f:Double):Double {
        val x=(a.size-1)*f;val i=x.toInt();return a[i]*(1-(x-i))+a[min(i+1,a.lastIndex)]*(x-i)
    }
    private fun clearPitch(p:DoubleArray,note:Int):Boolean {
        val finite=p.filter{it.isFinite()}.sorted().toDoubleArray()
        if(finite.size<10 || finite.size<p.size*.8)return true
        val lo=quantile(finite,.1);val hi=quantile(finite,.9)
        val center=finite.filter{it>=lo && it<=hi}.average()
        if(abs(center-note)<=.35 || finite.count{abs(it-note)<.45}>=finite.size*.7)return true
        val q=DoubleArray(p.size){i->
            val w=p.copyOfRange(max(0,i-1),min(p.size,i+2))
            if(w.all{it.isFinite()})median(w) else p[i]
        }
        // Inspect the original 140ms core, rather than eroding its two edges
        // with a centred derivative window (which would demand ~200ms).
        for(i in 0..q.size-14) {
            val core=q.copyOfRange(i,i+14)
            if(core.all{it.isFinite() && abs(it-note)<.45} && core.max()-core.min()<.32)return true
        }
        return false
    }
    private fun correlation(a:DoubleArray,b:DoubleArray):Double {
        val am=a.average();val bm=b.average();var xy=0.0;var xx=0.0;var yy=0.0
        for(i in a.indices){val x=a[i]-am;val y=b[i]-bm;xy+=x*y;xx+=x*x;yy+=y*y}
        return if(xx*yy>1e-12)xy/sqrt(xx*yy) else 0.0
    }
    fun apply(notes:List<MelodyNote>,track:StablePitchTracker.Track,onset:DoubleArray,
        cancelled:()->Boolean={false}):List<MelodyNote> {
        val out=mutableListOf<MelodyNote>();var i=0
        while(i<notes.size) {
            if(cancelled())throw InterruptedException("已取消识别")
            val main=notes[i]
            if(i+1>=notes.size){out+=main;break}
            val tail=notes[i+1];val end=tail.startMs+tail.durationMs
            val gap=if(i+2<notes.size)notes[i+2].startMs-end else 1000
            var merge=main.startMs+main.durationMs==tail.startMs && main.durationMs>=450 &&
                tail.durationMs in 150..450 && gap>=200 && abs(main.midi-tail.midi) in 1..2
            val start=tail.startMs/10;val finish=end/10;val previous=max(main.startMs/10,start-25)
            if(merge)merge=start>=3 && finish-start>=12 && start-previous>=10 &&
                finish<=track.pitch.size && finish<=track.rms.size && finish<=track.probability.size && finish<=onset.size
            if(merge)merge=!clearPitch(track.pitch.copyOfRange(start,finish),tail.midi)
            if(merge) {
                val rms=track.rms.copyOfRange(start,finish);val prior=track.rms.copyOfRange(previous,start)
                merge=rms.all{it.isFinite() && it>0} && prior.all{it.isFinite()} && prior.max()>0
                if(merge) {
                    val q=max(3,rms.size/4);val drop=rms.takeLast(q).average()/rms.take(q).average()
                    val slope=correlation(DoubleArray(rms.size){it.toDouble()},DoubleArray(rms.size){ln(max(1e-9,rms[it]))})
                    val peak=rms.max()/prior.max();val mass=median(track.probability.copyOfRange(start,finish))
                    val attack=onset.copyOfRange(start-3,min(onset.size,start+4)).max()
                    merge=drop<=.5 && slope<=-.8 && peak<=.9 && mass<.45 && attack<.35
                }
            }
            if(merge){out+=main.copy(durationMs=end-main.startMs);i+=2} else {out+=main;i++}
        }
        return out
    }
}
