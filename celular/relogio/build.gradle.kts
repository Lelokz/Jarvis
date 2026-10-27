plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// O Jarvis no Galaxy Watch 7 (Wear OS 5). O applicationId e a chave de
// assinatura TÊM que ser os mesmos do app do celular: é assim que o Wear OS
// deixa os dois conversarem (o relógio fala com o PC pelo celular).
android {
    namespace = "com.lelokz.jarvis"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.lelokz.jarvis"
        minSdk = 30          // Wear OS 3+
        targetSdk = 34       // Wear OS 5 é Android 14
        versionCode = 4
        versionName = "0.3.0"
        // O Galaxy Watch 7 roda em 32 bits (conferido no adb).
        ndk { abiFilters += listOf("armeabi-v7a") }
    }

    // O átomo, a voz, o Silero e o tubo vêm de comum/; o ícone e o tema, do
    // app do celular (o mesmo Jarvis).
    sourceSets["main"].java.srcDir("../comum")
    sourceSets["main"].res.srcDir("../app/src/main/res")

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
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("com.google.android.gms:play-services-wearable:18.2.0")
    // Só para compilar o comum/Ouvido.kt: no relógio o onnxruntime quebra
    // (32 bits), e o fim da frase é pelo volume (Escuta.kt).
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")
}
