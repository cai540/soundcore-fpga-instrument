package cn.soundcore.instrument

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.enableEdgeToEdge
import androidx.activity.SystemBarStyle
import androidx.core.content.FileProvider
import androidx.core.content.edit
import android.net.Uri
import java.io.File
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    private var currentView by mutableStateOf(BleView())
    private var savedScene by mutableStateOf<InstrumentScene?>(null)
    private lateinit var ble: BleController
    private lateinit var melody: MelodyAudio
    private lateinit var sheetMelody:MelodyAudio
    private lateinit var sheetCapture:SheetCapture
    private lateinit var tools:ProductToolsController
    private lateinit var library:OnlineScores
    private lateinit var libraryPlayer:MelodyAudio
    private var toolsView by mutableStateOf(ProductToolsView())
    private var libraryView by mutableStateOf(ScoreLibraryView())
    private var libraryMelodyView by mutableStateOf(MelodyView())
    private var requestedTab by mutableStateOf(0)
    private var toolsOpen by mutableStateOf(false)
    private var onlineOpen by mutableStateOf(false)
    private var libraryLoaded by mutableStateOf(false)
    private var librarySection by mutableStateOf(0)
    private val scorePicker=registerForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null)library.import(uri)}
    private var melodyView by mutableStateOf(MelodyView())
    private var sheetMelodyView by mutableStateOf(MelodyView())
    private var sheetView by mutableStateOf(SheetView())
    private var sheetMode by mutableStateOf(false)
    private var microphoneForTools=false
    private val microphoneRequest = registerForActivityResult(ActivityResultContracts.RequestPermission()) {
        if(microphoneForTools){if(it && toolsOpen)tools.microphone(true)else if(toolsOpen)tools.microphoneDenied();microphoneForTools=false}
        else if (it) melody.record()
        else melodyView = melodyView.copy(message = "麦克风权限未授予，仍可选择音频")
    }
    private val audioPicker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) melody.import(uri)
    }
    private val sheetPicker=registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()){uris->if(uris.isNotEmpty())sheetCapture.import(uris)}
    private var cameraUri:Uri?=null
    private val cameraPicker=registerForActivityResult(ActivityResultContracts.TakePicture()){ok->
        if(ok)cameraUri?.let{sheetCapture.import(listOf(it))}
    }
    private var creationWorkspaceActive=false
    private var activeTab = 0
    private var afterPermission: (() -> Unit)? = null
    private val permissionRequest = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        if (grants.values.all { it }) afterPermission?.invoke()
        else currentView = currentView.copy(message = "蓝牙权限未授予")
        afterPermission = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(statusBarStyle=SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),navigationBarStyle=SystemBarStyle.dark(android.graphics.Color.TRANSPARENT))
        cameraUri=if(Build.VERSION.SDK_INT>=33)savedInstanceState?.getParcelable("cameraUri",Uri::class.java) else @Suppress("DEPRECATION") savedInstanceState?.getParcelable("cameraUri")
        ble = BleController(this) { currentView = it }
        tools=ProductToolsController(this,ble){toolsView=it}
        library=OnlineScores(this){libraryView=it}
        intent.data?.let{if(library.receiveLink(it)){requestedTab=1;librarySection=1}}
        libraryPlayer=MelodyAudio(this,"library_"){libraryMelodyView=it}
        melody = MelodyAudio(this) { melodyView = it; syncCaptureDisplay() }
        sheetMelody=MelodyAudio(this,"sheet_"){sheetMelodyView=it;syncCaptureDisplay()}
        sheetCapture=SheetCapture(this,ble){sheetView=it;syncCaptureDisplay()}
        savedScene = InstrumentScene.fromStored("我的场景",
            getSharedPreferences("soundcore_scenes", MODE_PRIVATE).getString("custom", null))
        setContent {
            SoundcoreTheme {
                StudioScreen(currentView,
                    deviceContent={
                        if(toolsOpen)ProductToolsPanel(toolsView,currentView.connected,tools,onMicrophone={enabled->
                            if(enabled){microphoneForTools=true;microphoneRequest.launch(Manifest.permission.RECORD_AUDIO)}
                            else tools.microphone(false)
                        }){toolsOpen=false}
                        else {
                            DevicePage(currentView,{withBluetoothPermission{ble.scan()}},{address->withBluetoothPermission{ble.connect(address)}},{ble.disconnect()},{t,v->ble.command(t,v)},onTools={toolsOpen=true})
                        }
                    },
                    libraryContent={
                        androidx.compose.foundation.layout.Row{
                            androidx.compose.material3.FilterChip(librarySection==0,onClick={libraryPlayer.stopPreview();librarySection=0},label={androidx.compose.material3.Text("机身曲目")})
                            androidx.compose.material3.FilterChip(librarySection==1,onClick={librarySection=1},label={androidx.compose.material3.Text("曲谱书架")})
                        }
                        if(librarySection==0)SongsPage(currentView,currentView.connected && currentView.state?.writeAllowed==true,{t,v->ble.command(t,v)},{p,d,v->if(d)ble.noteOn(p,v)else ble.noteOff(p)})
                        else if(libraryLoaded){
                            androidx.compose.material3.TextButton(onClick={libraryPlayer.stopPreview();libraryLoaded=false}){androidx.compose.material3.Text("‹ 返回曲谱书架")}
                            CreationPlayer(libraryPlayer,libraryMelodyView,true,onBack={libraryPlayer.stopPreview();libraryLoaded=false})
                        }else ScoreLibraryPanel(libraryView,library,onImport={scorePicker.launch(arrayOf("application/json","text/plain","application/octet-stream"))},
                            onBrowse={startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW,Uri.parse("https://soundcore-phone-lab-1030.liuwencai05.chatgpt.site/catalog.html")))},
                            onUse={score,name->if(libraryPlayer.acceptSheet(score,name))libraryLoaded=true})
                    },
                    melodyContent = {
                        val deviceBusy=currentView.uploadProgress!=null || currentView.uploadedScore?.let{(it.playing || it.guiding) && !it.finished}==true
                        CreativeWorkspace(melodyView,sheetView,sheetMelodyView,
                            onMode={melody.stopPreview();sheetMelody.stopPreview();sheetMode=it;syncCaptureDisplay()},
                            onLeave={if(melodyView.recording)melody.finishRecording();melody.stopPreview();sheetMelody.stopPreview();creationWorkspaceActive=false;syncCaptureDisplay()},
                            onWorkspaceActive={creationWorkspaceActive=it;syncCaptureDisplay()},
                            recordContent={CreationPlayer(melody,melodyView,false)},
                            sheetContent={
                                if(sheetView.loaded)CreationPlayer(sheetMelody,sheetMelodyView,true)
                                else SheetPanel(sheetView,currentView.connected,!deviceBusy && !sheetMelodyView.previewing,
                                    onImport={sheetPicker.launch(arrayOf("image/*"))},onRecognize={sheetCapture.recognize(it)},onCancel={sheetCapture.cancel()},
                                    onPage={sheetCapture.setPage(it)},onScoreChange={sheetCapture.changeScore(it)},onBpm={sheetCapture.setBpm(it)},onPart={sheetCapture.setPart(it)},
                                    onUse={sheetCapture.use{score,name->sheetMelody.acceptSheet(score,name)}},onMode={sheetCapture.setMode(it)},
                                    onCamera={
                                        runCatching {
                                            val file=File(cacheDir,"score-camera.jpg")
                                            cameraUri=FileProvider.getUriForFile(this@MainActivity,packageName+".files",file)
                                            cameraPicker.launch(cameraUri!!)
                                        }.onFailure{sheetView=sheetView.copy(message="无法打开相机，可以从相册选择曲谱。")}
                                    })
                            })
                    },
                    onScan = { withBluetoothPermission { ble.scan() } },
                    onConnect = { address -> withBluetoothPermission { ble.connect(address) } },
                    onDisconnect = { ble.disconnect() },
                    onCommand = { type, value -> ble.command(type, value) },
                    onNote = { pad, down, velocity ->
                        if (down) ble.noteOn(pad, velocity) else ble.noteOff(pad)
                    },
                    onAllNotesOff = { ble.releaseAllNotes() },
                    onPitch = { index,down,velocity -> ble.exactNote(index,down,velocity) },
                    onScene = { ble.applyScene(it) },
                    savedScene = savedScene,
                    onSaveScene = {
                        currentView.state?.let { state ->
                            InstrumentScene.fromState("我的场景", state,currentView.pitchLayout?.key?:0)?.let { scene ->
                                savedScene = scene
                                getSharedPreferences("soundcore_scenes", MODE_PRIVATE).edit { putString("custom", scene.storedValue()) }
                            }
                        }
                    },
                    initialTab=requestedTab,
                    onTabChanged = { tab ->
                        requestedTab=tab
                        if(activeTab==2 && tab!=2){if(melodyView.recording)melody.finishRecording();melody.stopPreview();sheetMelody.stopPreview()}
                        if(activeTab==4 && tab!=4){toolsOpen=false;tools.leave()}
                        if(activeTab==1 && tab!=1)libraryPlayer.stopPreview()
                        activeTab = tab
                        syncCaptureDisplay()
                        ble.setPerformanceVisible(tab in 0..2)
                    })
            }
        }
    }

    @androidx.compose.runtime.Composable
    private fun CreationPlayer(player:MelodyAudio,playerView:MelodyView,isSheet:Boolean,onBack:()->Unit={sheetCapture.editSelection()}) {
        MelodyPanel(playerView,currentView,
                            onRecord = { microphoneRequest.launch(Manifest.permission.RECORD_AUDIO) },
                            onFinish = { player.finishRecording() },
                            onImport = { audioPicker.launch(arrayOf("audio/*")) },
                            onPreview = { player.preview() },
                            onTranspose = { player.setTranspose(it) },onTimbre = { player.setTimbre(it) },
                            onUpload = { playerView.score?.let { score ->
                                try { player.save(); ble.uploadScore(score.events(playerView.transpose),playerView.timbre,
                                    score.tonicKey?.let{Math.floorMod(it+playerView.transpose,12)}) }
                                catch (_: Exception) { } } },
                            onCancel = { ble.cancelScoreUpload() },
                            onAction = { ble.command(Protocol.SCORE_ACTION,it) },
                            onNote = { pad,down -> if (down) ble.noteOn(pad,176) else ble.noteOff(pad) },
                            onInputMode = { player.setInputMode(it) },
                            onCancelRecognition = { player.cancelRecognition() },
                            onRecognize = { player.recognize(it) },onRange = { a,b -> player.setRange(a,b) },
                            onSeek = { player.seek(it) },onSelectNote = { player.selectNote(it) },
                            onOriginal = { player.preview(true) },onEdit = { p,d,s -> player.edit(p,d,s) },
                            onUndo = { player.undo() },onSplit = { player.split() },onMerge = { player.merge() },onDelete={player.delete()},
                            capture=!isSheet,onBackToSheet=onBack)
    }

    private fun withBluetoothPermission(action: () -> Unit) {
        val required = if (Build.VERSION.SDK_INT >= 31)
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        val missing = required.filter {
            checkSelfPermission(it) != android.content.pm.PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) action()
        else {
            afterPermission = action
            permissionRequest.launch(missing.toTypedArray())
        }
    }

    private fun syncCaptureDisplay() {
        if(::ble.isInitialized)ble.setCaptureDisplay(if(activeTab==2 && creationWorkspaceActive && sheetMode){
            if(sheetView.busy)CaptureDisplay(stage=3,progress=sheetView.progress)
            else CaptureDisplay.from(sheetMelodyView,sheetView.loaded)
        } else CaptureDisplay.from(melodyView,activeTab==2 && creationWorkspaceActive))
    }

    override fun onNewIntent(intent:android.content.Intent){
        super.onNewIntent(intent);setIntent(intent)
        intent.data?.let{if(::library.isInitialized && library.receiveLink(it)){libraryLoaded=false;librarySection=1;requestedTab=1}}
    }

    override fun onSaveInstanceState(outState:Bundle){outState.putParcelable("cameraUri",cameraUri);super.onSaveInstanceState(outState)}

    override fun onDestroy() {
        if(::tools.isInitialized)tools.close()
        if(::library.isInitialized)library.close()
        if(::libraryPlayer.isInitialized)libraryPlayer.close()
        if (::melody.isInitialized) melody.close()
        if(::sheetMelody.isInitialized)sheetMelody.close()
        if(::sheetCapture.isInitialized)sheetCapture.close()
        ble.disconnect()
        super.onDestroy()
    }

    override fun onStop() {
        if(::tools.isInitialized)tools.leave()
        toolsOpen=false
        if(::libraryPlayer.isInitialized)libraryPlayer.suspendAudio()
        if (::melody.isInitialized) melody.suspendAudio()
        if(::sheetMelody.isInitialized)sheetMelody.suspendAudio()
        if(::sheetCapture.isInitialized)sheetCapture.cancel()
        ble.setCaptureDisplay(CaptureDisplay())
        ble.setPerformanceVisible(false)
        ble.releaseBend()
        super.onStop()
    }

    override fun onStart() {
        super.onStart()
        if (::ble.isInitialized) ble.setPerformanceVisible(activeTab in 0..2)
        syncCaptureDisplay()
    }
}
