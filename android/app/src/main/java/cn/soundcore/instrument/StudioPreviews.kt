package cn.soundcore.instrument

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview

private val previewState = BleView(
    message = "已连接 · FPGA 已确认",
    connected = true,
    state = DeviceState(2, 1, 24, true, 2, 0, 3, 3, true)
)

@Composable
private fun PreviewPage(tab: Int) {
    SoundcoreTheme {
        StudioScreen(previewState, {}, {}, {}, { _, _ -> }, initialTab = tab)
    }
}

@Preview(name = "01 演奏", widthDp = 393, heightDp = 852, showBackground = true)
@Composable private fun PerformancePreview() = PreviewPage(0)

@Preview(name = "02 曲目", widthDp = 393, heightDp = 852, showBackground = true)
@Composable private fun SongsPreview() = PreviewPage(1)

@Preview(name = "03 音色", widthDp = 393, heightDp = 852, showBackground = true)
@Composable private fun TimbrePreview() = PreviewPage(3)

@Preview(name = "04 设备", widthDp = 393, heightDp = 852, showBackground = true)
@Composable private fun DevicePreview() = PreviewPage(4)
