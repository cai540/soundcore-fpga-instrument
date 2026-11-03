package cn.soundcore.instrument

enum class AppDestination(val index:Int,val label:String) {
    PERFORMANCE(0,"演奏"), LIBRARY(1,"曲库"), CREATE(2,"创作"), SOUND(3,"音色"), DEVICE(4,"设备");
    companion object { fun fromIndex(index:Int)=entries.firstOrNull{it.index==index}?:PERFORMANCE }
}
