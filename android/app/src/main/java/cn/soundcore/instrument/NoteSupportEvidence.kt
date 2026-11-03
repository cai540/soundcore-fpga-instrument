package cn.soundcore.instrument

import kotlin.math.*

/** Project-designed note-level evidence contract. No absolute pitch, song/key,
 * lyric, title or file identity enters the learned support decision.
 * CREPE activations and the YIN/pYIN-style physical track keep their own provenance.
 */
internal class NoteSupportEvidence(private val track:StablePitchTracker.Track,
    private val neural:Array<FloatArray>) {
    init {
        require(track.pitch.size==track.probability.size && track.pitch.size==track.rms.size)
        require(neural.isNotEmpty() && neural.all{it.size==360})
    }
    private val peakRms=max(1e-9,track.rms.maxOrNull()?:0.0)
    private val peaks=IntArray(neural.size){f->neural[f].indices.maxBy{neural[f][it]}}
    data class Vector(val values:DoubleArray,val neuralMean:Double,val physicalAgreement:Double,
        val physicalConfidence:Double)

    fun candidate(note:MelodyNote,midi:Int):Vector {
        val trim=min(70,note.durationMs/5)
        val a=((note.startMs+trim)/20).coerceIn(0,neural.size)
        val z=((note.startMs+note.durationMs-trim)/20).coerceIn(a,neural.size)
        val lo=((note.startMs+trim)/10).coerceIn(0,track.pitch.size)
        val hi=((note.startMs+note.durationMs-trim)/10).coerceIn(lo,track.pitch.size)
        val bin=(((midi-69-12*log2(10.0/440))*100-1997.3794084376191)/20).roundToInt()
        var activation=0.0;var strong=0.0;var relative=0.0;var winner=0.0
        for(f in a until z){
            var v=0.0
            for(k in max(0,bin-2)..min(359,bin+2))v=max(v,neural[f][k].toDouble())
            val top=neural[f][peaks[f]].toDouble()
            activation+=v;if(v>=.35)strong++
            if(top>=.05)relative+=v/top
            if(abs(peaks[f]-bin)<=4 && top>=.12)winner++
        }
        var agreement=0.0;var confidence=0.0;var voiced=0.0;var weighted=0.0
        var octaveConflict=0.0;var distance=0.0;var energy=0.0
        for(f in lo until hi){
            val p=track.probability[f].takeIf{it.isFinite()}?.coerceIn(0.0,1.0)?:0.0
            confidence+=p;energy+=(track.rms[f]/peakRms).coerceIn(0.0,1.0)
            val pitch=track.pitch[f]
            if(pitch.isFinite() && p>=.1){
                val error=abs(pitch-midi);voiced++
                if(error<.8)agreement++
                weighted+=p*exp(-.5*(error/.65).pow(2))
                if(abs(error-12)<.8)octaveConflict++
                distance+=min(1.0,error/12)
            }
        }
        val n=max(1,z-a).toDouble();val m=max(1,hi-lo).toDouble()
        val values=doubleArrayOf(activation/n,strong/n,relative/n,winner/n,weighted/m,
            agreement/m,confidence/m,voiced/m,octaveConflict/m,distance/m,energy/m,
            (note.durationMs/1000.0).coerceIn(0.0,1.0))
        return Vector(values,values[0],values[5],values[6])
    }
    companion object {
        val NAMES=listOf("neural_mean","neural_strong_fraction","neural_relative",
            "neural_winner_fraction","physical_weighted_close","physical_agreement",
            "physical_confidence","physical_voiced_fraction","physical_octave_conflict",
            "physical_distance","relative_rms","duration_seconds_capped")
    }
}
