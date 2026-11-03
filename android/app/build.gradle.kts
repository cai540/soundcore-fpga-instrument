plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("app.cash.paparazzi")
}
android {
    namespace = "cn.soundcore.instrument"
    compileSdk = 36
    defaultConfig {
        applicationId = "cn.soundcore.instrument"
        minSdk = 26
        targetSdk = 35
        versionCode = 24
        versionName = "0.24-scope-lab"
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true; buildConfig = true }
}
dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.08.00")
    implementation(composeBom)
    implementation("androidx.activity:activity-compose:1.12.4")
    implementation("androidx.exifinterface:exifinterface:1.4.2")
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.23.2")
    testImplementation("com.microsoft.onnxruntime:onnxruntime:1.23.2")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20250517")
}
