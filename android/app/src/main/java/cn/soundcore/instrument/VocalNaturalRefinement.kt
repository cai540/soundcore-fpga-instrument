package cn.soundcore.instrument

/** Conservative seeds -> measured note restoration -> weak ambiguous-pitch
 * refinement. Newly established notes/boundaries outrank a tonal prior.
 * References and lyric clocks are deliberately absent from the interface.
 */
internal object VocalNaturalRefinement {
    data class Result(val restored:List<MelodyNote>,val quantized:List<MelodyNote>,
        val notes:List<MelodyNote>,val protectedNotes:BooleanArray,val protectedBoundaries:BooleanArray)

    internal fun protections(seeds:List<MelodyNote>,restored:List<MelodyNote>):Pair<BooleanArray,BooleanArray> {
        val protectedNotes=BooleanArray(restored.size)
        val protectedBoundaries=BooleanArray(restored.size)
        val originalStarts=seeds.map{it.startMs}.toSet();var parent=0
        for((i,n) in restored.withIndex()) {
            while(parent<seeds.lastIndex && n.startMs>=seeds[parent].startMs+seeds[parent].durationMs)parent++
            val seed=seeds.getOrNull(parent)?:continue
            val contained=n.startMs>=seed.startMs && n.startMs+n.durationMs<=seed.startMs+seed.durationMs
            protectedNotes[i]=contained && n.midi!=seed.midi
            protectedBoundaries[i]=i>0 && n.startMs !in originalStarts
        }
        return protectedNotes to protectedBoundaries
    }

    fun refine(seeds:List<MelodyNote>,track:StablePitchTracker.Track,
        boundary:VocalBoundaryEvidence.Result,onset:DoubleArray,cancelled:()->Boolean={false}):Result {
        if(cancelled())throw InterruptedException("已取消识别")
        val restored=VocalEventRestoration.refine(seeds,track,boundary.novelty,cancelled)
        val (protectedNotes,protectedBoundaries)=protections(seeds,restored)
        val quantized=TonalPitchRefinement.apply(restored,track,protectedNotes,cancelled)
        val result=TonalBoundaryCoalescing.apply(restored,quantized,boundary.strength,onset,
            track.rms,protectedBoundaries,cancelled)
        if(cancelled())throw InterruptedException("已取消识别")
        return Result(restored,quantized,result,protectedNotes,protectedBoundaries)
    }
}
