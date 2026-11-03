package cn.soundcore.instrument

// Generated from the same catalogue as the FPGA ROM lengths.
data class SongEntry(val id: Int, val title: String, val events: Int)
object SongCatalog {
    val songs = listOf(
        SongEntry(0, "公版示例甲", 246),
        SongEntry(1, "公版示例乙", 224)
    )
    fun title(id: Int) = songs.getOrElse(id) { songs[0] }.title
    fun length(id: Int) = songs.getOrElse(id) { songs[0] }.events
}
