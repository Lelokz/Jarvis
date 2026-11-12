package com.lelokz.painel

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.compose.runtime.mutableStateOf
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Igual ao do app da NOVA: baixa o APK novo da porta remota e entrega ao
 * instalador do Android. Fica só o "Atualizar este app?" do sistema.
 */
object Atualizador {
    private val cliente = OkHttpClient.Builder().callTimeout(3, TimeUnit.MINUTES).build()

    /** Cancelou ou falhou (o instalador avisa aqui; a tela mostra e volta o retângulo). */
    val falhou = mutableStateOf("")

    /** O Android deixa o Painel instalar? Na primeira vez, não: abre o ajuste dele. */
    fun podeInstalar(c: Context): Boolean {
        if (c.packageManager.canRequestPackageInstalls()) return true
        c.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${c.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        return false
    }

    /** Baixa e manda instalar. Roda fora da thread principal. Devolve o erro, ou "" se foi. */
    fun baixarEInstalar(c: Context, url: String, progresso: (Float) -> Unit): String {
        val arquivo = File(c.cacheDir, "painel.apk")
        try {
            cliente.newCall(Request.Builder().url(url).build()).execute().use { r ->
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
                sessao.openWrite("painel", 0, arquivo.length()).use { saida ->
                    arquivo.inputStream().use { it.copyTo(saida) }
                    sessao.fsync(saida)
                }
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
    private fun notificar(c: Context, confirmar: Intent) {
        val gerente = c.getSystemService(NotificationManager::class.java)
        gerente.createNotificationChannel(NotificationChannel("atualizacao", "Atualização do app",
            NotificationManager.IMPORTANCE_HIGH))
        val abrir = PendingIntent.getActivity(c, 5, confirmar, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val aviso = Notification.Builder(c, "atualizacao")
            .setContentTitle("Atualização do Painel pronta")
            .setContentText("Toca pra instalar")
            .setSmallIcon(R.drawable.ic_notificacao)
            .setContentIntent(abrir)
            .setAutoCancel(true)
            .setTimeoutAfter(15 * 60 * 1000L)
            .build()
        try { gerente.notify(79, aviso) } catch (e: SecurityException) { }
    }

    override fun onReceive(c: Context, intent: Intent) {
        when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val confirmar = if (Build.VERSION.SDK_INT >= 33)
                    intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
                else intent.getParcelableExtra(Intent.EXTRA_INTENT)
                confirmar ?: return
                confirmar.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                notificar(c, confirmar)
                try { c.startActivity(confirmar) } catch (e: Exception) { }
            }
            PackageInstaller.STATUS_SUCCESS -> Unit
            else -> Atualizador.falhou.value =
                "A atualização não foi: ${intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "cancelada"}"
        }
    }
}
