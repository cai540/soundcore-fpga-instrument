package cn.soundcore.instrument

import kotlin.math.*

/** Source time is never rebased by trimming or local recognition. */
data class MelodyRange(val startMs: Int, val endMs: Int) {
    init { require(startMs >= 0 && endMs - startMs in 250..180000) }
    val durationMs get() = endMs - startMs
    fun samples(pcm: FloatArray, rate: Int): FloatArray {
        val a = (startMs.toLong() * rate / 1000).toInt()
        val b = (endMs.toLong() * rate / 1000).toInt()
        require(a >= 0 && b <= pcm.size && b > a)
        return pcm.copyOfRange(a, b)
    }
}

data class MelodyRevision(val score:MelodyScore,val transpose:Int,val range:MelodyRange?,val edited:Boolean,
    val origin:String="local",val algorithm:String="local-${MelodyRecognition.ALGORITHM_VERSION}")

object MelodyWorkspace {
    fun absolute(score: MelodyScore, offsetMs: Int, sourceDurationMs: Int): MelodyScore =
        validated(score.copy(notes=score.notes.map { it.copy(startMs = it.startMs + offsetMs) },sourceDurationMs=sourceDurationMs))

    fun validated(score: MelodyScore): MelodyScore {
        require(score.notes.isNotEmpty() && score.sourceDurationMs in 250..180000)
        var end = 0
        score.notes.forEach { n ->
            require(n.startMs >= end && n.durationMs >= 20 && n.midi in 24..108 &&
                n.confidence.isFinite() && n.startMs.toLong() + n.durationMs <= score.sourceDurationMs)
                { "音符不能重叠、短于20毫秒或超出原音范围" }
            end = n.startMs + n.durationMs
        }
        require(score.durationMs <= 180000 && score.notes.size <= 1023)
        score.suggestedTranspose?.let { score.events(it) }
        return score
    }

    fun edit(score: MelodyScore, index: Int, semitones: Int = 0,
             durationDelta: Int = 0, onsetDelta: Int = 0): MelodyScore {
        require(index in score.notes.indices)
        val n = score.notes[index]
        val next = n.copy(midi = n.midi + semitones, startMs = n.startMs + onsetDelta,
            durationMs = n.durationMs + durationDelta - onsetDelta)
        return validated(score.copy(notes = score.notes.toMutableList().also { it[index] = next }))
    }

    fun split(score: MelodyScore, index: Int, atMs: Int): MelodyScore {
        val n = score.notes[index]
        require(atMs - n.startMs >= 60 && n.startMs + n.durationMs - atMs >= 60) { "请在音符中间分开" }
        return validated(score.copy(notes = score.notes.take(index) +
            listOf(n.copy(durationMs = atMs - n.startMs),
                n.copy(startMs = atMs, durationMs = n.startMs + n.durationMs - atMs)) + score.notes.drop(index + 1)))
    }

    fun merge(score: MelodyScore, index: Int): MelodyScore {
        val a = score.notes[index]; val b = score.notes.getOrNull(index + 1) ?: error("后面没有音符")
        require(a.midi == b.midi && b.startMs - a.startMs - a.durationMs <= 120) { "只能合并紧邻的相同音高" }
        return validated(score.copy(notes = score.notes.take(index) +
            a.copy(durationMs = b.startMs + b.durationMs - a.startMs) + score.notes.drop(index + 2)))
    }

    fun delete(score:MelodyScore,index:Int):MelodyScore {
        require(score.notes.size>1 && index in score.notes.indices) { "至少保留一个音符" }
        return validated(score.copy(notes=score.notes.filterIndexed { i,_ -> i!=index }))
    }

    /** Keep both outside tails of notes crossing the replacement range. */
    fun replace(score: MelodyScore, range: MelodyRange, local: MelodyScore): MelodyScore {
        require(local.sourceDurationMs <= range.durationMs + 1)
        val kept = score.notes.flatMap { n ->
            val end = n.startMs + n.durationMs
            if (end <= range.startMs || n.startMs >= range.endMs) listOf(n)
            else buildList {
                if (range.startMs - n.startMs >= 20) add(n.copy(durationMs = range.startMs - n.startMs))
                if (end - range.endMs >= 20) add(n.copy(startMs = range.endMs, durationMs = end - range.endMs))
            }
        }
        val replacement = local.notes.map { it.copy(startMs = it.startMs + range.startMs) }
        val joined=mutableListOf<MelodyNote>()
        for(n in (kept+replacement).sortedBy{it.startMs}) {
            val previous=joined.lastOrNull()
            // Cropping a sustained note must not invent an extra attack at
            // either cut edge. Genuine same-pitch attacks INSIDE stay intact.
            if(previous!=null && previous.midi==n.midi && previous.startMs+previous.durationMs==n.startMs &&
                (n.startMs==range.startMs || n.startMs==range.endMs))
                joined[joined.lastIndex]=previous.copy(durationMs=n.startMs+n.durationMs-previous.startMs)
            else joined+=n
        }
        return validated(score.copy(notes=joined))
    }

    fun preview(score: MelodyScore, transpose: Int, range: MelodyRange): ShortArray {
        val result = ShortArray(range.durationMs * 16)
        val partial = score.notes.mapNotNull { n ->
            val a = max(range.startMs, n.startMs); val b = min(range.endMs, n.startMs + n.durationMs)
            if (b - a < 20) null else n.copy(startMs = a, durationMs = b - a)
        }
        if (partial.isEmpty()) return result
        val scoped = MelodyScore(partial, score.sourceDurationMs)
        val samples = MelodyWire.preview(scoped.events(transpose))
        val offset = (scoped.firstMs - range.startMs) * 16
        samples.copyInto(result, offset, 0, min(samples.size, result.size - offset))
        return result
    }

    fun nearest(score: MelodyScore, timeMs: Int): Int = score.notes.indices.minByOrNull {
        val n = score.notes[it]
        when { timeMs < n.startMs -> n.startMs - timeMs
            timeMs > n.startMs + n.durationMs -> timeMs - n.startMs - n.durationMs
            else -> 0 }
    } ?: -1

    fun noteName(midi: Int): String = arrayOf("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B")[midi.mod(12)] + (midi / 12 - 1)
}
