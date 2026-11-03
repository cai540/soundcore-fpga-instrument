package cn.soundcore.instrument

import android.annotation.SuppressLint
import android.content.Context
import android.webkit.*
import android.os.Handler
import android.os.Looper
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.File

/** A network-blocked local WebView runs the same geometry/OCR code as the site. */
@SuppressLint("SetJavaScriptEnabled")
class OfflineSheetEngine(private val context:Context,private val ble:BleController) {
    private val main=Handler(Looper.getMainLooper())
    private var loaded=false;private var closed=false;private var generation=0
    private var begin:(()->Unit)?=null
    private var done:((Result<SheetMusic>)->Unit)?=null
    private var progress:((Int,String)->Unit)?=null
    private var images=emptyList<File>()
    private val origin="https://appassets.androidplatform.net"
    private var web=WebView(context)
    init { setup() }
    private fun setup(){
        web.settings.apply{javaScriptEnabled=true;domStorageEnabled=true;allowFileAccess=false;allowContentAccess=false
            mixedContentMode=WebSettings.MIXED_CONTENT_NEVER_ALLOW;setSupportMultipleWindows(false)}
        web.addJavascriptInterface(Bridge(),"SoundcoreNative")
        web.webViewClient=object:WebViewClient(){
            override fun onRenderProcessGone(view:WebView,detail:RenderProcessGoneDetail):Boolean {
                main.post{
                    finish(generation,Result.failure(IllegalStateException("识谱组件内存不足，已重建；可以重试较小图片")))
                    if(!closed){loaded=false;web.destroy();web=WebView(context);setup()}
                };return true
            }
            override fun onReceivedError(view:WebView,request:WebResourceRequest,error:WebResourceError){
                if(request.isForMainFrame)main.post{finish(generation,Result.failure(IllegalStateException("本地识谱组件加载失败：${error.description}")))}
            }
            override fun shouldOverrideUrlLoading(view:WebView,request:WebResourceRequest)=true
            override fun shouldInterceptRequest(view:WebView,request:WebResourceRequest):WebResourceResponse {
                val uri=request.url;val path=uri.path.orEmpty()
                if(uri.scheme!="https" || uri.host!="appassets.androidplatform.net" || !path.startsWith("/offline/") || path.contains(".."))return blocked()
                return try{
                    val image=Regex("/offline/input/(\\d+)").matchEntire(path)
                    if(image!=null){val file=images.getOrNull(image.groupValues[1].toInt())?:return blocked()
                        WebResourceResponse("image/jpeg",null,file.inputStream())}
                    else {val mime=when(path.substringAfterLast('.')){"html"->"text/html";"js"->"application/javascript";"json"->"application/json";"wasm"->"application/wasm";else->"application/octet-stream"}
                        WebResourceResponse(mime,"UTF-8",context.assets.open(path.removePrefix("/"))).apply{
                            responseHeaders=mapOf("Cache-Control" to "no-store","Content-Security-Policy" to "default-src 'self' data: blob:; script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval'; worker-src 'self' blob:; connect-src 'self'; img-src 'self' data: blob:")}}
                }catch(_:Exception){blocked()}
            }
        }
        web.loadUrl("$origin/offline/index.html")
    }
    private fun blocked()=WebResourceResponse("text/plain","UTF-8",403,"Blocked",emptyMap(),ByteArrayInputStream(byteArrayOf()))
    fun recognize(files:List<File>,overrides:JSONObject,onProgress:(Int,String)->Unit,onResult:(Result<SheetMusic>)->Unit,mode:SheetRecognitionMode=SheetRecognitionMode.PHONE){
        check(!closed);cancel();val id=++generation;images=files;done=onResult;progress=onProgress
        begin={val pages=JSONArray();files.indices.forEach{pages.put(JSONObject().put("image","$origin/offline/input/$it").put("name","第${it+1}页"))}
            web.evaluateJavascript("SoundcoreOffline.start($id,$pages,$overrides,${JSONObject.quote(if(mode==SheetRecognitionMode.DEVICE)"fpga" else "phone")})",null)}
        if(loaded){begin?.invoke();begin=null}else onProgress(0,"初始化手机本地识谱…")
        main.postDelayed({if(id==generation && done!=null)finish(id,Result.failure(IllegalStateException("本次识谱超时，原结果保留；可按页重试")))},360000)
        main.postDelayed({if(id==generation && !loaded)finish(id,Result.failure(IllegalStateException("本地识谱组件未能初始化，请重新进入识谱页面")))},20000)
    }
    private fun finish(id:Int,result:Result<SheetMusic>){if(id!=generation || closed)return;val callback=done;done=null;progress=null;begin=null;callback?.invoke(result)}
    fun cancel(){generation++;begin=null;done=null;progress=null;ble.cancelOmr();if(loaded && !closed)web.evaluateJavascript("SoundcoreOffline.cancel()",null)}
    fun close(){cancel();closed=true;web.removeJavascriptInterface("SoundcoreNative");web.destroy()}
    private inner class Bridge {
        @JavascriptInterface fun connected()=ble.view.connected
        @JavascriptInterface fun ready(){main.post{if(!closed){loaded=true;begin?.invoke();begin=null}}}
        @JavascriptInterface fun progress(id:Int,value:Int,text:String){main.post{if(id==generation && !closed)progress?.invoke(value.coerceIn(0,100),text.take(160))}}
        @JavascriptInterface fun classify(id:Int,request:Int,hex:String){main.post{
            if(id!=generation || closed)return@post
            if(!hex.matches(Regex("[a-f0-9]{64}"))){finish(id,Result.failure(IllegalStateException("本地符号图像无效")));return@post}
            val bitmap=ByteArray(32){hex.substring(it*2,it*2+2).toInt(16).toByte()}
            ble.inferBitmap(bitmap){result->if(id==generation && !closed){
                val value=result.getOrNull()?.let{JSONObject().put("class",it.symbolClass).put("margin",it.margin).toString()}?:"null"
                val error=result.exceptionOrNull()?.message?.let{JSONObject.quote(it)}?:"null"
                web.evaluateJavascript("SoundcoreOffline.result($request,$value,$error)",null)
            }}
        }}
        @JavascriptInterface fun cancelGlyph(){main.post{ble.cancelOmr()}}
        @JavascriptInterface fun complete(id:Int,json:String){main.post{if(id==generation && !closed){
            val result=runCatching{require(json.length<=2_000_000);SheetMusic(JSONObject(json)).also{it.compile();it.parts()}}
            finish(id,result)
        }}}
        @JavascriptInterface fun error(id:Int,message:String){main.post{finish(id,Result.failure(IllegalStateException(message.take(250))))}}
    }
}
