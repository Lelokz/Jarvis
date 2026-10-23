package com.lelokz.jarvis

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.net.Uri
import android.os.Build
import android.provider.Settings
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * O app se atualiza sozinho (beta 0.10.0): baixa o APK novo da porta remota e
 * entrega ao instalador do Android. Fica só o "Atualizar este app?" do
 * sistema, que nenhum app pode pular. Antes era o Chrome baixando, com os
 * avisos de "app desconhecido" a cada vez (pedido do Léo, 23/10/2026).
 */
object Atualizador {
    private val cliente = OkHttpClient.Builder().callTimeout(3, TimeUnit.MINUTES).build()

    /** O Android deixa o Jarvis instalar? Na primeira vez, não: abre o ajuste dele. */
    fun podeInstalar(c: Context): Boolean {
        if (c.packageManager.canRequestPackageInstalls()) return true
        c.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${c.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        return false
    }

    /** Baixa e manda instalar. Roda fora da thread principal. Devolve o erro, ou "" se foi. */
    fun baixarEInstalar(c: Context, base: String, progresso: (Float) -> Unit): String {
        val arquivo = File(c.cacheDir, "jarvis.apk")
        try {
            cliente.newCall(Request.Builder().url("${base.trimEnd('/')}/jarvis.apk").build()).execute().use { r ->
                if (!r.isSuccessful) return "O PC não entregou o app (${r.code})."
                val corpo = r.body ?: return "Veio vazio."
                val total = corpo.contentLength()
                var baixado = 0L
                var ultimo = -1
                arquivo.outputStream().use { saida ->
                    corpo.byteStream().use { entrada ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            val n = entrada.read(buffer)
                            if (n < 0) break
                            saida.write(buffer, 0, n)
                            baixado += n
                            val pct = if (total > 0) (baixado * 100 / total).toInt() else -1
                            if (pct != ultimo) { ultimo = pct; if (pct >= 0) progresso(pct / 100f) }
                        }
                    }
                }
            }
        } catch (e: Exception) {
            return "Sem conexão com o PC."
        }
        return try {
            val instalador = c.packageManager.packageInstaller
            val parametros = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
                .apply { setAppPackageName(c.packageName) }
            val id = instalador.createSession(parametros)
            instalador.openSession(id).use { sessao ->
                sessao.openWrite("jarvis", 0, arquivo.length()).use { saida ->
                    arquivo.inputStream().use { it.copyTo(saida) }
                    sessao.fsync(saida)
                }
                // Mutável: o instalador põe o resultado nos extras.
                val resposta = PendingIntent.getBroadcast(c, id, Intent(c, ResultadoDaInstalacao::class.java),
                    PendingIntent.FLAG_UPDATE_CURRENT or
                        (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0))
                sessao.commit(resposta.intentSender)
            }
            ""
        } catch (e: Exception) {
            "Não deu pra instalar (${e.message})."
        } finally {
            arquivo.delete()
        }
    }
}

/** O instalador responde aqui: precisa da confirmação do Léo, deu certo ou falhou. */
class ResultadoDaInstalacao : BroadcastReceiver() {
    override fun onReceive(c: Context, intent: Intent) {
        when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val confirmar = if (Build.VERSION.SDK_INT >= 33)
                    intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
                else intent.getParcelableExtra(Intent.EXTRA_INTENT)
                confirmar?.let { c.startActivity(it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
            }
            PackageInstaller.STATUS_SUCCESS -> Unit  // o app reinicia na versão nova
            else -> (c.applicationContext as? App)?.jarvis?.let {
                // Cancelou ou falhou: dá para tentar de novo pelo retângulo.
                it.atualizando.value = -1f
                it.aviso.value = "A atualização não foi: ${intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "cancelada"}"
            }
        }
    }
}
