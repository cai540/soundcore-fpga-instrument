package cn.soundcore.instrument

import java.io.ByteArrayOutputStream
import kotlin.math.*

data class MelodyNote(val startMs: Int, val durationMs: Int, val midi: Int,
    val confidence: Float)
data class ScoreEvent(val durationMs: Int, val note: Int?) {
    init { require(durationMs in 1..65535 && (note == null || note in 0..71)) }
    fun word(): Int = (durationMs shl 7) or (note ?: 127)
}
data class MelodyScore(val notes: List<MelodyNote>, val sourceDurationMs: Int,val keepScoreRests:Boolean=false,val tonicKey:Int?=null) {
    init { require(tonicKey==null || tonicKey in 0..11) }
    val firstMs get() = notes.first().startMs
    val durationMs get() = if(keepScoreRests)sourceDurationMs else notes.last().let { it.startMs + it.durationMs } - firstMs
    val suggestedTranspose: Int? get() {
        if (notes.isEmpty()) return null
        val lo = notes.minOf { it.midi }; val hi = notes.maxOf { it.midi }
        if (hi - lo > 71) return null
        return 0.coerceIn(PitchLayout.MIDI_MIN - lo, PitchLayout.MIDI_MAX - hi)
    }
    fun events(transpose: Int): List<ScoreEvent> {
        require(notes.isNotEmpty() && durationMs <= 180000)
        val result = mutableListOf<ScoreEvent>(); var cursor = if(keepScoreRests)0 else firstMs
        notes.forEach { n ->
            require(n.startMs >= cursor && n.durationMs >= 20)
            require(n.midi + transpose in PitchLayout.MIDI_MIN..PitchLayout.MIDI_MAX) { "旋律超出设备音域" }
            if (n.startMs > cursor) result += ScoreEvent(n.startMs - cursor, null)
            result += ScoreEvent(n.durationMs, n.midi + transpose - PitchLayout.MIDI_MIN)
            cursor = n.startMs + n.durationMs
        }
        if(keepScoreRests && cursor<sourceDurationMs)result+=ScoreEvent(sourceDurationMs-cursor,null)
        require(result.size <= 1023) { "音符太密，请缩短录音" }
        return result
    }
}

/** Local monophonic pitch probabilities, temporal tracking and note segmentation.
 * Based on YIN/pYIN; see StablePitchTracker and the bundled ISC attribution.
 * Frame pitch is not a note event: preserve rests and repeated syllable attacks.
 */
object MelodyRecognition {
    const val RATE = 16000
    const val ALGORITHM_VERSION = 7

    fun resample(samples: FloatArray, sampleRate: Int): FloatArray {
        require(sampleRate in 8000..192000 && samples.size <= sampleRate * 41)
        require(samples.all { it.isFinite() })
        if (sampleRate == RATE) return samples.copyOf()
        val result=FloatArray(((samples.size.toLong()*RATE+sampleRate-1)/sampleRate).toInt())
        var used=0;val sampler=PcmResampler(sampleRate){result[used++]=it}
        samples.forEach(sampler::push);sampler.finish()
        check(used==result.size)
        return result
    }

    @JvmOverloads
    fun recognize(samples: FloatArray, sampleRate: Int,
        progress: (Int) -> Unit = {}, cancelled: () -> Boolean = { false },
        mode: MelodyInput = MelodyInput.VOCAL): MelodyScore {
        require(sampleRate in 8000..192000)
        require(samples.size >= sampleRate / 4) { "录音太短，请录制更完整的旋律" }
        require(samples.size <= sampleRate * 40) { "支持40秒以内的录音" }
        if (cancelled()) throw InterruptedException("已取消识别")
        val pcm = resample(samples, sampleRate)
        val raw = StablePitchTracker.track(pcm, progress, cancelled,exactWindow=mode==MelodyInput.VOCAL)
        if (cancelled()) throw InterruptedException("已取消识别")
        return decode(pcm,raw,samples.size*1000/sampleRate,progress,cancelled,mode)
    }

