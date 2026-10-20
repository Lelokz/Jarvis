package com.lelokz.jarvis

import android.app.Application

/** O processo do app: segura o Jarvis único (a tela e o serviço usam o mesmo). */
class App : Application() {
    val jarvis: Jarvis by lazy { Jarvis(this) }
    val ponte: PonteRelogio by lazy { PonteRelogio(this) }
}
