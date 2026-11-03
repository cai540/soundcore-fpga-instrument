package cn.soundcore.instrument

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import java.util.UUID

data class FoundDevice(val name: String, val address: String)
data class BleView(
    val message: String = "尚未连接",
    val devices: List<FoundDevice> = emptyList(),
    val connected: Boolean = false,
    val state: DeviceState? = null,
    val telemetry: DeviceTelemetry? = null,
    val pending: Boolean = false,
    val scoreSupported: Boolean? = null,
    val uploadedScore: UploadedScoreState? = null,
    val uploadProgress: Int? = null,
    val scoreMessage: String = "连接设备后可传入旋律",
    val captureSupported: Boolean? = null,
    val pitchLayout:PitchLayoutState?=null,
    val padOrder:List<Int> = (0..6).toList(),
    val layoutSupported:Boolean?=null
)

/** All mutations run on the main Handler; Activity owns runtime permission requests. */
@SuppressLint("MissingPermission")
class BleController(private val context: Context, private val onChange: (BleView) -> Unit) {
    private var toolCallback:((Result<ByteArray>)->Unit)?=null
    private val toolOwner=ToolReplyOwner()
    fun requestTool(type:Int,payload:ByteArray=byteArrayOf(),callback:(Result<ByteArray>)->Unit) {
        if(!ToolWire.contains(type) || !view.connected || channel==null || gatt==null || view.pitchLayout==null){callback(Result.failure(IllegalStateException("请连接配套的声芯固件")));return}
        if(toolCallback!=null){callback(Result.failure(IllegalStateException("正在同步设备，请稍候")));return}
        try{Protocol.encodeCommand(type,0,payload)}catch(e:Exception){callback(Result.failure(e));return}
        val command=QueuedCommand(type,payload.clone());toolOwner.begin(command);toolCallback=callback
        commands.offer(command);dispatchNext()
    }
    private fun failTool(message:String){val done=toolCallback;toolCallback=null;toolOwner.clear();done?.invoke(Result.failure(IllegalStateException(message)))}
    private val captureUpdates=CaptureDisplayQueue()
    private var captureLoop=0
    fun setCaptureDisplay(value:CaptureDisplay){captureUpdates.offer(value)}
    private fun scheduleCaptureDisplay(token:Int) {
        handler.postDelayed({if(token==captureLoop && view.connected){
            if(view.captureSupported==true && scoreTransfer==null && heldPadMask==0)
                captureUpdates.take(SystemClock.uptimeMillis())?.let{commandBytes(Protocol.CAPTURE_DISPLAY,it.payload(),background=true)}
            scheduleCaptureDisplay(token)
        }},500)
    }
    private val handler = Handler(Looper.getMainLooper())
    private val adapter: BluetoothAdapter? =
        (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
    private val stream = FrameStream()
    private var scanner = adapter?.bluetoothLeScanner
    private var gatt: BluetoothGatt? = null
    private var channel: BluetoothGattCharacteristic? = null
    private var scanActive = false
    private var scanGeneration = 0
    private var connectGeneration = 0
    private var sequence = 0
    private var inflightSequence: Int? = null
    private var inflightType: Int? = null
    private var inflightFrame: ByteArray? = null
    private var inflightWriteType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
    private var inflightAttempt = 0
    private var pollGeneration = 0
    private var heartbeatGeneration = 0
    private var telemetryGeneration = 0
    private var performanceVisible = true
    private var toolsVisible=false
    fun setPadOrder(order:List<Int>){if(order.sorted()==(0..6).toList())publish(view.copy(padOrder=order))}
    fun setToolsVisible(value:Boolean){toolsVisible=value;requestPlayingPriority()}
    private var expectedScene: InstrumentScene? = null
    private val commands = CommandQueue()
    private var heldPadMask = 0
    // The transport has one byte-aware pacer; do not stack a 16 ms note timer
    // on top of GATT and UART delays.
    private val realtime = RealtimeNotes(intervalMs = 0)
    private val writePacer = BleWritePacer()
    private var transportBusy = false
    private var transportType: Int? = null
    private var transportGeneration = 0
    private var realtimePumpGeneration = 0
    private var scoreTransfer: ScoreTransfer? = null
    private var omrTransfer:OmrTransfer?=null
    private var omrCallback:((Result<OmrResult>)->Unit)?=null
    private var glyphId=0
    private var omrQuietUntil=0L
    fun inferBitmap(bitmap:ByteArray,callback:(Result<OmrResult>)->Unit){handler.post{
        if(!view.connected || omrTransfer!=null || scoreTransfer!=null){callback(Result.failure(IllegalStateException("请先连接设备并等待其他传输完成")));return@post}
        glyphId=glyphId%65535+1
        try{omrTransfer=OmrTransfer(glyphId,bitmap);omrCallback=callback;omrTransfer?.next()?.let{commandBytes(it.type,it.payload)}}
        catch(e:Exception){callback(Result.failure(e))}
    }}
    private fun failOmr(message:String){val callback=omrCallback;omrTransfer=null;omrCallback=null;commands.removeOmrTransfers();callback?.invoke(Result.failure(IllegalStateException(message)))}
    fun cancelOmr(){handler.post{
        val id=omrTransfer?.id ?: return@post
        if(inflightType in Protocol.OMR_BEGIN..Protocol.OMR_ABORT){inflightSequence=null;inflightType=null;inflightFrame=null}
        failOmr("已取消识谱")
        commands.offer(QueuedCommand(Protocol.OMR_ABORT,byteArrayOf(id.toByte(),(id shr 8).toByte())))
        omrQuietUntil=SystemClock.uptimeMillis()+100
        handler.postDelayed({dispatchNext()},100)
    }}
    var view = BleView()
        private set

    private fun publish(newView: BleView) { if(newView==view)return; view = newView; onChange(newView) }
    private fun status(text: String) = publish(view.copy(message = text))
    private val serviceId = UUID.fromString("0000ffe0-0000-1000-8000-00805f9b34fb")
    private val dataId = UUID.fromString("0000ffe1-0000-1000-8000-00805f9b34fb")
    private val cccdId = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            handler.post {
                if(!scanActive || view.connected)return@post
                val address = result.device.address
                val name = result.scanRecord?.deviceName ?: result.device.name ?: "未命名 BLE"
                val previous = view.devices.firstOrNull { it.address == address }
                if (previous == null)
                    publish(view.copy(devices = orderedDevices(view.devices + FoundDevice(name, address))))
                else if (name != "未命名 BLE" && previous.name != name)
                    publish(view.copy(devices = orderedDevices(view.devices.map {
                        if (it.address == address) FoundDevice(name, address) else it
                    })))
            }
        }
        override fun onScanFailed(errorCode: Int) {
            handler.post { scanActive = false; status("扫描失败：$errorCode") }
        }
    }

    fun scan() {
        if (adapter?.isEnabled != true) { status("请先打开手机蓝牙"); return }
        stopScan()
        scanner = adapter?.bluetoothLeScanner
        val currentScanner = scanner ?: return status("蓝牙扫描器不可用，请重新打开蓝牙")
        publish(view.copy(devices = emptyList(), message = "扫描中…"))
        try {
            currentScanner.startScan(scanCallback)
            scanActive = true
            val generation = ++scanGeneration
            handler.postDelayed({
                if (generation == scanGeneration && scanActive) {
                    stopScan()
                    status("扫描结束，请选择设备")
                }
            }, 10000)
        } catch (_: SecurityException) { status("缺少蓝牙扫描权限") }
    }

    fun stopScan() {
        scanGeneration++
        if (scanActive) try { scanner?.stopScan(scanCallback) } catch (_: SecurityException) { }
        scanActive = false
    }

    fun connect(address: String) {
        stopScan()
        disconnect()
        try {
            val device = adapter?.getRemoteDevice(address) ?: return status("蓝牙不可用")
            status("正在连接 ${device.name ?: address}…")
            val opened = device.connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE)
                ?: return status("蓝牙连接未启动")
            gatt = opened
            val generation = ++connectGeneration
            handler.postDelayed({
                if (generation == connectGeneration && gatt === opened && !view.connected) {
                    disconnect()
                    status("蓝牙连接超时，请重试")
                }
            }, 12000)
        } catch (_: SecurityException) { status("缺少蓝牙连接权限") }
    }

    fun disconnect() {
        failOmr("蓝牙已断开，识谱已停止")
        scoreTransfer = null
        stopScan()
        connectGeneration++
        pollGeneration++
        heartbeatGeneration++
        telemetryGeneration++
        if (heldPadMask != 0 && inflightSequence == null && !transportBusy &&
            writePacer.delayMs(SystemClock.uptimeMillis()) == 0L) {
            val characteristic = channel
            val currentGatt = gatt
            if (characteristic != null && currentGatt != null) {
                val next = (sequence + 1) and 0xff
                write(currentGatt, characteristic,
                    Protocol.encodeCommand(Protocol.ALL_NOTES_OFF, next),
                    BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)
            }
        }
        heldPadMask = 0
        realtime.clear(); writePacer.reset(); realtimePumpGeneration++
        transportBusy = false; transportType = null; transportGeneration++
        commands.clear()
        gatt?.disconnect()
        gatt?.close()
        gatt = null
        channel = null
        inflightSequence = null
        inflightType = null
        inflightFrame = null
        failTool("蓝牙连接已中断，重新连接后可重读设备录音")
        stream.reset()
        expectedScene = null
        publish(view.copy(connected = false, state = null, telemetry = null,
            pending = false, message = "已断开", scoreSupported = null, uploadedScore = null,
            uploadProgress = null, scoreMessage = "连接设备后可重新上传",captureSupported=null,pitchLayout=null,layoutSupported=null))
    }

    fun command(type: Int, value: Int? = null) {
        if(type==Protocol.SCORE_ACTION && value==0)captureUpdates.offer(CaptureDisplay())
        commandBytes(type,value?.let { byteArrayOf(it.toByte()) } ?: byteArrayOf())
    }

    fun uploadScore(events: List<ScoreEvent>, timbre: Int,key:Int?=null) {
        if (!view.connected || view.pitchLayout==null || view.scoreSupported != true || view.state?.writeAllowed != true)
            return status("请连接支持录音旋律的设备固件")
        if (scoreTransfer != null || omrTransfer!=null) return
        if (view.uploadedScore?.let { (it.playing || it.guiding) && !it.finished } == true)
            return publish(view.copy(scoreMessage = "请先停止当前旋律"))
        releaseAllNotes()
        val token = ((SystemClock.elapsedRealtime() % 65535) + 1).toInt()
        try { scoreTransfer = ScoreTransfer(events,timbre,token,key?:PitchLayout.estimateKey(events)) }
        catch (e: Exception) { return publish(view.copy(scoreMessage = e.message ?: "曲谱无效")) }
        publish(view.copy(uploadProgress = 0, scoreMessage = "准备传入旋律…"))
        scoreTransfer?.next()?.let { commandBytes(it.type,it.payload) }
    }

    fun cancelScoreUpload() {
        val token = scoreTransfer?.token ?: return
        scoreTransfer = null; commands.removeScoreTransfers()
        publish(view.copy(uploadProgress = null, scoreMessage = "已取消后续传输，正在查询设备旋律"))
        commandBytes(Protocol.SCORE_ABORT,byteArrayOf(token.toByte(),(token ushr 8).toByte()))
    }

    private fun failScore(message: String) {
        val token = scoreTransfer?.token
        scoreTransfer = null; commands.removeScoreTransfers()
        publish(view.copy(uploadProgress = null, scoreMessage = message))
        if (token != null && view.connected) commandBytes(Protocol.SCORE_ABORT,
            byteArrayOf(token.toByte(),(token ushr 8).toByte()))
    }

    fun noteOn(pad: Int, velocity: Int = 176) {
        if (pad !in 0..6 || !view.connected || view.state?.writeAllowed != true ||
            view.state?.vibratoDepth == null || view.pitchLayout==null) return
        val bit = 1 shl pad
        if (heldPadMask and bit != 0) return
        writePacer.touched(SystemClock.uptimeMillis())
        heldPadMask = heldPadMask or bit
        if (view.state?.realtimeNotes == true) {
            realtime.down(pad, velocity); dispatchNext()
        } else commandBytes(Protocol.NOTE_ON, byteArrayOf(pad.toByte(), velocity.coerceIn(1, 255).toByte()))
    }

    fun exactNote(index:Int,down:Boolean,velocity:Int=176) {
        if(index !in 0..71 || !view.connected || view.pitchLayout==null || view.state?.writeAllowed!=true)return
        writePacer.touched(SystemClock.uptimeMillis())
        if(down)realtime.downAbsolute(index,velocity) else realtime.upAbsolute(index)
        heldPadMask=realtime.held;dispatchNext()
    }

    fun noteOff(pad: Int) {
        if (pad !in 0..6) return
        writePacer.touched(SystemClock.uptimeMillis())
        heldPadMask = heldPadMask and (1 shl pad).inv()
        if (view.connected && view.state?.realtimeNotes == true) {
            realtime.up(pad); heldPadMask=realtime.held; dispatchNext()
        } else if (view.connected) commandBytes(Protocol.NOTE_OFF, byteArrayOf(pad.toByte()))
    }

    fun releaseAllNotes() {
        val hadNotes = heldPadMask != 0
        if(hadNotes)writePacer.touched(SystemClock.uptimeMillis())
        heldPadMask = 0
        if (view.connected && view.state?.realtimeNotes == true) {
            realtime.release(); dispatchNext()
        } else if (hadNotes && view.connected) commandBytes(Protocol.ALL_NOTES_OFF)
    }

    fun setPerformanceVisible(visible: Boolean) {
        performanceVisible = visible
        requestPlayingPriority()
        if (!visible) releaseAllNotes()
    }

    private fun requestPlayingPriority() {
        try {
            gatt?.requestConnectionPriority(if(performanceVisible || toolsVisible)
                BluetoothGatt.CONNECTION_PRIORITY_HIGH else BluetoothGatt.CONNECTION_PRIORITY_BALANCED)
        } catch (_: SecurityException) { /* Runtime permission is owned by Activity. */ }
    }

    fun releaseBend() {
        if (view.connected && view.state?.bend != null)
            commandBytes(Protocol.RELEASE_BEND)
    }

    fun applyScene(scene: InstrumentScene) {
        if (view.state?.vibratoDepth == null || view.pitchLayout==null) return status("设备固件暂不支持场景")
        if (!view.connected || view.state?.writeAllowed != true)
            return status("请先连接蓝牙并等待 FPGA 状态回传")
        expectedScene = scene
        command(Protocol.SET_KEY,scene.key)
        commandBytes(Protocol.SET_SCENE, scene.payload())
    }

    fun commandBytes(type: Int, payload: ByteArray = byteArrayOf(), background: Boolean = false) {
        if((type in Protocol.SET_VOLUME..Protocol.REALTIME_ABSOLUTE || type==Protocol.SET_KEY ||
            Protocol.isScoreTransfer(type) || type==Protocol.SCORE_ACTION) &&
            type!=Protocol.ALL_NOTES_OFF && type!=Protocol.HEARTBEAT && view.pitchLayout==null)
            return status("请先升级为配套的七自然音固件")
        if(type==Protocol.SET_BANK || type==Protocol.SET_KEY || type==Protocol.SET_SCENE || type==Protocol.SET_TIMBRE)releaseAllNotes()
        if (type == Protocol.ALL_NOTES_OFF) {
            heldPadMask = 0; realtime.release()
        }
        try { Protocol.encodeCommand(type, 0, payload) }
        catch (_: IllegalArgumentException) { status("命令参数无效"); return }
        if (!view.connected || channel == null) return status("尚未建立数据通道")
        commands.offer(QueuedCommand(type, payload.clone(), background))
        dispatchNext()
    }

    private fun dispatchNext() {
        val characteristic = channel ?: return status("尚未建立数据通道")
        val currentGatt = gatt ?: return
        if (transportBusy) return
        val now = SystemClock.uptimeMillis()
        val wireDelay = writePacer.delayMs(now)
        if(wireDelay > 0) { scheduleRealtimePump(wireDelay); return }
        val bankTransaction = inflightType == Protocol.SET_BANK || inflightType == Protocol.SET_SCENE ||
            commands.contains(Protocol.SET_BANK) || commands.contains(Protocol.SET_SCENE) ||
            inflightType==Protocol.SET_KEY || commands.contains(Protocol.SET_KEY)
        if (view.pitchLayout!=null && view.state?.realtimeNotes == true && (!bankTransaction || realtime.held == 0)) {
            val packet = realtime.peek(now)
            if (packet != null) {
                val next = (sequence + 1) and 0xff
                val kind = if (characteristic.properties and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE != 0)
                    BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE else BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                if (write(currentGatt, characteristic, Protocol.encodeCommand(packet.type, next, packet.payload()), kind)) {
                    sequence = next; realtime.sent(packet, now)
                    beginTransport(packet.type)
                    if (packet.attacks != 0 && view.uploadedScore?.guiding == true)
                        commands.offer(QueuedCommand(Protocol.SCORE_STATUS, byteArrayOf()))
                    // An already in-flight poll may contain the target from
                    // before this strike. Keep one fresh follow-up, coalesced.
                    if (packet.attacks != 0 && view.state?.guideUiState == 2)
                        commands.offer(QueuedCommand(Protocol.GET_STATE, byteArrayOf()))
                } else scheduleRealtimePump(4)
                return
            }
            realtime.delayMs(now)?.let { scheduleRealtimePump(it) }
        }
        if (inflightSequence != null) return
        if(SystemClock.uptimeMillis()<omrQuietUntil)return
        val backgroundDelay = writePacer.backgroundDelayMs(now, heldPadMask != 0)
        val command = commands.take(allowBackground = backgroundDelay == 0L) ?: run {
            if(!commands.isEmpty() && backgroundDelay > 0) scheduleRealtimePump(backgroundDelay)
            return
        }
        val next = (sequence + 1) and 0xff
        val bytes = Protocol.encodeCommand(command.type, next, command.payload)
        val props = characteristic.properties
        val writeType = when {
            props and BluetoothGattCharacteristic.PROPERTY_WRITE != 0 -> BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
            props and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE != 0 -> BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
            else -> {if(toolOwner.owns(command))failTool("设备通道不支持写入");return status("FFE1 不支持写入")}
        }
        val started = write(currentGatt, characteristic, bytes, writeType)
        if (started) {
            beginTransport(command.type)
            sequence = next
            toolOwner.started(command,next)
            inflightSequence = next
            inflightType = command.type
            inflightFrame = bytes
            inflightWriteType = writeType
            inflightAttempt = 0
            // Background reads must not toggle connection banners or disable controls.
            val setting = !command.background && !ToolWire.contains(command.type) && command.type in Protocol.SET_VOLUME..Protocol.SET_SCENE && command.type !in listOf(Protocol.NOTE_ON,Protocol.NOTE_OFF,Protocol.NOTE_LEASE,Protocol.HEARTBEAT)
            if(setting)publish(view.copy(pending=true))
            scheduleConfirmationTimeout(next, 0, if (command.type == Protocol.NOTE_ON ||
                command.type == Protocol.NOTE_OFF || command.type == Protocol.NOTE_LEASE) 150
                else if(command.type==Protocol.CAPTURE_STATUS || command.type==Protocol.CAPTURE_DISPLAY)700 else 2500)
        } else {
            if(toolOwner.owns(command))failTool("蓝牙写入未启动，请重试") else commands.offer(command)
            status("蓝牙写入未启动")
        }
    }

    private fun scheduleRealtimePump(delay: Long) {
        val generation = ++realtimePumpGeneration
        handler.postDelayed({ if (generation == realtimePumpGeneration && view.connected) dispatchNext() }, delay.coerceAtLeast(1))
    }

    private fun beginTransport(type: Int) {
        transportBusy = true; transportType = type
        val generation = ++transportGeneration
        // Do not start an overlapping GATT write after a lost callback: a late
        // callback has no request ID and could otherwise complete the wrong
        // frame. Closing the session also lets the FPGA note lease expire.
        handler.postDelayed({
            if (generation == transportGeneration && transportBusy) {
                disconnect()
                status("蓝牙写入超时，已断开，请重新连接")
            }
        }, 1000)
    }

    private fun write(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic,
                      bytes: ByteArray, writeType: Int): Boolean = try {
        val started = if (Build.VERSION.SDK_INT >= 33)
            gatt.writeCharacteristic(characteristic, bytes, writeType) == BluetoothStatusCodes.SUCCESS
        else {
            @Suppress("DEPRECATION")
            characteristic.value = bytes
            characteristic.writeType = writeType
            @Suppress("DEPRECATION")
            gatt.writeCharacteristic(characteristic)
        }
        if(started)writePacer.started(bytes.size,SystemClock.uptimeMillis())
        started
    } catch (_: SecurityException) { false }

    private fun scheduleConfirmationTimeout(requestSequence: Int, attempt: Int, delayMs: Long = 2500) {
        handler.postDelayed({
            if (inflightSequence != requestSequence || inflightAttempt != attempt) return@postDelayed
            if (transportBusy) {
                scheduleConfirmationTimeout(requestSequence, attempt, 50); return@postDelayed
            }
            val wireDelay=writePacer.delayMs(SystemClock.uptimeMillis())
            if(wireDelay>0){scheduleConfirmationTimeout(requestSequence,attempt,wireDelay);return@postDelayed}
            if(inflightType==Protocol.CAPTURE_STATUS || inflightType==Protocol.CAPTURE_DISPLAY) {
                inflightSequence=null;inflightType=null;inflightFrame=null;commands.removeCaptureDisplays()
                publish(view.copy(pending=false,captureSupported=false));dispatchNext();return@postDelayed
            }
            if(inflightType in Protocol.OMR_BEGIN..Protocol.OMR_ABORT){
                inflightSequence=null;inflightType=null;inflightFrame=null
                failOmr("FPGA识谱回复超时，数据没有重发或改用云端");dispatchNext();return@postDelayed
            }
            val currentGatt = gatt
            val characteristic = channel
            val bytes = inflightFrame
            val transient = inflightType == Protocol.NOTE_ON || inflightType == Protocol.NOTE_OFF ||
                inflightType == Protocol.NOTE_LEASE
            if (!transient && attempt == 0 && currentGatt != null && characteristic != null && bytes != null &&
                write(currentGatt, characteristic, bytes, inflightWriteType)) {
                // SET operations are absolute, so retrying the same frame and sequence is safe.
                inflightAttempt = 1
                beginTransport(inflightType ?: 0)
                status("FPGA 暂未确认，正在重试一次…")
                scheduleConfirmationTimeout(requestSequence, 1)
            } else {
                val failedType = inflightType
                if (inflightType == Protocol.SET_SCENE) expectedScene = null
                inflightSequence = null
                inflightType = null
                inflightFrame = null
                publish(view.copy(pending = false, message = "FPGA 未确认，请检查串口/供电"))
                if(ToolWire.contains(failedType) && toolOwner.matches(requestSequence))failTool("设备工具回复中断，请重试；已冻结的录音仍保留在设备")
                if (Protocol.isScoreTransfer(failedType))
                    failScore("传谱结果尚未确认，请等待状态回传或重新上传")
                dispatchNext()
            }
        }, delayMs)
    }

    private val callback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, statusCode: Int, newState: Int) {
            handler.post {
                if (this@BleController.gatt !== gatt) return@post
                if (statusCode == BluetoothGatt.GATT_SUCCESS && newState == BluetoothProfile.STATE_CONNECTED) {
                    writePacer.reset()
                    requestPlayingPriority()
                    status("已连接，发现服务中…")
                    try { gatt.discoverServices() } catch (_: SecurityException) { status("缺少连接权限") }
                } else {
                    channel = null
                    inflightSequence = null
                    inflightType = null
                    inflightFrame = null
                    heldPadMask = 0
                    realtime.clear(); writePacer.reset(); realtimePumpGeneration++
                    transportBusy = false; transportType = null; transportGeneration++
                    commands.clear()
                    failOmr("蓝牙已断开，识谱已停止")
                    scoreTransfer = null
                    failTool("蓝牙连接已中断，重新连接后可重读设备录音")
        stream.reset()
                    expectedScene = null
                    publish(view.copy(connected = false, pending = false, state = null,
                        telemetry = null, message = "连接已断开 ($statusCode)",scoreSupported = null,
                        uploadedScore = null,uploadProgress = null, scoreMessage = "已断开；传输未完成时原旋律保留",captureSupported=null,pitchLayout=null,layoutSupported=null))
                    gatt.close()
                    if (this@BleController.gatt === gatt) this@BleController.gatt = null
                }
            }
        }
        override fun onServicesDiscovered(gatt: BluetoothGatt, statusCode: Int) {
            handler.post {
                if (this@BleController.gatt !== gatt) return@post
                if (statusCode != BluetoothGatt.GATT_SUCCESS) return@post status("发现服务失败：$statusCode")
                val characteristic = gatt.getService(serviceId)?.getCharacteristic(dataId)
                    ?: return@post status("没有找到 FFE0/FFE1；请核实模块实物")
                val cccdValue = when {
                    characteristic.properties and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0 ->
                        BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                    characteristic.properties and BluetoothGattCharacteristic.PROPERTY_INDICATE != 0 ->
                        BluetoothGattDescriptor.ENABLE_INDICATION_VALUE
                    else -> return@post status("FFE1 不支持通知或指示，无法取得 FPGA 确认")
                }
                channel = characteristic
                val cccd = characteristic.getDescriptor(cccdId)
                    ?: return@post status("FFE1 缺少通知描述符")
                try {
                    if (!gatt.setCharacteristicNotification(characteristic, true))
                        return@post status("启用本地通知失败")
                    val ok = if (Build.VERSION.SDK_INT >= 33)
                        gatt.writeDescriptor(cccd, cccdValue) == BluetoothStatusCodes.SUCCESS
                    else {
                        @Suppress("DEPRECATION")
                        cccd.value = cccdValue
                        @Suppress("DEPRECATION")
                        gatt.writeDescriptor(cccd)
                    }
                    if (!ok) status("启用设备通知失败")
                } catch (_: SecurityException) { status("缺少连接权限") }
            }
        }
        override fun onDescriptorWrite(gatt: BluetoothGatt, descriptor: BluetoothGattDescriptor, statusCode: Int) {
            handler.post {
                if (this@BleController.gatt !== gatt) return@post
                if (statusCode != BluetoothGatt.GATT_SUCCESS) return@post status("通知订阅失败：$statusCode")
                publish(view.copy(connected = true, devices=emptyList(), message = "数据通道就绪，读取状态中…"))
                command(Protocol.GET_LAYOUT)
                command(Protocol.GET_STATE)
                command(Protocol.SCORE_STATUS)
                captureUpdates.reset()
                command(Protocol.CAPTURE_STATUS)
                scheduleCaptureDisplay(++captureLoop)
                schedulePoll(++pollGeneration)
                scheduleHeartbeat(++heartbeatGeneration)
                scheduleTelemetry(++telemetryGeneration)
            }
        }
        override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray) {
            handler.post { if (this@BleController.gatt === gatt) accept(value) }
        }
        @Deprecated("Android 13 uses the value-bearing callback")
        override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
            if (Build.VERSION.SDK_INT < 33) {
                @Suppress("DEPRECATION") val bytes = characteristic.value?.clone() ?: return
                handler.post { if (this@BleController.gatt === gatt) accept(bytes) }
            }
        }
        override fun onCharacteristicWrite(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, statusCode: Int) {
            handler.post {
                if (this@BleController.gatt !== gatt) return@post
                val wasRealtime = transportType == Protocol.REALTIME_NOTES || transportType==Protocol.REALTIME_ABSOLUTE
                writePacer.completed(SystemClock.uptimeMillis())
                transportBusy = false; transportType = null; transportGeneration++
                if (wasRealtime && statusCode != BluetoothGatt.GATT_SUCCESS) {
                    // Retry only the current fingers, never the failed old tap.
                    realtime.refresh(); scheduleRealtimePump(4)
                    return@post
                }
                if (!wasRealtime && inflightSequence != null &&
                    statusCode != BluetoothGatt.GATT_SUCCESS) {
                    val failedSequence=inflightSequence
                    val failedType = inflightType
                    if (inflightType == Protocol.SET_SCENE) expectedScene = null
                    inflightSequence = null
                    inflightType = null
                    inflightFrame = null
                    publish(view.copy(pending = false, message = "GATT 写入失败：$statusCode"))
                    if (failedType in Protocol.OMR_BEGIN..Protocol.OMR_ABORT)failOmr("蓝牙识谱写入失败")
                    if(ToolWire.contains(failedType) && toolOwner.matches(failedSequence))failTool("设备工具回复中断，请重试；已冻结的录音仍保留在设备")
                    if (Protocol.isScoreTransfer(failedType)) {
                        failScore("蓝牙传输失败，请等待状态回传后重试")
                    }
                    dispatchNext()
                } else dispatchNext()
            }
        }
    }

    private fun accept(bytes: ByteArray) {
        stream.push(bytes).forEach { frame ->
            if (frame.sequence != inflightSequence) return@forEach
            val requestType = inflightType
            inflightSequence = null
            inflightType = null
            inflightFrame = null
            if(ToolWire.contains(requestType)){
                val done=if(toolOwner.matches(frame.sequence))toolCallback else null
                if(done!=null){toolCallback=null;toolOwner.clear()};publish(view.copy(pending=false))
                done?.invoke(runCatching{ToolWire.checked(frame,requestType!!)});dispatchNext();return@forEach
            }
            if(requestType in Protocol.OMR_BEGIN..Protocol.OMR_ABORT){
                val transfer=omrTransfer
                if(transfer!=null)try{
                    transfer.acknowledge(frame)
                    val result=transfer.result
                    if(result!=null){val done=omrCallback;omrTransfer=null;omrCallback=null;publish(view.copy(pending=false))
                        if(view.captureSupported==true)captureUpdates.take(SystemClock.uptimeMillis())?.let{commandBytes(Protocol.CAPTURE_DISPLAY,it.payload())}
                        done?.invoke(Result.success(result))}
                    else transfer.next()?.let{commandBytes(it.type,it.payload)}
                }catch(e:Exception){failOmr(e.message?:"FPGA识谱回复无效")}
                dispatchNext();return@forEach
            }
            when (frame.type) {
                Protocol.LAYOUT_STATE -> {
                    val layout=PitchLayoutState.from(frame.payload)
                    publish(view.copy(pitchLayout=layout,layoutSupported=layout!=null,pending=false,
                        message=if(layout!=null)"已连接 · 七自然音 / 完整半音" else "音高版本不匹配，请升级配套固件"))
                    if(layout!=null)view.uploadedScore?.let { score ->
                        if(score.schema==2 && score.noteIndex!=null)publish(view.copy(uploadedScore=score.copy(bank=PitchLayout.bank(score.noteIndex,layout.key))))
                    }
                }
                Protocol.CAPTURE_STATE -> {
                    val b=frame.payload
                    val valid=b.size==14 && b[0].toInt()==1 && b[11].toInt()==1
                    publish(view.copy(captureSupported=valid,pending=false))
                }
                Protocol.SCORE_STATE -> {
                    val parsed = UploadedScoreState.from(frame.payload)
                    val state=parsed?.let{if(it.noteIndex!=null)it.copy(bank=PitchLayout.bank(it.noteIndex,view.pitchLayout?.key?:0)) else it}
                    if (state == null) failScore("设备旋律状态无效，请重试")
                    else {
                        publish(view.copy(scoreSupported = true,uploadedScore = state,pending = false))
                        val transfer = scoreTransfer
                        if (Protocol.isScoreTransfer(requestType) && transfer != null) {
                            try {
                                transfer.acknowledge(requestType!!,state)
                                if (transfer.done) {
                                    scoreTransfer = null
                                    publish(view.copy(uploadProgress = null,scoreMessage = "旋律已传入 · 可断开手机演奏，设备断电后需重传"))
                                } else {
                                    publish(view.copy(uploadProgress = transfer.confirmed * 100 / transfer.count,
                                        scoreMessage = "正在传入 ${transfer.confirmed} / ${transfer.count} 个事件"))
                                    transfer.next()?.let { commandBytes(it.type,it.payload) }
                                }
                            } catch (_: Exception) { failScore("传谱校验失败（${state.error}），请重新上传") }
                        } else if (state.error != 0) publish(view.copy(scoreMessage = when (state.error) {
                            2 -> "请先停止播放或指引，再上传"; 6 -> "设备中还没有旋律，请先上传"
                            7 -> "传谱已超时，请重新上传"; else -> "设备未接受操作（${state.error}）"
                        }))
                    }
                }
                Protocol.STATE -> {
                    val state = DeviceState.from(frame.payload)
                    if (state == null) publish(view.copy(pending = false,
                        message = "FPGA 状态帧无效 (${frame.payload.size}字节): " +
                            frame.payload.joinToString(" ") { "%02X".format(it.toInt() and 0xff) }))
                    else {
                        val scene = expectedScene
                        val message = if (requestType == Protocol.SET_SCENE && scene != null) {
                            expectedScene = null
                            if (scene.matches(state)) "场景已在设备生效：${scene.name}"
                            else "场景未完全生效，请检查设备状态"
                        } else if(view.layoutSupported==false)"设备需要升级七自然音固件" else "已连接 · FPGA 已确认"
                        val enteredPerformance = view.state?.isPerformanceActive != true && state.isPerformanceActive
                        publish(view.copy(state = state, pending = false, message = message))
                        if (enteredPerformance) schedulePoll(++pollGeneration)
                        // NOTE_ON's ACK can precede the FPGA guide-step update.
                        // Read again promptly so the next target appears at once.
                        if (requestType == Protocol.NOTE_ON && state.guideUiState == 2)
                            command(Protocol.GET_STATE)
                    }
                }
                Protocol.TELEMETRY -> {
                    val reading = DeviceTelemetry.from(frame.payload)
                    if (reading != null) publish(view.copy(telemetry = reading,
                        state = view.state?.copy(padMask = reading.padMask), pending = false))
                    else publish(view.copy(pending = false, message = "力度帧无效"))
                }
                Protocol.ERROR -> {
                    val code = frame.payload.firstOrNull()?.toInt()?.and(0xff) ?: -1
                    if(requestType==Protocol.GET_LAYOUT || requestType==Protocol.SET_KEY){
                        publish(view.copy(pending=false,pitchLayout=null,layoutSupported=false,
                            message="设备仍是旧版音高编码，请安装配套七自然音固件"))
                        dispatchNext();return@forEach
                    }
                    if(requestType==Protocol.CAPTURE_STATUS || requestType==Protocol.CAPTURE_DISPLAY) {
                        commands.removeCaptureDisplays()
                        publish(view.copy(pending=false,captureSupported=false))
                        dispatchNext();return@forEach
                    }
                    if (requestType == Protocol.SCORE_STATUS && code == 2) {
                        publish(view.copy(pending = false,scoreSupported = false,
                            scoreMessage = "录音与试听可用；传入设备需要识谱固件"))
                        dispatchNext(); return@forEach
                    }
                    if (Protocol.isScoreTransfer(requestType))
                        failScore("设备拒绝传谱（$code），原旋律保留")
                    if (requestType == Protocol.SET_SCENE) expectedScene = null
                    if (code == 4) { heldPadMask = 0; commands.clear() }
                    publish(view.copy(pending = false,
                        state = if (code == 4) view.state?.copy(writeAllowed = false) else view.state,
                        message = if (code == 4) "设备连接会话已失效，请重新连接" else "设备拒绝命令：$code"))
                }
                else -> publish(view.copy(pending = false, message = "收到未知 FPGA 响应：${frame.type}"))
            }
            dispatchNext()
        }
    }

    private fun schedulePoll(generation: Int) {
        handler.postDelayed({
            if (view.connected && generation == pollGeneration) {
                if (commands.isEmpty() && scoreTransfer == null && omrTransfer==null && !toolsVisible && toolCallback==null && writePacer.backgroundDelayMs(SystemClock.uptimeMillis(),heldPadMask!=0)==0L) {
                    commandBytes(Protocol.GET_STATE,background=true)
                    if (view.scoreSupported == true) commandBytes(Protocol.SCORE_STATUS,background=true)
                    if(view.pitchLayout==null && view.layoutSupported!=false)commandBytes(Protocol.GET_LAYOUT,background=true)
                }
                schedulePoll(generation)
            }
        }, if (view.state?.isPerformanceActive == true || view.uploadedScore?.let { (it.playing || it.guiding) && !it.finished } == true) 350 else 1200)
    }

    private fun scheduleHeartbeat(generation: Int) {
        handler.postDelayed({
            if (view.connected && generation == heartbeatGeneration) {
                if (scoreTransfer == null && omrTransfer==null && view.state?.writeAllowed == true && view.state?.vibratoDepth != null) {
                    if (heldPadMask != 0 && view.state?.realtimeNotes == true) {
                        realtime.refresh(); dispatchNext()
                    } else {
                        if (heldPadMask != 0)commandBytes(Protocol.NOTE_LEASE, byteArrayOf(heldPadMask.toByte()))
                        commandBytes(Protocol.HEARTBEAT)
                    }
                }
                scheduleHeartbeat(generation)
            }
        }, 500)
    }

    private fun scheduleTelemetry(generation: Int) {
        handler.postDelayed({
            if (view.connected && generation == telemetryGeneration) {
                if (scoreTransfer == null && omrTransfer==null && performanceVisible && !toolsVisible && view.state?.vibratoDepth != null &&
                    commands.isEmpty() && toolCallback==null && writePacer.backgroundDelayMs(SystemClock.uptimeMillis(),heldPadMask!=0)==0L) commandBytes(Protocol.GET_TELEMETRY,background=true)
                scheduleTelemetry(generation)
            }
        }, 160)
    }
}
