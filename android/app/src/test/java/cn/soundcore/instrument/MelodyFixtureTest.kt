package cn.soundcore.instrument

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.io.ByteArrayOutputStream
import kotlin.math.*

class MelodyFixtureTest {
    private fun wav(samples: ShortArray): ByteArray {
        val out = ByteArrayOutputStream()
        fun le(v: Int,n: Int) { repeat(n) { out.write(v ushr (it * 8) and 255) } }
        out.write("RIFF".toByteArray());le(36+samples.size*2,4);out.write("WAVEfmt ".toByteArray())
        le(16,4);le(1,2);le(1,2);le(16000,4);le(32000,4);le(2,2);le(16,2)
        out.write("data".toByteArray());le(samples.size*2,4);samples.forEach { le(it.toInt(),2) };return out.toByteArray()
    }
    @Test fun independentMelodyTimingAndCrossLanguageUploadFixture() {
        val pitches = listOf(60,64,67,67,65,62,61,69,72,71,67,64)
        val durations = listOf(500,350,900,400,300,700,250,500,1000,350,400,1300)
        val gaps = listOf(0,0,180,0,0,230,0,0,150,0,0,0)
        val pcm = mutableListOf<Float>(); val reference = mutableListOf<MelodyNote>()
        repeat(3200) { pcm += 0f }
        val random = java.util.Random(91)
        pitches.forEachIndexed { k,n ->
            val start = pcm.size / 16; var phase = 0.0
            repeat(durations[k]*16) { i ->
                val amp = min(1.0,min(i/150.0,(durations[k]*16-i-1)/250.0)).coerceAtLeast(0.0)
                val hz = 440*2.0.pow((n-69)/12.0)*2.0.pow(.12*sin(2*PI*5*i/16000)/12)
                phase += 2*PI*hz/16000
                pcm += (amp*(.23*sin(phase)+.11*sin(2*phase)+.07*sin(3*phase)) +
                    random.nextGaussian()*.002).toFloat()
            }
            reference += MelodyNote(start,durations[k],n,1f)
            repeat(gaps[k]*16) { pcm += (random.nextGaussian()*.001).toFloat() }
        }
        repeat(3200) { pcm += 0f }
        val begin = System.nanoTime()
        val score = MelodyRecognition.recognize(pcm.toFloatArray(),16000)
        val elapsed = (System.nanoTime()-begin)/1_000_000
        assertEquals(pitches,score.notes.map { it.midi })
        val errors = reference.zip(score.notes).flatMap { (a,b) ->
            listOf(abs(a.startMs-b.startMs),abs(a.startMs+a.durationMs-b.startMs-b.durationMs)) }
        assertTrue("onset/offset errors $errors",errors.max()<=60)
        val events = score.events(0)
        assertEquals("Only the three performed rests should remain: $events", 3, events.count { it.note == null })
        val out = File("../../../build/vocal_app_20261028/fixtures");out.mkdirs()
        File(out,"single_instrument_reference.wav").writeBytes(wav(pcm.map { (it*24000).toInt().toShort() }.toShortArray()))
        File(out,"recognized_preview.wav").writeBytes(wav(MelodyWire.preview(events)))
        File(out,"recognized.mid").writeBytes(MelodyWire.midi(events))
        File(out,"recognition_metrics.json").writeText("""{"notes":${pitches.size},"correct_pitches":${score.notes.size},"max_boundary_error_ms":${errors.max()},"analysis_ms_desktop":$elapsed,"duration_ms":${score.durationMs},"events":${events.size},"real_recording":false}""")
        File(out,"recognized_notes.csv").writeText("start_ms,duration_ms,midi,confidence\n"+
            score.notes.joinToString("\n") { "${it.startMs},${it.durationMs},${it.midi},${it.confidence}" })
        val t = ScoreTransfer(events,1,0x3456)
        val stream = ByteArrayOutputStream();var sequence = 5
        while(!t.done) {
            val command = t.next()!!
            stream.write(Protocol.encodeCommand(command.type,sequence++,command.payload))
            val state = when(command.type) {
                Protocol.SCORE_ABSOLUTE_BEGIN -> UploadedScoreState(2,0,0,0,7,0,1,0,t.token,schema=2)
                Protocol.SCORE_DATA -> UploadedScoreState(2,0,t.confirmed+(command.payload.size-4)/3,0,7,0,1,0,t.token,schema=2)
                else -> UploadedScoreState(1,0,t.count,0,7,0,1,t.crc,t.token,schema=2)
            }
            t.acknowledge(command.type,state)
        }
        stream.write(Protocol.encodeCommand(Protocol.SCORE_ACTION,sequence,byteArrayOf(1)))
        val bytes = stream.toByteArray()
        File(out,"android_upload.hex").writeText(bytes.joinToString("\n") { "%02x".format(it.toInt() and 255) })
        File(out,"android_upload_meta.vh").writeText("`define FIXTURE_BYTES ${bytes.size}\n`define FIXTURE_EVENTS ${events.size}\n`define FIXTURE_CRC 16'h${t.crc.toString(16)}\n`define FIXTURE_MS ${events.sumOf { it.durationMs }}\n")
    }
}
