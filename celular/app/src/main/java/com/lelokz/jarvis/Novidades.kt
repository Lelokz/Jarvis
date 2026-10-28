package com.lelokz.jarvis

import android.app.Application
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * O que o PC guardou para o celular (por enquanto, a escola: nota nova, prova
 * na agenda) e a versão do app compilado. O app busca na porta remota
 * (`/novidades` e `/versao`): ao conectar e, com o app fechado, a cada 15 min
 * pelo Android (`TarefaNovidades`). Sem o celular precisar ficar ligado no PC.
 */
object Novidades {
    private val cliente = OkHttpClient.Builder().callTimeout(15, TimeUnit.SECONDS).build()
    private const val CANAL = "escola"

    private fun prefs(c: Context) = c.getSharedPreferences("jarvis", Context.MODE_PRIVATE)

    /** Busca e mostra as novidades que ainda não apareceram. Roda fora da thread principal. */
    fun buscar(c: Context) {
        val p = prefs(c)
        val base = p.getString("base", null)?.trimEnd('/') ?: return
        val chave = p.getString("chave", null) ?: return
        val primeiraVez = !p.contains("novidade_ultima")
        val ultima = p.getLong("novidade_ultima", 0L)
        val lista = try {
            cliente.newCall(Request.Builder().url("$base/novidades?desde=$ultima")
                .header("Authorization", "Bearer $chave").build()).execute().use { r ->
                if (!r.isSuccessful) return
                JSONObject(r.body?.string() ?: return).optJSONArray("novidades") ?: return
            }
        } catch (e: Exception) {
            return  // PC desligado ou sem Tailscale: tenta na próxima
        }
        // Desligadas nos Ajustes do app: marca como vistas, sem mostrar. O
        // interruptor é o da escola; os avisos do grupo da família sempre saem.
        val mostrarEscola = p.getBoolean("notificar_escola", true)
        var maior = ultima
        for (i in 0 until lista.length()) {
            val n = lista.getJSONObject(i)
            val id = n.optLong("id")
            if (id <= ultima) continue
            maior = maxOf(maior, id)
            // Na primeira vez só marca o que já existia: nada de enxurrada.
            if (!primeiraVez && (n.optString("tipo") == "grupo" || mostrarEscola)) mostrar(c, id, n.optString("titulo", "NOVA"), n.optString("texto"))
        }
        p.edit().putLong("novidade_ultima", maior).apply()
    }

