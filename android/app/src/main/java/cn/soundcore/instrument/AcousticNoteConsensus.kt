package cn.soundcore.instrument

import kotlin.math.*

/** One owner for final label validation. Accepted acoustic/neural decisions keep
 * their established behaviour. The independently trained head annotates weak
 * evidence for review; synthetic-only training does not give it authority to
 * change pitches, reject events or move their clock on real singing.
 */
internal object AcousticNoteConsensus {
    fun resolve(notes:List<MelodyNote>,track:StablePitchTracker.Track,neural:Array<FloatArray>,
        cancelled:()->Boolean={false}):List<MelodyNote> {
        val evidence=NoteSupportEvidence(track,neural)
        return notes.mapNotNull{note->
            if(cancelled())throw InterruptedException("已取消识别")
            if(note.durationMs<120)return@mapNotNull note
            val trim=min(70,note.durationMs/5)
            val a=((note.startMs+trim)/20).coerceIn(0,neural.size)
            val z=((note.startMs+note.durationMs-trim)/20).coerceIn(0,neural.size)
            if(z-a<3)return@mapNotNull note
            val lo=((note.startMs+trim)/10).coerceIn(0,track.pitch.size)
            val hi=((note.startMs+note.durationMs-trim)/10).coerceIn(0,track.pitch.size)
            if(hi<=lo)return@mapNotNull note
            val old=evidence.candidate(note,note.midi)
            // 1% pYIN no-trough fallback is not an acoustic note. Nor may an
            // unrelated neural peak justify this label after event restoration.
            if(note.durationMs<=250 && old.neuralMean<.12 && old.physicalConfidence<.1)return@mapNotNull null
            var best=note.midi;var selected=old
            for(pitch in max(24,note.midi-12)..min(95,note.midi+12)){
                val value=if(pitch==note.midi)old else evidence.candidate(note,pitch)
                if(value.neuralMean>selected.neuralMean){best=pitch;selected=value}
            }
            val guarded=best!=note.midi && selected.neuralMean>=.35 && selected.neuralMean>old.neuralMean*1.35 &&
                selected.physicalAgreement>=.5 && selected.physicalAgreement>=old.physicalAgreement+.2
            val accepted=if(guarded)selected else old
            note.copy(midi=if(guarded)best else note.midi,
                confidence=NoteSupportModel.score(accepted.values).toFloat())
        }
    }
}
