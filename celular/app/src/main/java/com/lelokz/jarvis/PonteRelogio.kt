package com.lelokz.jarvis

import android.app.Application
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder
import android.util.Base64
import com.google.android.gms.tasks.Tasks
import com.google.android.gms.wearable.ChannelClient
import com.google.android.gms.wearable.Wearable
import com.google.android.gms.wearable.WearableListenerService
import org.json.JSONObject
import java.io.DataInputStream
import java.io.DataOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.Executors

/**
 * O celular como ponte do relógio. O relógio não tem Tailscale: ele abre um
 * canal do Wear OS até aqui (Bluetooth), e o celular abre para ele uma
 * conexão própria na porta remota, com "quem": "relogio". Para o PC o relógio
 * é um corpo a mais: a voz do que ele pede vai só para ele.
 *
 * Quase tudo só passa: o que vem do PC desce pelo canal, o que sobe do
 * relógio vai para o PC. Duas coisas o celular faz no meio, para o relógio
 * responder mais rápido: decide o fim da frase do microfone do relógio
 * (`EscutaRemota`, com o Silero) e manda a voz pela metade da taxa.
 */
class PonteRelogio(private val app: Application) {
    private val prefs = app.getSharedPreferences("jarvis", Application.MODE_PRIVATE)
    private var atual: Sessao? = null
    private val escuta by lazy { EscutaRemota(app) }

    @Synchronized
    fun abrir(canal: ChannelClient.Channel) {
        atual?.fechar()
        atual = Sessao(canal).also { it.comecar() }
    }

    private inner class Sessao(private val canal: ChannelClient.Channel) {
        private val canais = Wearable.getChannelClient(app)
        private val escrita = Executors.newSingleThreadExecutor()
        private var saida: DataOutputStream? = null
        private var conexao: Conexao? = null
        @Volatile private var fechada = false

        fun comecar() = Thread({ rodar() }, "ponte-relogio").start()

        private fun rodar() {
            try {
                val entrada = DataInputStream(Tasks.await(canais.getInputStream(canal)).buffered())
                saida = DataOutputStream(Tasks.await(canais.getOutputStream(canal)).buffered())
                val base = prefs.getString("base", null)
                val chave = prefs.getString("chave", null)
                if (base == null || chave == null) {
                    estado(false, "abra o app no celular e cole o link")
                    Thread.sleep(500)
                    fechar()
                    return
                }
                val vivo = manterVivo(true)
                conexao = Conexao(base, chave, quem = "relogio", historico = 0,
                    aoReceber = { ev -> doPc(ev) },
                    aoMudar = { ok, motivo ->
                        estado(ok, if (ok) "" else motivo)
                        if (ok) conexao?.enviar(JSONObject().put("diag", JSONObject()
                            .put("motivo", "ponte do relógio aberta (celular acordado: $vivo)")))
                    }).also { it.abrir() }
                while (!fechada) {
                    val (tipo, dados) = Tubo.ler(entrada) ?: break
                    when (tipo) {
                        Tubo.TEXTO -> conexao?.enviar(JSONObject(String(dados)))
                        Tubo.AUDIO -> conexao?.enviar(dados)
                        Tubo.FALA_INICIO -> {
                            val j = try { JSONObject(String(dados)) } catch (e: Exception) { JSONObject() }
                            escuta.comecar(j.optLong("desiste_ms", 6000L))
                        }
                        Tubo.FALA_PEDACO -> {
                            val antes = escuta.falou
                            val fim = escuta.pedaco(dados)
                            if (!antes && escuta.falou) avisarEscuta(JSONObject().put("falou", true))
                            if (fim != null) terminarEscuta(fim)
                        }
                        Tubo.FALA_FIM -> {
                            if (String(dados) == "cancelar") escuta.cancelar()
                            else terminarEscuta(escuta.encerrar())
                        }
                    }
                }
            } catch (e: Exception) {
                // O relógio fechou o app, saiu de perto ou o Bluetooth caiu.
            }
            fechar()
        }

        /** A frase acabou: a fala vai para o PC na hora, e o relógio fecha o microfone. */
        private fun terminarEscuta(fim: String) {
            val vale = fim == "silêncio" || fim == "tempo máximo" || fim == "toque"
            if (vale) conexao?.enviar(escuta.wav())
            avisarEscuta(JSONObject().put("fim", fim))
            conexao?.enviar(JSONObject().put("diag", JSONObject()
                .put("motivo", "escuta").put("fim", fim).put("audio_ms", escuta.duracaoMs)))
        }

        private fun avisarEscuta(ev: JSONObject) {
            if (fechada) return
            ev.put("ev", "_escuta")
            escrita.execute { mandar(Tubo.TEXTO, ev.toString().toByteArray()) }
        }

        private fun doPc(ev: JSONObject) {
            if (fechada) return
            escrita.execute {
                if (ev.optString("ev") == "voz") {
                    val pcm = metade(Base64.decode(ev.optString("pcm"), Base64.DEFAULT))
                    val dados = ByteBuffer.allocate(4 + pcm.size).putInt(ev.optInt("taxa", 24000) / 2).put(pcm).array()
                    mandar(Tubo.VOZ, dados)
                } else {
                    mandar(Tubo.TEXTO, ev.toString().toByteArray())
                }
            }
        }

        /** O relógio sabe se o caminho até o PC está de pé (o "_ponte" é só nosso). */
        private fun estado(ok: Boolean, motivo: String) {
            if (fechada) return
            val ev = JSONObject().put("ev", "_ponte").put("conectado", ok).put("motivo", motivo)
            escrita.execute { mandar(Tubo.TEXTO, ev.toString().toByteArray()) }
        }

        private fun mandar(tipo: Int, dados: ByteArray) {
            val s = saida ?: return
            try { Tubo.escrever(s, tipo, dados) } catch (e: Exception) { fechar() }
        }

        fun fechar() {
            if (fechada) return
            fechada = true
            conexao?.fechar()
            runCatching { canais.close(canal) }
            escrita.shutdown()
            synchronized(this@PonteRelogio) {
                if (atual === this) {
                    atual = null
                    manterVivo(false)
                }
            }
        }
    }