    /** Shared tested event decoder; observers never edit an emitted note list. */
    internal fun decode(pcm:FloatArray,raw:StablePitchTracker.Track,durationMs:Int,
        progress:(Int)->Unit={},cancelled:()->Boolean={false},mode:MelodyInput=MelodyInput.VOCAL,
        refineHarmonics:Boolean=true,minimumVocalDwell:Int=15):MelodyScore {
        val track=if(mode==MelodyInput.VOCAL && refineHarmonics)HarmonicRegisterRefinement.refine(pcm,raw,cancelled) else raw
        progress(91)
        val onset=if(mode==MelodyInput.VOCAL)VocalOnsetEvidence.onsetEvidence(pcm,cancelled) else null
        progress(94)
        val seed = VocalNoteSegmentation.segment(track,durationMs,mode,cancelled,onset,minimumVocalDwell)
        val score=if(mode==MelodyInput.VOCAL) {
            val boundary=VocalBoundaryEvidence.analyze(pcm,track.rms,cancelled)
            val refined=VocalNaturalRefinement.refine(seed.notes,track,boundary,onset!!,cancelled)
            val alternative=VocalMainNoteSegmentation.alternative(track,seed.sourceDurationMs,cancelled,onset)
            val recovered=VocalAlternativeRestoration.apply(refined.notes,alternative.notes,track,boundary.novelty,cancelled)
            val release=ReleaseContourProjection.apply(recovered,track,onset,cancelled)
            val validated=VocalOctaveValidation.refine(pcm,release,cancelled)
            val projected=VocalContourProjection.apply(validated,track,onset,boundary.novelty,cancelled)
            MelodyScore(projected,seed.sourceDurationMs)
        } else seed
        if (cancelled()) throw InterruptedException("已取消识别")
        progress(100)
        return score
    }
}

object MelodyWire {
    fun bytes(events: List<ScoreEvent>): ByteArray = events.flatMap { e ->
        val w = e.word(); listOf(w.toByte(), (w shr 8).toByte(), (w shr 16).toByte())
    }.toByteArray()
    fun crc16(bytes: ByteArray): Int {
        var crc = 0xffff
        bytes.forEach { b ->
            crc = crc xor ((b.toInt() and 255) shl 8)
            repeat(8) { crc = ((crc shl 1) xor (if (crc and 0x8000 != 0) 0x1021 else 0)) and 65535 }
        }
        return crc
    }
    fun preview(events: List<ScoreEvent>, rate: Int = 16000): ShortArray {
        val out = ShortArray(events.sumOf { it.durationMs } * rate / 1000)
        var offset = 0; var phase = 0.0
        events.forEach { e ->
            val count = e.durationMs * rate / 1000
            val hz = e.note?.let { 440 * 2.0.pow((it + PitchLayout.MIDI_MIN - 69) / 12.0) } ?: 0.0
            for (i in 0 until count) {
                val envelope = min(1.0, min(i / (rate * .012), (count - 1 - i) / (rate * .018))).coerceAtLeast(0.0)
                if (offset + i < out.size) out[offset + i] =
                    (if (hz == 0.0) 0 else (sin(phase) * envelope * 7500).toInt()).toShort()
                phase = (phase + 2 * PI * hz / rate) % (2 * PI)
            }
            offset += count
        }
        return out
    }
    /** Standard MIDI, fixed 500000us/quarter and 1000 ticks/quarter: 2 ticks/ms. */
    fun midi(events: List<ScoreEvent>): ByteArray {
        val track = ByteArrayOutputStream()
        fun variable(v: Int) { var n = v; val parts = mutableListOf(n and 127)
            while (n > 127) { n = n ushr 7; parts.add(0, (n and 127) or 128) }; parts.forEach(track::write) }
        track.write(byteArrayOf(0, 0xff.toByte(), 0x51, 3, 7, 0xa1.toByte(), 0x20))
        var rest = 0
        events.forEach { e ->
            if (e.note == null) rest += e.durationMs * 2
            else {
                variable(rest); rest = 0; track.write(byteArrayOf(0x90.toByte(), (e.note + PitchLayout.MIDI_MIN).toByte(), 88))
                variable(e.durationMs * 2); track.write(byteArrayOf(0x80.toByte(), (e.note + PitchLayout.MIDI_MIN).toByte(), 0))
            }
        }
        variable(rest); track.write(byteArrayOf(0xff.toByte(), 0x2f, 0))
        val out = ByteArrayOutputStream()
        out.write(byteArrayOf(77,84,104,100,0,0,0,6,0,0,0,1,3,0xe8.toByte(),77,84,114,107))
        val n = track.size(); out.write(byteArrayOf((n ushr 24).toByte(),(n ushr 16).toByte(),(n ushr 8).toByte(),n.toByte()))
        out.write(track.toByteArray()); return out.toByteArray()
    }
}
