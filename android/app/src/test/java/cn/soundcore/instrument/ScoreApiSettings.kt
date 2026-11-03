package cn.soundcore.instrument

import android.content.Context
import java.util.UUID

/** Historical configuration contract for protocol regressions; test source only. */
class ScoreApiSettings(context:Context) {
    private val prefs=context.getSharedPreferences("score_api",Context.MODE_PRIVATE)
    fun engine()=RecognitionEngine.API
    @android.annotation.SuppressLint("UseKtx") // A checked synchronous commit prevents an unsaved installation identity.
    fun load():ScoreApiConfig {
        val id=prefs.getString("installation_id",null)?:UUID.randomUUID().toString().replace("-","").also{
            check(prefs.edit().putString("installation_id",it).commit()){"创作会话未能保存，请重试"}
        }
        return ScoreApiConfig(ManagedRecognition.BASE_URL,managed=true,installationId=id)
    }
}