    /**
     * O serviço em primeiro plano segura o celular acordado enquanto a
     * conversa do relógio passa por ele (sem isso o Android congela o app em
     * segundo plano). Se o Android não deixar ligar daqui, a ponte segue sem.
     */
    private fun manterVivo(ligar: Boolean): Boolean {
        val i = Intent(app, ServicoPonte::class.java)
        return try {
            if (ligar) app.startForegroundService(i) else app.stopService(i)
            true
        } catch (e: Exception) {
            false
        }
    }
}

/**
 * A voz pela metade da taxa (40 kHz → 20 kHz): a média de cada par de
 * amostras. Metade dos bytes no Bluetooth; no alto-falante do relógio não se
 * ouve a diferença (a média já corta os agudos que dobrariam).
 */
private fun metade(pcm: ByteArray): ByteArray {
    val entrada = ByteBuffer.wrap(pcm).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
    val n = entrada.remaining() / 2
    val saida = ByteBuffer.allocate(n * 2).order(ByteOrder.LITTLE_ENDIAN)
    for (i in 0 until n) {
        saida.putShort(((entrada.get(2 * i).toInt() + entrada.get(2 * i + 1).toInt()) / 2).toShort())
    }
    return saida.array()
}

/** Acordado pelo Google Play services quando o relógio abre o canal "/jarvis". */
class ServicoRelogio : WearableListenerService() {
    override fun onChannelOpened(channel: ChannelClient.Channel) {
        if (channel.path == Tubo.CAMINHO) (application as App).ponte.abrir(channel)
    }
}

/** A notificação "Jarvis no relógio": o celular fica acordado enquanto ela existe. */
class ServicoPonte : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val gerente = getSystemService(NotificationManager::class.java)
        gerente.createNotificationChannel(
            NotificationChannel("relogio", "NOVA no relógio", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Aparece enquanto o relógio conversa com a NOVA pelo celular"
                setShowBadge(false)
            })
        val aviso = Notification.Builder(this, "relogio")
            .setContentTitle("NOVA no relógio")
            .setContentText("Levando a conversa do relógio até o PC")
            .setSmallIcon(R.drawable.ic_notificacao)
            .setOngoing(true)
            .build()
        try {
            startForeground(8, aviso, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        } catch (e: Exception) {
            stopSelf()
        }
        return START_NOT_STICKY
    }
}
