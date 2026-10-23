plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.lelokz.jarvis"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.lelokz.jarvis"
        minSdk = 29          // Android 10+: o S21 FE e o Galaxy Watch 7 sobram
        targetSdk = 35
        versionCode = 20
        versionName = "0.11.1 (janela beta 0.10.5)"
        // O S21 FE e o Galaxy Watch 7 são 64 bits: sem as outras arquiteturas,
        // o onnxruntime não incha o APK.
        ndk { abiFilters += listOf("arm64-v8a") }
    }

    // O átomo, a voz, o ouvido e o tubo do relógio: iguais no relógio.
    sourceSets["main"].java.srcDir("../comum")

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    // WebSocket da porta remota (porta_remota.py)
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    // O "hey Jarvis" no celular: os mesmos modelos ONNX do PC (openWakeWord e
    // o Silero VAD), em assets/.
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")
    // A ponte do relógio: o canal do Wear OS (PonteRelogio.kt).
    implementation("com.google.android.gms:play-services-wearable:18.2.0")
}
