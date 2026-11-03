package cn.soundcore.instrument

import org.json.JSONObject
import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.io.ByteArrayOutputStream
import java.net.ServerSocket
import java.net.InetAddress
import java.io.InputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.nio.ByteBuffer
import java.nio.ByteOrder

class ScoreApiTest {
    @Test fun managedLiveServiceWorksWithProductionClientWithoutManualConfiguration() {
        org.junit.Assume.assumeTrue(System.getenv("SCORE_API_MANAGED_LIVE")=="1")
        val root=File("../../..").canonicalFile
        val client=ScoreApiClient(ScoreApiConfig(ManagedRecognition.BASE_URL,managed=true,installationId=java.util.UUID.randomUUID().toString().replace("-","")))
        val music=client.recognizeSheet(File(root,"tests/fixtures/sheet_test.png").readBytes(),"image/png"){_,_->}
        val events=music.compile().first
        assertTrue(events.isNotEmpty());assertTrue(music.parts().isNotEmpty())
        File(root,"build/app_product_20261101/live_ai/android_managed_live.json").writeText(JSONObject()
            .put("actual_production_client",true).put("manual_configuration",false)
            .put("provider_key_in_client",false).put("title",music.title).put("events",events.size).toString(2))
    }
    @Test fun nativeClipIsNotDownsampledBeforeUploadAndLocalClockRemainsAligned() {
        for(rate in listOf(16000,22050,44100,48000)) {
            val native=NativeMelodyPcm(FloatArray(rate*2){it.toFloat()/rate},rate)
            val clipped=native.clip(MelodyRange(500,1500))
            assertEquals(rate,clipped.size);assertEquals(.5f,clipped.first(),.0001f)
            assertEquals(32000,native.local16k().size)
        }
        val buffer=NativePcmBuffer(44100,1)
        repeat(44100){buffer.push(it/44100f)}
        assertEquals(44100,buffer.finish().samples.size)
        assertEquals(44099/44100f,buffer.finish().samples.last(),0f)
    }
    @Test fun liveApiUsesActualAndroidClientWithArbitraryPcm() {
        org.junit.Assume.assumeTrue(System.getenv("SCORE_API_LIVE")=="1")
        val root=File("../../..").canonicalFile
        val key=File(root,".score-api/service.key").readText().trim()
        val input=File(root,"build/vocal_40s_phrase_20261030/inputs/zuguo/source.wav")
        val ff=ProcessBuilder("ffmpeg","-v","error","-i",input.path,"-ac","1","-ar","44100","-f","f32le","-").start()
        val raw=ff.inputStream.readBytes();check(ff.waitFor()==0)
        val b=ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);val pcm=FloatArray(raw.size/4){b.float}
        val progress=mutableListOf<Int>()
        val found=ScoreApiClient(ScoreApiConfig("http://127.0.0.1:8765",key)).recognize(pcm,44100){p,_->progress+=p}
        val expected=JSONObject(File(root,"build/score_api_20261030/real_http_native/http_result.json").readText()).getJSONObject("result").getJSONArray("notes")
        assertEquals((0 until expected.length()).map{expected.getJSONObject(it).getInt("midi")},found.first.notes.map{it.midi})
        assertTrue(progress.zipWithNext().all{(a,b)->a<=b})
        assertTrue(found.second in setOf("source-vocal-units-v1","source-vocal-units-v1-bailian"))
        val out=JSONObject().put("actual_android_http_client",true).put("algorithm",found.second).put("notes",found.first.notes.size)
            .put("source_sample_rate",44100).put("pitch_sequence_identical",true).put("physical_hardware_test",false)
        val liveFolder=if(found.second.endsWith("-bailian"))"build/bailian_20261030" else "build/score_api_20261030"
        File(root,liveFolder).mkdirs();File(root,"$liveFolder/android_live_http.json").writeText(out.toString(2))
    }
    private class TinyServer(private val respond:(String,String,Map<String,String>,ByteArray)->JSONObject):AutoCloseable {
        private val socket=ServerSocket(0,20,InetAddress.getByName("127.0.0.1"))
        val port=socket.localPort
        private val pool=Executors.newCachedThreadPool()
        private val accept=Thread {
            while(!socket.isClosed)try {val client=socket.accept();pool.execute{try{client.use{c->
                c.soTimeout=5000;val input=c.getInputStream()
                val first=line(input).split(' ');val headers=mutableMapOf<String,String>()
                while(true){val l=line(input);if(l.isEmpty())break;val colon=l.indexOf(':');headers[l.substring(0,colon).lowercase()]=l.substring(colon+1).trim()}
                val data=ByteArray(headers["content-length"]?.toInt()?:0);var used=0
                while(used<data.size){val n=input.read(data,used,data.size-used);check(n>0);used+=n}
                val body=respond(first[0],first[1],headers,data).toString().toByteArray()
                c.getOutputStream().apply{write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${body.size}\r\nConnection: close\r\n\r\n".toByteArray());write(body);flush()}
            }}catch(_:java.io.IOException){/* Expected when the client cancels an in-flight response. */}}}catch(_:java.net.SocketException){if(!socket.isClosed)throw IllegalStateException("Test socket failed")}
        }.apply{isDaemon=true;start()}
        override fun close(){socket.close();accept.join(1000);pool.shutdownNow()}
        private fun line(input:InputStream):String {val out=ByteArrayOutputStream()
            while(true){val n=input.read();check(n>=0);if(n==10)return out.toString("UTF-8").trimEnd('\r');out.write(n);check(out.size()<8192)}}
    }
    private fun identity()=JSONObject().put("schema_version",1).put("request_id","request-1234567890")
        .put("source_sha256","digest").put("source_sample_rate",16000).put("source_duration_ms",250)
    private fun score()=identity().put("notes",JSONArray().put(JSONObject().put("start_ms",0).put("duration_ms",200).put("midi",60)))
    @Test fun addressPolicyRefusesPublicHttpAndCredentialUrls() {
        listOf("http://10.0.2.2:8765/","http://192.168.1.4:8765","https://example.org").forEach{ScoreApiContract.baseUrl(it)}
        listOf("http://example.org","http://8.8.8.8","http://192.168.1.4@evil.org","https://example.org?token=x",
            "file:///tmp/file","https://example.org/v1","http://192.168.1.4:0").forEach {
            assertTrue("rejected $it",runCatching{ScoreApiContract.baseUrl(it)}.isFailure) }
    }
    @Test fun resultRejectsWrongClockOverlapAndFractionalPitch() {
        fun parse(j:JSONObject)=ScoreApiContract.score(j,"request-1234567890","digest",16000,250)
        assertEquals(60,parse(score()).notes.single().midi)
        val fraction=score().apply{getJSONArray("notes").getJSONObject(0).put("midi",60.5)}
        val overlap=score().apply{getJSONArray("notes").put(JSONObject().put("start_ms",100).put("duration_ms",100).put("midi",62))}
        listOf(score().put("source_sha256","wrong"),score().put("source_duration_ms",251),fraction,overlap).forEach {
            assertTrue(runCatching{parse(it)}.isFailure) }
        val absolute=MelodyWorkspace.absolute(parse(score()),5000,12000)
        assertEquals(5000,absolute.notes.single().startMs)
        assertEquals(0f,absolute.notes.single().confidence)
    }
    @Test fun actualHttpCancellationDeletesOnlyThisJob() {
        val polled=CountDownLatch(1);val removed=CountDownLatch(1);val jobId="a".repeat(32)
        var source=JSONObject()
        val server=TinyServer{method,path,headers,bytes ->
            when {
                path.endsWith("health")->JSONObject().put("schema_version",1).put("ready",true).put("input_modes",JSONArray(listOf("vocal")))
                method=="POST"->{
                    assertEquals(4000*4,bytes.size)
                    source=JSONObject().put("schema_version",1).put("job_id",jobId).put("request_id",headers["idempotency-key"])
                        .put("source_sha256",headers["x-audio-sha256"]).put("source_sample_rate",16000).put("source_duration_ms",250)
                    JSONObject(source.toString()).put("status","queued").put("phase","queued").put("progress",0)}
                method=="DELETE"->{assertTrue(path.endsWith(jobId));removed.countDown();JSONObject().put("status","cancelled")}
                else->{polled.countDown();JSONObject(source.toString()).put("status","running").put("phase","speech").put("progress",10)}
            }
        }
        try {
            val client=ScoreApiClient(ScoreApiConfig("http://127.0.0.1:${server.port}","test-service-token-123456789"))
            val done=CountDownLatch(1);val failed=AtomicBoolean(false)
            val thread=Thread{try{client.recognize(FloatArray(4000){.1f},16000){_,_->}}catch(_:Exception){failed.set(true)}finally{done.countDown()}}
            thread.start();assertTrue(polled.await(5,TimeUnit.SECONDS));client.cancel()
            assertTrue(done.await(5,TimeUnit.SECONDS));assertTrue(failed.get());assertTrue(removed.await(2,TimeUnit.SECONDS))
        } finally {server.close()}
    }
    @Test fun managedImageJobBootstrapsSessionWithoutProviderOrManualToken() {
        var sessions=0;var source=JSONObject();val job="c".repeat(32)
        val document=JSONObject().put("notation","jianpu").put("title","测试曲").put("tonic_midi",60).put("bpm",80)
            .put("numerator",4).put("denominator",4).put("measures",JSONArray().put(JSONObject().put("id",1)
                .put("events",JSONArray().put(JSONObject().put("degree",1).put("octave",0).put("accidental",0).put("ticks",96)))))
        val server=TinyServer{method,path,headers,bytes->
            when {
                path=="/v1/session"->{sessions++;assertFalse(headers.containsKey("authorization"))
                    assertEquals("a".repeat(32),JSONObject(String(bytes)).getString("installation_id"))
                    JSONObject().put("access_token","test-short-lived-session-"+"x".repeat(40)).put("expires_at",System.currentTimeMillis()/1000+3600)}
                else->{assertTrue(headers["authorization"]!!.startsWith("Bearer test-short-lived-session-"))
                    when {
                        path.endsWith("sheet-health")->JSONObject().put("schema_version",1).put("ready",true)
                        method=="POST"->{assertEquals("image/png",headers["content-type"]);assertArrayEquals(byteArrayOf(1,2,3),bytes)
                            source=JSONObject().put("schema_version",1).put("job_id",job).put("request_id",headers["idempotency-key"])
                                .put("source_sha256",headers["x-image-sha256"]).put("source_sample_rate",0).put("source_duration_ms",0)
                            JSONObject(source.toString()).put("status","queued").put("progress",0)}
                        else->JSONObject(source.toString()).put("status","succeeded").put("progress",100)
                            .put("result",JSONObject(source.toString()).put("score",document))
                    }
                }
            }
        }
        try {
            val client=ScoreApiClient(ScoreApiConfig("http://127.0.0.1:${server.port}",managed=true,installationId="a".repeat(32)))
            val found=client.recognizeSheet(byteArrayOf(1,2,3),"image/png"){_,_->}
            assertEquals("测试曲",found.title);assertEquals(1,sessions);assertEquals(60,found.parts().first().score.notes.first().midi)
        } finally {server.close()}
    }
    @Test fun realApiResultPassesAndroidTransferAndCreatesRtlFixture() {
        val root=File("../../..").canonicalFile
        emitFixture(File(root,"build/score_api_20261030/real_http_phone16k/http_result.json"),File(root,"build/score_api_20261030/android_fixture"))
    }
    @Test fun realBailianResultPassesTheSameAndroidContractAndTransfer() {
        val root=File("../../..").canonicalFile
        emitFixture(File(root,"build/bailian_20261030/zuguo_http/http_result.json"),File(root,"build/bailian_20261030/android_fixture"))
    }
    private fun emitFixture(source:File,directory:File) {
        // External real-inference fixture is optional on clean checkouts; CI contract tests above remain deterministic.
        if(!source.exists())return
        val job=JSONObject(source.readText());val r=job.getJSONObject("result")
        val parsed=ScoreApiContract.score(r,r.getString("request_id"),r.getString("source_sha256"),r.getInt("source_sample_rate"),40000)
        val shifted=MelodyWorkspace.absolute(parsed,5000,50000)
        assertEquals(parsed.notes.map{it.startMs+5000},shifted.notes.map{it.startMs})
        val transpose=parsed.suggestedTranspose!!;val events=parsed.events(transpose)
        val transfer=ScoreTransfer(events,1,0x3456);val out=ByteArrayOutputStream();var seq=5
        while(!transfer.done){val cmd=transfer.next()!!;out.write(Protocol.encodeCommand(cmd.type,seq++,cmd.payload))
            val state=when(cmd.type){Protocol.SCORE_ABSOLUTE_BEGIN->UploadedScoreState(2,0,0,0,7,0,1,0,transfer.token,schema=2)
                Protocol.SCORE_DATA->UploadedScoreState(2,0,transfer.confirmed+(cmd.payload.size-4)/3,0,7,0,1,0,transfer.token,schema=2)
                else->UploadedScoreState(1,0,transfer.count,0,7,0,1,transfer.crc,transfer.token,schema=2)}
            transfer.acknowledge(cmd.type,state)}
        out.write(Protocol.encodeCommand(Protocol.SCORE_ACTION,seq,byteArrayOf(1)))
        directory.mkdirs();val bytes=out.toByteArray()
        File(directory,"android_upload.hex").writeText(bytes.joinToString("\n"){"%02x".format(it.toInt() and 255)})
        File(directory,"android_upload_meta.vh").writeText("`define FIXTURE_BYTES ${bytes.size}\n`define FIXTURE_EVENTS ${events.size}\n`define FIXTURE_NOTES ${parsed.notes.size}\n`define FIXTURE_CRC 16'h${transfer.crc.toString(16)}\n`define FIXTURE_MS ${events.sumOf{it.durationMs}}\n")
    }
}
