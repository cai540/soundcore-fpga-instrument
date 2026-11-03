package cn.soundcore.instrument

import kotlin.math.*

/** Remove only an equivalent boundary introduced by pitch refinement.
 * The caller's phoneticStrength must be a measured, gain-normalized envelope
 * change on the same 10ms grid (0=no independent phonetic evidence).
 * Missing evidence never means that no onset happened: keep the boundary.
 * Original same-pitch repetitions and real silence are always preserved.
 */
internal object TonalBoundaryCoalescing {
    fun apply(original:List<MelodyNote>,refined:List<MelodyNote>,
        phoneticStrength:DoubleArray?,onsetEvidence:DoubleArray?,rms:DoubleArray,
        cancelled:()->Boolean={false}):List<MelodyNote> =
        apply(original,refined,phoneticStrength,onsetEvidence,rms,null,cancelled)

    /** A boundary already established by independent note-level evidence has
     * priority over a weak tonal prior, even when its neighbouring pitches tie.
     */
    fun apply(original:List<MelodyNote>,refined:List<MelodyNote>,
        phoneticStrength:DoubleArray?,onsetEvidence:DoubleArray?,rms:DoubleArray,
        protectedBoundaries:BooleanArray?,cancelled:()->Boolean):List<MelodyNote> {
        if(cancelled())throw InterruptedException("已取消识别")
        require(original.size==refined.size)
        require(protectedBoundaries==null || protectedBoundaries.size==refined.size)
        require(original.indices.all{original[it].startMs==refined[it].startMs && original[it].durationMs==refined[it].durationMs})
        if(refined.size<2 || phoneticStrength==null || onsetEvidence==null || rms.isEmpty())return refined
        val floor=max(.0025,(rms.maxOrNull()?:0.0)*.035)
        val out=mutableListOf(refined.first())
        for(i in 1 until refined.size) {
            if(i%32==0 && cancelled())throw InterruptedException("已取消识别")
            val n=refined[i];val previous=out.last();val boundary=n.startMs/10
            val edited=original[i-1].midi!=refined[i-1].midi || original[i].midi!=n.midi
            val originalRepeat=original[i-1].midi==original[i].midi
            val measured=boundary in phoneticStrength.indices && boundary in onsetEvidence.indices && boundary in rms.indices &&
                phoneticStrength[boundary].isFinite() && onsetEvidence[boundary].isFinite()
            val independent=protectedBoundaries?.get(i)==true || !measured ||
                phoneticStrength[boundary]>=.12 || onsetEvidence[boundary]>=.30
            val audible=measured && (max(0,boundary-2)..min(rms.lastIndex,boundary+2)).all{rms[it]>floor*1.5}
            // Exact adjacency avoids inventing sound in any unmeasured gap.
            if(edited && !originalRepeat && previous.midi==n.midi &&
                previous.startMs+previous.durationMs==n.startMs && !independent && audible) {
                val total=previous.durationMs+n.durationMs
                val confidence=(previous.confidence*previous.durationMs+n.confidence*n.durationMs)/total
                out[out.lastIndex]=previous.copy(durationMs=total,confidence=confidence)
            } else out+=n
        }
        return out
    }
}
