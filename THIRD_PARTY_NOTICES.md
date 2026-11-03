# 第三方与资产归属

1. CREPE / torchcrepe基础预训练权重，MIT。当前crepe_tiny.json明确说明无项目重训练。ONNX导出不改变基础权重的来源。保留android/app/src/main/assets/open_source_licenses中的CREPE与TORCHCREPE许可证。
2. ONNX Runtime，MIT；保留ONNX_RUNTIME_LICENSE.txt。Gradle依赖按其原许可证使用。
3. Tesseract.js / OCR训练数据、WASM依赖：保留android/app/src/main/assets/offline/ocr中的LICENSE及TRAINEDDATA_LICENSE、打包JS内许可证注释；相应上游许可证优先。
4. librosa相关设计/工具归属见随包ISC声明；其他Python依赖适用各自许可。
5. Gowin PLL、BRAM仿真原语与厂商生成IP按高云原有条款使用；仅分发项目已有包装源与配置，不分发IDE、下载器或厂商加密工具。请从厂商安装相应工具与仿真库。
6. 公版书架旋律使用传统/公版乐曲及已有来源说明，各JSON中source字段保留；编配不是原录音。完整竞赛工程中两首现代歌曲事件/歌词数据来源于提交者提供材料，不纳入项目MIT许可。公开仓库使用单独公版示例。
7. 现场照片、录音、人声分离文件、API凭据、SDK/编译缓存、电脑用户名与调试签名私钥不属于公开源码分发内容。
8. 本项目原创贡献集中于HDL调度与资源复用、压力事件策略、识别证据融合/事件转换和系统联动。不宣称通用DDS、ADSR、FFT或第三方模型由项目首创。