    private fun mostrar(c: Context, id: Long, titulo: String, texto: String) {
        val gerente = c.getSystemService(NotificationManager::class.java)
        gerente.createNotificationChannel(
            NotificationChannel(CANAL, "Escola", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "Nota nova, média e o que os professores postaram na agenda"
            })
        val abrir = PendingIntent.getActivity(c, 0, Intent(c, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE)
        val aviso = Notification.Builder(c, CANAL)
            .setContentTitle(titulo)
            .setContentText(texto.lineSequence().first())
            .setStyle(Notification.BigTextStyle().bigText(texto))
            .setSmallIcon(R.drawable.ic_notificacao)
            .setContentIntent(abrir)
            .setAutoCancel(true)
            .build()
        try {
            gerente.notify((id % Int.MAX_VALUE).toInt(), aviso)
        } catch (e: SecurityException) {
            // Sem a permissão de notificação: fica para quando ele der.
        }
    }

    private const val CANAL_SEGURANCA = "seguranca"
    private const val ID_NOTIF_DESBLOQUEIO = 77

    // -- pedidos do grupo da família (beta 0.13.0) -----------------------------

    /** O primeiro pedido esperando o Sim: (id, quem, pedido), ou null. */
    fun pedidoPendente(c: Context): Triple<String, String, String>? {
        val p = prefs(c)
        val base = p.getString("base", null)?.trimEnd('/') ?: return null
        val chave = p.getString("chave", null) ?: return null
        return try {
            cliente.newCall(Request.Builder().url("$base/aprovacao")
                .header("Authorization", "Bearer $chave").build()).execute().use { r ->
                if (!r.isSuccessful) null
                else JSONObject(r.body?.string() ?: return null).optJSONArray("pedidos")?.optJSONObject(0)
                    ?.let { Triple(it.optString("id"), it.optString("quem"), it.optString("pedido")) }
            }
        } catch (e: Exception) {
            null
        }
    }

    fun responderPedido(c: Context, id: String, sim: Boolean): String {
        val p = prefs(c)
        val base = p.getString("base", null)?.trimEnd('/') ?: return ""
        val chave = p.getString("chave", null) ?: return ""
        c.getSystemService(NotificationManager::class.java).cancel(ID_NOTIF_PEDIDO)
        return try {
            val corpo = JSONObject().put("id", id).put("sim", sim).toString()
                .toRequestBody("application/json".toMediaType())
            cliente.newCall(Request.Builder().url("$base/aprovacao").post(corpo)
                .header("Authorization", "Bearer $chave").build()).execute().use { r ->
                JSONObject(r.body?.string() ?: "{}").optString("resultado")
            }
        } catch (e: Exception) {
            ""
        }
    }

    private const val ID_NOTIF_PEDIDO = 78

    fun notificarPedido(c: Context, quem: String, pedido: String) {
        val gerente = c.getSystemService(NotificationManager::class.java)
        gerente.createNotificationChannel(
            NotificationChannel(CANAL_SEGURANCA, "Segurança do PC", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Quando pedem para desbloquear o PC ou algo pelo grupo da família"
            })
        val abrir = PendingIntent.getActivity(c, 3, Intent(c, MainActivity::class.java)
            .putExtra("aprovacao", true).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val aviso = Notification.Builder(c, CANAL_SEGURANCA)
            .setContentTitle("Pedido de $quem pro Jarvis")
            .setContentText(pedido)
            .setStyle(Notification.BigTextStyle().bigText(pedido))
            .setSmallIcon(R.drawable.ic_notificacao)
            .setContentIntent(abrir)
            .setAutoCancel(true)
            .setTimeoutAfter(5 * 60 * 1000L)
            .build()
        try { gerente.notify(ID_NOTIF_PEDIDO, aviso) } catch (e: SecurityException) { }
    }

    /** O pedido de desbloquear o PC esperando resposta: o id, ou null. */
    fun desbloqueioPendente(c: Context): String? {
        val p = prefs(c)
        val base = p.getString("base", null)?.trimEnd('/') ?: return null
        val chave = p.getString("chave", null) ?: return null
        return try {
            cliente.newCall(Request.Builder().url("$base/desbloqueio")
                .header("Authorization", "Bearer $chave").build()).execute().use { r ->
                if (!r.isSuccessful) null
                else JSONObject(r.body?.string() ?: return null).optJSONObject("pedido")?.optString("id")
                    ?.takeIf { it.isNotEmpty() }
            }
        } catch (e: Exception) {
            null
        }
    }

    /** Sim ou Não. Devolve "desbloqueado", "recusado", "expirou", "falhou" ou "" (sem conexão). */
    fun responderDesbloqueio(c: Context, id: String, sim: Boolean): String {
        val p = prefs(c)
        val base = p.getString("base", null)?.trimEnd('/') ?: return ""
        val chave = p.getString("chave", null) ?: return ""
        tirarNotificacaoDesbloqueio(c)
        return try {
            val corpo = JSONObject().put("id", id).put("sim", sim).toString()
                .toRequestBody("application/json".toMediaType())
            cliente.newCall(Request.Builder().url("$base/desbloqueio").post(corpo)
                .header("Authorization", "Bearer $chave").build()).execute().use { r ->
                JSONObject(r.body?.string() ?: "{}").optString("resultado")
            }
        } catch (e: Exception) {
            ""
        }
    }

    /** A notificação "Pediram pra desbloquear o PC": tocar abre o app já no aviso. */
    fun notificarDesbloqueio(c: Context) {
        val gerente = c.getSystemService(NotificationManager::class.java)
        gerente.createNotificationChannel(
            NotificationChannel(CANAL_SEGURANCA, "Segurança do PC", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Quando pedem para desbloquear o PC"
            })
        val abrir = PendingIntent.getActivity(c, 1, Intent(c, MainActivity::class.java)
            .putExtra("desbloqueio", true).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val aviso = Notification.Builder(c, CANAL_SEGURANCA)
            .setContentTitle("Desbloquear o PC?")
            .setContentText("Pediram pro Jarvis desbloquear o PC. Toque pra responder.")
            .setSmallIcon(R.drawable.ic_notificacao)
            .setContentIntent(abrir)
            .setAutoCancel(true)
            .setTimeoutAfter(3 * 60 * 1000L)
            .build()
        try {
            gerente.notify(ID_NOTIF_DESBLOQUEIO, aviso)
        } catch (e: SecurityException) {
        }
    }

    fun tirarNotificacaoDesbloqueio(c: Context) =
        c.getSystemService(NotificationManager::class.java).cancel(ID_NOTIF_DESBLOQUEIO)

    /** O versionCode do app compilado no PC, ou null se não deu para saber. */
    fun versaoNoPc(c: Context): Int? {
        val base = prefs(c).getString("base", null)?.trimEnd('/') ?: return null
        return try {
            cliente.newCall(Request.Builder().url("$base/versao").build()).execute().use { r ->
                if (!r.isSuccessful) null
                else JSONObject(r.body?.string() ?: return null).optInt("versionCode", -1).takeIf { it > 0 }
            }
        } catch (e: Exception) {
            null
        }
    }

    /** A cada 15 min (o mínimo do Android), só com internet. */
    fun agendar(app: Application) {
        // Se o Android recusar, o app segue sem a busca de fundo: nunca derruba
        // a abertura (a beta 0.7 caía aqui, sem ACCESS_NETWORK_STATE).
        try {
            val agenda = app.getSystemService(JobScheduler::class.java)
            if (agenda.getPendingJob(TarefaNovidades.ID) != null) return
            agenda.schedule(JobInfo.Builder(TarefaNovidades.ID, ComponentName(app, TarefaNovidades::class.java))
                .setPeriodic(TimeUnit.MINUTES.toMillis(15))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPersisted(true)
                .build())
        } catch (e: Exception) {
        }
    }
}

/** O Android chama de tempos em tempos, mesmo com o app fechado. */
class TarefaNovidades : JobService() {
    override fun onStartJob(params: JobParameters): Boolean {
        Thread({
            Novidades.buscar(applicationContext)
            // App fechado: o pedido de desbloquear também chega por aqui (o
            // aviso na hora vai pelo WhatsApp do próprio Léo).
            if (Novidades.desbloqueioPendente(applicationContext) != null)
                Novidades.notificarDesbloqueio(applicationContext)
            Novidades.pedidoPendente(applicationContext)?.let { (_, quem, pedido) ->
                Novidades.notificarPedido(applicationContext, quem, pedido)
            }
            jobFinished(params, false)
        }, "novidades").start()
        return true
    }

    override fun onStopJob(params: JobParameters): Boolean = true

    companion object { const val ID = 31 }
}
