from pathlib import Path
R=Path(__file__).resolve().parents[1];p=R/'app/android/app/src/main/java/cn/soundcore/instrument/BleController.kt';t=p.read_text(encoding='utf8')
def rep(a,b):
    global t
    assert a in t,a[:100];t=t.replace(a,b)
rep('val captureSupported: Boolean? = null','val captureSupported: Boolean? = null,\n    val pitchLayout:PitchLayoutState?=null,\n    val layoutSupported:Boolean?=null')
rep('captureSupported=null))','captureSupported=null,pitchLayout=null,layoutSupported=null))')
rep('if (!view.connected || view.scoreSupported != true || view.state?.writeAllowed != true)', 'if (!view.connected || view.pitchLayout==null || view.scoreSupported != true || view.state?.writeAllowed != true)')
rep('view.state?.vibratoDepth == null) return','view.state?.vibratoDepth == null || view.pitchLayout==null) return')
rep('    fun noteOff(pad: Int)', '''    fun exactNote(index:Int,down:Boolean,velocity:Int=176) {
        if(index !in 0..71 || !view.connected || view.pitchLayout==null || view.state?.writeAllowed!=true)return
        if(down)realtime.downAbsolute(index,velocity) else realtime.upAbsolute(index)
        heldPadMask=realtime.held;dispatchNext()
    }

    fun noteOff(pad: Int)''')
rep('    fun commandBytes(type: Int, payload: ByteArray = byteArrayOf()) {','''    fun commandBytes(type: Int, payload: ByteArray = byteArrayOf()) {
        if((type in Protocol.SET_VOLUME..Protocol.REALTIME_ABSOLUTE || type==Protocol.SET_KEY ||
            Protocol.isScoreTransfer(type) || type==Protocol.SCORE_ACTION) &&
            type!=Protocol.ALL_NOTES_OFF && type!=Protocol.HEARTBEAT && view.pitchLayout==null)
            return status("请先升级为配套的七自然音固件")
        if(type==Protocol.SET_BANK || type==Protocol.SET_KEY || type==Protocol.SET_SCENE)releaseAllNotes()''')
rep('commands.contains(Protocol.SET_BANK) || commands.contains(Protocol.SET_SCENE)', 'commands.contains(Protocol.SET_BANK) || commands.contains(Protocol.SET_SCENE) ||\n            inflightType==Protocol.SET_KEY || commands.contains(Protocol.SET_KEY)')
rep('if (view.state?.realtimeNotes == true && (!bankTransaction', 'if (view.pitchLayout!=null && view.state?.realtimeNotes == true && (!bankTransaction')
rep('Protocol.encodeCommand(Protocol.REALTIME_NOTES, next, packet.payload())','Protocol.encodeCommand(packet.type, next, packet.payload())')
rep('beginTransport(Protocol.REALTIME_NOTES)','beginTransport(packet.type)')
rep('transportType == Protocol.REALTIME_NOTES','transportType == Protocol.REALTIME_NOTES || transportType==Protocol.REALTIME_ABSOLUTE')
rep('command(Protocol.GET_STATE)\n                command(Protocol.SCORE_STATUS)','command(Protocol.GET_LAYOUT)\n                command(Protocol.GET_STATE)\n                command(Protocol.SCORE_STATUS)')
t=t.replace('requestType in Protocol.SCORE_BEGIN..Protocol.SCORE_COMMIT','Protocol.isScoreTransfer(requestType)').replace('failedType in Protocol.SCORE_BEGIN..Protocol.SCORE_COMMIT','Protocol.isScoreTransfer(failedType)')
rep('                Protocol.CAPTURE_STATE -> {','''                Protocol.LAYOUT_STATE -> {
                    val layout=PitchLayoutState.from(frame.payload)
                    publish(view.copy(pitchLayout=layout,layoutSupported=layout!=null,pending=false,
                        message=if(layout!=null)"已连接 · 七自然音 / 完整半音" else "音高版本不匹配，请升级配套固件"))
                    if(layout!=null)view.uploadedScore?.let { score ->
                        if(score.schema==2 && score.noteIndex!=null)publish(view.copy(uploadedScore=score.copy(bank=PitchLayout.bank(score.noteIndex,layout.key))))
                    }
                }
                Protocol.CAPTURE_STATE -> {''')
rep('val state = UploadedScoreState.from(frame.payload)','val parsed = UploadedScoreState.from(frame.payload)\n                    val state=parsed?.let{if(it.noteIndex!=null)it.copy(bank=PitchLayout.bank(it.noteIndex,view.pitchLayout?.key?:0)) else it}')
rep('val code = frame.payload.firstOrNull()?.toInt()?.and(0xff) ?: -1','''val code = frame.payload.firstOrNull()?.toInt()?.and(0xff) ?: -1
                    if(requestType==Protocol.GET_LAYOUT || requestType==Protocol.SET_KEY){
                        publish(view.copy(pending=false,pitchLayout=null,layoutSupported=false,
                            message="设备仍是旧版音高编码，请安装配套七自然音固件"))
                        dispatchNext();return@forEach
                    }''')
rep('else "已连接 · FPGA 已确认"', 'else if(view.layoutSupported==false)"设备需要升级七自然音固件" else "已连接 · FPGA 已确认"')
rep('if (view.scoreSupported == true) command(Protocol.SCORE_STATUS)','if (view.scoreSupported == true) command(Protocol.SCORE_STATUS)\n                    if(view.layoutSupported!=false)command(Protocol.GET_LAYOUT)')
p.write_text(t,encoding='utf8')
