plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// O app "Painel do Canal" (12/11/2026): o Painel do PC no celular, com a
// mesma ligação do app da NOVA (a porta remota). Versões de 5 em 5.
android {
    namespace = "com.lelokz.painel"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.lelokz.painel"
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = "beta 0.1.0"
    }

    // Só o átomo da NOVA (o resto do comum puxa o onnxruntime).
    sourceSets["main"].java.srcDir("atomo")

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
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
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
