package cn.soundcore.instrument

/** The creative pipeline is local. Preserve cancellation and useful model errors. */
internal fun creationError(error:Exception):String=when(error) {
    is InterruptedException->"已取消识别"
    else->error.message?.take(180)?:"暂时未能完成，请稍后再试"
}
