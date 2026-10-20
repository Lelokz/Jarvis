package com.lelokz.jarvis

import android.app.Application
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import com.google.android.gms.tasks.Tasks
import com.google.android.gms.wearable.ChannelClient
import com.google.android.gms.wearable.Wearable
import org.json.JSONObject
import java.io.DataInputStream
import java.io.DataOutputStream
import java.nio.ByteBuffer
import java.util.concurrent.Executors

/**
 * O Jarvis no relógio: o canal até o celular (que repassa ao PC), o ouvido,
 * a voz e o que a tela mostra. UM por processo (`App`).
 *
 * O jeito de usar: o botão abre o app e ele já está ouvindo; fala, ele
 * responde na tela e em voz, e fica mais 7 s ouvindo (como no PC) para a
 * conversa seguir sem apertar nada.
 */
class Relogio(private val app: Application) {
    val estado = mutableStateOf("dormindo")     // o do PC: pensando, falando...
    val ligado = mutableStateOf(false)          // o caminho até o PC está de pé
    val motivo = mutableStateOf("procurando o celular…")
    val ouvindo = mutableStateOf(false)
    val tocando = mutableStateOf(false)
    val esperando = mutableStateOf(false)       // mandou a fala, a resposta não veio
    val nivel = mutableFloatStateOf(0f)
    val voceDisse = mutableStateOf("")
    val resposta = mutableStateOf("")
    val atividade = mutableStateOf("")

    private val principal = Handler(Looper.getMainLooper())
    private val canais = Wearable.getChannelClient(app)
    private val escrita = Executors.newSingleThreadExecutor()
    private val voz = Voz { t -> principal.post { mudouTocando(t) } }
    private val escuta by lazy { Escuta { n -> principal.post { nivel.floatValue = n } } }
    private var canal: ChannelClient.Channel? = null
    private var saida: DataOutputStream? = null
    private var abrindo = false
    private var visivel = false
    // A conversa que começou no relógio: depois da voz, abre a janela de 7 s.
    private var conversando = false
    private var ouvirQuandoLigar = false

    companion object {
        const val DESISTE_MS = 6000L   // abriu e não falou nada
        const val JANELA_MS = 7000L    // depois da resposta
        const val FECHA_MS = 30000L    // tela fora e nada acontecendo: solta o celular
    }

    /** O que o átomo mostra. */
    val estadoVisivel: String
        get() = when {
            !ligado.value -> "sem_conexao"
            ouvindo.value -> "escutando"
            tocando.value -> "falando"
            esperando.value || estado.value == "pensando" || estado.value == "falando" -> "pensando"
            else -> "pronto"
        }

    /** Tem algo acontecendo (a tela não pode apagar no meio). */
    val ocupado: Boolean
        get() = ouvindo.value || tocando.value || esperando.value

    // -- o canal até o celular ------------------------------------------------

    fun aparecer() {
        visivel = true
        principal.removeCallbacks(fecharQuieto)
        abrir()
    }

    fun sumir() {
        visivel = false
        principal.removeCallbacks(fecharQuieto)
        principal.postDelayed(fecharQuieto, FECHA_MS)
    }

    private val fecharQuieto = Runnable {
        if (!visivel && !ocupado) fechar()
        else if (!visivel) sumir()
    }

    private fun abrir() {
        if (canal != null || abrindo) return
        abrindo = true
        motivo.value = "procurando o celular…"
        Thread({
            try {
                val nos = Tasks.await(Wearable.getNodeClient(app).connectedNodes)
                val no = nos.firstOrNull { it.isNearby } ?: nos.firstOrNull()
                if (no == null) {
                    principal.post { abrindo = false; caiu("sem o celular por perto") }
                    return@Thread
                }
                val c = Tasks.await(canais.openChannel(no.id, Tubo.CAMINHO))
                val entrada = DataInputStream(Tasks.await(canais.getInputStream(c)).buffered())
                val s = DataOutputStream(Tasks.await(canais.getOutputStream(c)).buffered())
                principal.post {
                    canal = c; saida = s; abrindo = false
                    motivo.value = "chamando o PC…"
                }
                while (true) {
                    val (tipo, dados) = Tubo.ler(entrada) ?: break
                    when (tipo) {
                        Tubo.TEXTO -> {
                            val ev = try { JSONObject(String(dados)) } catch (e: Exception) { continue }
                            principal.post { receber(ev) }
                        }
                        Tubo.VOZ -> {
                            val b = ByteBuffer.wrap(dados)
                            val taxa = b.getInt()
                            principal.post { chegouVoz(taxa, dados.copyOfRange(4, dados.size)) }
                        }
                    }
                }
            } catch (e: Exception) {
                // O celular sumiu, o Bluetooth caiu, ou o app de lá não respondeu.
            }
            principal.post { abrindo = false; caiu("sem o celular") }
        }, "canal-celular").start()
    }

