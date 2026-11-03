package cn.soundcore.instrument

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.nio.FloatBuffer
import java.security.MessageDigest
import kotlin.math.*

/** Immutable bundled weights, one reusable session. No download or service client. */
internal class CrepePitchObserver(private val modelBytes:()->ByteArray):AutoCloseable {
    private var session:OrtSession?=null
    private val environment=OrtEnvironment.getEnvironment()
    var loads=0;private set
    private fun session():OrtSession {
        session?.let{return it}
        val bytes=modelBytes()
        val sha=MessageDigest.getInstance("SHA-256").digest(bytes).joinToString(""){"%02x".format(it)}
        require(sha==MODEL_SHA){"内置音高模型校验失败，请重新安装完整APK"}
        return OrtSession.SessionOptions().use { options ->
            options.setIntraOpNumThreads(2);options.setInterOpNumThreads(1);options.setCPUArenaAllocator(false)
            environment.createSession(bytes,options).also{session=it;loads++}
        }
    }
    /** 20ms neural observations; 10ms acoustic onset clock remains separate. */
    @Synchronized fun observe(pcm:FloatArray,progress:(Int)->Unit={},cancelled:()->Boolean={false}):Array<FloatArray> {
        require(pcm.size in 4000..640000 && pcm.all{it.isFinite()})
        if(cancelled())throw InterruptedException("已取消识别")
        val model=session();val count=pcm.size/320+1
        val result=Array(count){FloatArray(360)}
        for(start in 0 until count step 2){
            if(cancelled())throw InterruptedException("已取消识别")
            val n=min(2,count-start);val input=FloatArray(n*1024)
            for(k in 0 until n){
                var mean=0.0
                for(j in 0 until 1024){val value=pcm.getOrElse((start+k)*320-512+j){0f};input[k*1024+j]=value;mean+=value}
                mean/=1024;var variance=0.0
                for(j in 0 until 1024){val value=input[k*1024+j]-mean;input[k*1024+j]=value.toFloat();variance+=value*value}
                val scale=max(1e-10,sqrt(variance/1023))
                for(j in 0 until 1024)input[k*1024+j]=(input[k*1024+j]/scale).toFloat()
            }
            OnnxTensor.createTensor(environment,FloatBuffer.wrap(input),longArrayOf(n.toLong(),1024)).use{tensor->
                model.run(mapOf("frames" to tensor)).use { output ->
                    @Suppress("UNCHECKED_CAST")
                    val rows=output[0].value as Array<FloatArray>
                    check(rows.size==n && rows.all{it.size==360 && it.all{v->v.isFinite() && v in 0f..1f}}){"音高模型输出异常"}
                    for(k in 0 until n)result[start+k]=rows[k].copyOf()
                }
            }
            if(cancelled())throw InterruptedException("已取消识别")
            progress(min(100,(start+n)*100/count))
        }
        return result
    }
    @Synchronized override fun close(){session?.close();session=null}
    companion object {const val MODEL_SHA="bfd412b7d1b8209bbd2a0ca8f3b96783a7de0ce25cfed4f7d9e9a57595747ccb"}
}
