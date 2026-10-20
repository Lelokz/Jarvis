package com.lelokz.jarvis

import android.app.Application

/** O processo do app do relógio: segura o Relogio único. */
class App : Application() {
    val relogio: Relogio by lazy { Relogio(this) }
}