    private fun caiu(porque: String) {
        val c = canal
        canal = null; saida = null
        if (c != null) runCatching { canais.close(c) }
        ligado.value = false
        motivo.value = porque
        esperando.value = false
        // Com a tela na frente, tenta de novo daqui a pouco.
        if (visivel) principal.postDelayed({ if (visivel) abrir() }, 3000)
    }

    private fun fechar() {
        val c = canal ?: return
        canal = null; saida = null
        runCatching { canais.close(c) }
        ligado.value = false
    }

    private fun mandar(tipo: Int, dados: ByteArray) {
        val s = saida ?: return
        escrita.execute {
            try { Tubo.escrever(s, tipo, dados) } catch (e: Exception) { }
        }
    }

    // -- ouvir e falar --------------------------------------------------------

    /** O app abriu pelo botão (ou o toque no átomo parado): começa a ouvir. */
    fun ouvir() {
        if (!ligado.value) { ouvirQuandoLigar = true; return }
        if (ouvindo.value) return
        voz.parar()
        vibrar()
        conversando = true
        escutar(DESISTE_MS)
    }

    private fun escutar(desisteMs: Long) {
        ouvindo.value = true
        Thread({
            val wav = escuta.ouvir(desisteMs)
            principal.post {
                ouvindo.value = false
                nivel.floatValue = 0f
                if (wav != null) {
                    mandar(Tubo.AUDIO, wav)
                    esperando.value = true
                    resposta.value = ""
                    atividade.value = ""
                } else if (!esperando.value && !tocando.value) {
                    conversando = false // ninguém falou: a conversa acabou
                }
            }
        }, "escuta").start()
    }

    /** O toque no átomo: depende do que ele está fazendo. */
    fun tocou() {
        when {
            !ligado.value -> abrir()
            ouvindo.value -> escuta.encerrar()
            tocando.value -> { voz.parar(); conversando = false }
            else -> ouvir()
        }
    }

    private fun chegouVoz(taxa: Int, pcm: ByteArray) {
        // A voz dele chegando com o microfone aberto esperando: fecha o
        // microfone (o relógio não pode se ouvir). Se o Léo já estava falando,
        // deixa terminar.
        if (ouvindo.value && !escuta.falou) escuta.cancelar()
        voz.tocar(taxa, pcm)
    }

    private fun mudouTocando(t: Boolean) {
        tocando.value = t
        if (t) esperando.value = false
        // Terminou de falar: uns segundos ouvindo sem apertar nada.
        if (!t && conversando && !ouvindo.value) escutar(JANELA_MS)
    }

    private fun vibrar() {
        val v = app.getSystemService(Vibrator::class.java)
        v?.vibrate(VibrationEffect.createOneShot(40, 180))
    }

    // -- o que chega do PC (pelo celular) ---------------------------------------

    private fun receber(ev: JSONObject) {
        when (ev.optString("ev")) {
            "_ponte" -> {
                ligado.value = ev.optBoolean("conectado")
                motivo.value = ev.optString("motivo")
                if (ligado.value && ouvirQuandoLigar) { ouvirQuandoLigar = false; ouvir() }
            }
            "estado" -> estado.value = ev.optString("estado")
            "voce_disse" -> {
                voceDisse.value = ev.optString("texto")
                resposta.value = ""
                atividade.value = ""
            }
            "jarvis_disse" -> {
                // Aviso de WhatsApp é só no PC (decisão do Léo).
                if (ev.optString("acao").startsWith("whatsapp:")) return
                resposta.value = ev.optString("texto")
                atividade.value = ""
                esperando.value = false // a voz vem logo atrás; o "falando" do PC cobre
            }
            "mostrar" -> {
                val titulo = ev.optString("titulo")
                val texto = ev.optString("texto")
                resposta.value = listOf(resposta.value, titulo, texto).filter { it.isNotBlank() }.joinToString("\n\n")
            }
            "atividade" -> atividade.value = ev.optString("texto")
            "aviso" -> when (ev.optString("situacao")) {
                "limite" -> { resposta.value = "O limite do Claude acabou por agora."; esperando.value = false }
                "offline" -> { resposta.value = "O PC está sem internet."; esperando.value = false }
            }
            "erro" -> { resposta.value = ev.optString("motivo"); esperando.value = false }
        }
    }
}
