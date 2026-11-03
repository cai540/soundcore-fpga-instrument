package cn.soundcore.instrument

/** A small UI summary, never audio or an instruction to generate a note. */
data class CaptureDisplay(val stage:Int=0,val progress:Int=0,val position:Int=0,
    val duration:Int=0,val notes:Int=0,val midi:Int=255,val level:Int=0) {
    init { require(stage in 0..8 && progress in 0..100 && position in 0..1800 && duration in 0..1800 &&
        notes in 0..1023 && (midi in 24..108 || midi==255) && level in 0..255) }
    fun payload()=byteArrayOf(1,stage.toByte(),progress.toByte(),position.toByte(),(position ushr 8).toByte(),
        duration.toByte(),(duration ushr 8).toByte(),notes.toByte(),(notes ushr 8).toByte(),midi.toByte(),level.toByte())
    companion object {
        fun from(v:MelodyView,visible:Boolean):CaptureDisplay {
            if(!visible)return CaptureDisplay()
            val stage=when {v.recording->1;v.busy->if(v.readingSource)8 else 3
                v.previewing->if(v.originalPreview)5 else 6
                v.score!=null->if(v.edited)7 else 4;v.hasSource->2;else->0}
            val range=v.range
            val pos=if(v.recording)v.seconds*10 else ((v.positionMs-(if(v.previewing)range?.startMs?:0 else 0))/100).coerceIn(0,1800)
            val dur=if(v.recording)1800 else (if(v.previewing)range?.durationMs?:0 else range?.endMs?:0)/100
            val progress=if(v.previewing && dur>0)pos*100/dur else if(stage==7 && v.score!=null)
                (v.selectedNote+1).coerceAtLeast(0)*100/v.score.notes.size else v.progress
            return CaptureDisplay(stage,progress.coerceIn(0,100),pos,dur.coerceIn(0,1800),v.score?.notes?.size?:0,
                v.score?.notes?.getOrNull(v.selectedNote)?.midi?.let{(it+v.transpose).coerceIn(24,108)}?:255,v.level.coerceIn(0,255))
        }
    }
}

/** Coalesce frequent progress notifications; at most 2 packets/s, refresh lease. */
class CaptureDisplayQueue {
    private var desired=CaptureDisplay();private var sent:CaptureDisplay?=null
    private var sentAt:Long?=null
    fun offer(value:CaptureDisplay){desired=value}
    fun reset(){sent=null;sentAt=null}
    fun take(now:Long):CaptureDisplay? {
        val elapsed=sentAt?.let{now-it}?:Long.MAX_VALUE
        if(elapsed<500 || desired==sent && (desired.stage==0 || elapsed<1500))return null
        sent=desired;sentAt=now;return desired
    }
}
