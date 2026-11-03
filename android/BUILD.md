JDK 17; Gradle 8.13; Android SDK compileSdk 36, targetSdk 35, minSdk 26.
Run gradle :app:assembleDebug and gradle :app:testDebugUnitTest. Create local.properties with your sdk.dir; no API key is required.
Snapshot tests: gradle :app:verifyPaparazziDebug. Instrumented/device tests need an actual phone and permissions. Do not distribute the local debug keystore as project source.
