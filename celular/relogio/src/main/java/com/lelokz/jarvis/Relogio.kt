package com.lelokz.jarvis

import android.app.Application
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
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
 * O jeito de usar (o Léo, 27/10/2026): o app abre dormindo (o átomo cinza).
 * Um toque no átomo e ele ouve; fala, ele responde na tela e em voz, e fica
 * mais 4 s ouvindo para a conversa seguir sem tocar. Sem conversa, volta a
 * dormir, com o app aberto (a tela apaga sozinha). Tocar enquanto ouve manda
 * na hora; tocar enquanto pensa ou fala para tudo e volta a ouvir.
 */
class Relogio(private val app: Application) {
    val estado = mutableStateOf("dormindo")     // o do PC: pensando, falando...
    val ligado = mutableStateOf(false)          // o caminho até o PC está de pé
    val motivo = mutableStateOf("procurando o celular…")
    val ouvindo = mutableStateOf(false)
    val tocando = mutableStateOf(false)
    val esperando = mutableStateOf(false)       // mandou a fala, a resposta não veio
    val nivel = mutableFloatStateOf(0f)
    // A conversa desde que o app abriu, a mais nova primeiro (fica logo embaixo do átomo).
    val conversa = mutableStateListOf<Troca>()
    val atividade = mutableStateOf("")
    // Quem responde: a MESMA do PC e do app (o PC manda no "cerebro").
    val persona = mutableStateOf("jarvis")
    val corPersona = mutableStateOf("")         // "#rrggbb" da Friday (o Léo escolhe no PC)

    private val principal = Handler(Looper.getMainLooper())
    private val canais = Wearable.getChannelClient(app)
    private val escrita = Executors.newSingleThreadExecutor()
    private val voz = Voz { t -> principal.post { mudouTocando(t) } }
    private val microfone = Microfone(
        aoPedaco = { pcm -> mandar(Tubo.FALA_PEDACO, pcm) },
        aoNivel = { n -> principal.post { nivel.floatValue = n } },
    )
    // O celular já ouviu fala nesta escuta (a voz dele chegando só cancela se não).
    private var falouNaEscuta = false
    // Quando a frase acabou: a demora até o 1º som vai para o log do PC.
    private var fimDaFala = 0L
    private var canal: ChannelClient.Channel? = null
    private var saida: DataOutputStream? = null
    private var abrindo = false
    private var visivel = false
    // A conversa que começou no relógio: depois da voz, abre a janela de 4 s.
    private var conversando by mutableStateOf(false)   // estado: o átomo depende dele
    // Disse "dorme aí": deixa ele falar o "Tá bom." e volta a dormir.
    private var indoDormir = false
    // Mandou parar: o resto da voz que ainda vinha do PC não toca.
    private var descartarVoz = false

    /** Uma ida e volta: o que você disse e o que ele respondeu. */
    data class Troca(val voce: String, val resposta: String)

    /** A resposta da troca de agora (`juntar`: soma ao que já tinha, como o "mostrar"). */
    private fun responder(texto: String, juntar: Boolean = false) {
        if (texto.isBlank()) return
        val agora = conversa.firstOrNull()
        if (agora == null) { conversa.add(0, Troca("", texto)); return }
        val nova = if (juntar && agora.resposta.isNotBlank()) agora.resposta + "\n\n" + texto else texto
        conversa[0] = agora.copy(resposta = nova)
    }

    companion object {
        const val TROCAS = 20          // a conversa guardada na tela
        const val DESISTE_MS = 6000L   // abriu e não falou nada
        const val JANELA_MS = 4000L    // depois da resposta (7 s era demais, o Léo)
        const val FECHA_MS = 30000L    // tela fora e nada acontecendo: solta o celular
    }

    /** O que o átomo mostra ("dormindo": ligado, esperando o toque). */
    val estadoVisivel: String
        get() = when {
            !ligado.value -> "sem_conexao"
            ouvindo.value -> "escutando"
            tocando.value -> "falando"
            // Entre o texto chegar e a voz começar, o "pensando"/"falando" do PC cobre.
            esperando.value || (conversando && estado.value in setOf("pensando", "falando")) -> "pensando"
            else -> "dormindo"
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
        if (ouvindo.value) { microfone.desligar(); ouvindo.value = false }
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

    /** O toque no átomo dormindo: começa a ouvir. */
    private fun ouvir() {
        if (!ligado.value || ouvindo.value) return
        voz.parar()
        vibrar()
        conversando = true
        escutar(DESISTE_MS)
    }

    /** Liga o microfone indo para o celular; o celular avisa quando a frase acabou (`_escuta`). */
    private fun escutar(desisteMs: Long) {
        ouvindo.value = true
        falouNaEscuta = false
        mandar(Tubo.FALA_INICIO, JSONObject().put("desiste_ms", desisteMs).toString().toByteArray())
        microfone.ligar()
        // O celular não respondeu (app velho, travou): não fica preso em "ouvindo".
        principal.removeCallbacks(semResposta)
        principal.postDelayed(semResposta, Microfone.SEGURANCA_MS + 1000)
    }

    private val semResposta = Runnable {
        if (ouvindo.value) { cancelarEscuta(); motivo.value = "o celular não respondeu" }
    }

    /** O celular decidiu: a frase acabou (ou ninguém falou). */
    private fun escutaAcabou(fim: String) {
        principal.removeCallbacks(semResposta)
        microfone.desligar()
        ouvindo.value = false
        nivel.floatValue = 0f
        if (fim == "silêncio" || fim == "tempo máximo" || fim == "toque") {
            descartarVoz = false   // a voz que vier agora é a resposta desta fala
            esperando.value = true
            atividade.value = ""
            fimDaFala = System.currentTimeMillis()
        } else if (!esperando.value && !tocando.value) {
            conversando = false // ninguém falou: a conversa acabou
        }
    }

    /** Fecha o microfone sem mandar nada (a voz dele chegou, ou "dorme aí"). */
    private fun cancelarEscuta() {
        if (!ouvindo.value) return
        principal.removeCallbacks(semResposta)
        mandar(Tubo.FALA_FIM, "cancelar".toByteArray())
        microfone.desligar()
        ouvindo.value = false
        nivel.floatValue = 0f
    }

    /** O toque no nome: Jarvis ⇄ Friday. Troca no PC e no app também. */
    fun trocarPersona() {
        if (!ligado.value) return
        val nova = if (persona.value == "friday") "jarvis" else "friday"
        persona.value = nova
        mandar(Tubo.TEXTO, JSONObject().put("pedir", "cerebro").put("persona", nova).toString().toByteArray())
    }

    /** O toque no átomo: depende do que ele está fazendo. */
    fun tocou() {
        when {
            !ligado.value -> abrir()
            ouvindo.value -> mandar(Tubo.FALA_FIM, "toque".toByteArray())   // manda na hora
            tocando.value || esperando.value -> parar()
            else -> ouvir()
        }
    }

    /** Pensando ou falando: para tudo (aqui e no PC) e volta a ouvir. */
    private fun parar() {
        descartarVoz = true
        voz.parar()
        mandar(Tubo.TEXTO, JSONObject().put("pedir", "parar").toString().toByteArray())
        esperando.value = false
        indoDormir = false
        principal.removeCallbacks(dormirAgora)
        vibrar()
        conversando = true
        escutar(DESISTE_MS)
    }

    private fun chegouVoz(taxa: Int, pcm: ByteArray) {
        if (descartarVoz) return
        // A voz dele chegando com o microfone aberto esperando: fecha o
        // microfone (o relógio não pode se ouvir). Se o Léo já estava falando,
        // deixa terminar.
        if (ouvindo.value && !falouNaEscuta) cancelarEscuta()
        if (fimDaFala > 0) {
            val ms = System.currentTimeMillis() - fimDaFala
            fimDaFala = 0
            mandar(Tubo.TEXTO, JSONObject().put("diag", JSONObject().put("motivo", "demora no relógio")
                .put("fim_da_fala_ate_1o_som_ms", ms).put("1a_voz_kb", pcm.size / 1024)).toString().toByteArray())
        }
        voz.tocar(taxa, pcm)
    }

    private fun mudouTocando(t: Boolean) {
        tocando.value = t
        if (t) esperando.value = false
        if (!t && indoDormir) { dormirAgora(); return }
        // Terminou de falar: uns segundos ouvindo sem apertar nada.
        if (!t && conversando && !ouvindo.value) escutar(JANELA_MS)
    }

    private val dormirAgora = Runnable { dormirAgora() }

    private fun dormirAgora() {
        principal.removeCallbacks(dormirAgora)
        if (!indoDormir) return
        indoDormir = false
        esperando.value = false
        conversando = false
        cancelarEscuta()
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
            }
            "_escuta" -> {
                if (ev.optBoolean("falou")) falouNaEscuta = true
                if (ev.has("fim") && ouvindo.value) escutaAcabou(ev.optString("fim"))
            }
            "estado" -> estado.value = ev.optString("estado")
            "cerebro" -> if (ev.has("persona")) {
                persona.value = ev.optString("persona", "jarvis")
                corPersona.value = ev.optString("cor_persona")
            }
            "voce_disse" -> {
                val disse = ev.optString("texto")
                conversa.add(0, Troca(disse, ""))
                while (conversa.size > TROCAS) conversa.removeAt(conversa.lastIndex)
                if (eComandoDeDormir(disse)) {
                    // O PC dorme sozinho (assistente.py); aqui é parar de ouvir
                    // e dormir depois do "Tá bom.". Sem voz em 4 s, dorme igual.
                    conversando = false
                    indoDormir = true
                    cancelarEscuta()
                    principal.postDelayed(dormirAgora, 4000)
                }
                atividade.value = ""
            }
            "jarvis_disse" -> {
                // Aviso de WhatsApp é só no PC (decisão do Léo).
                if (ev.optString("acao").startsWith("whatsapp:")) return
                responder(ev.optString("texto"))
                atividade.value = ""
                esperando.value = false // a voz vem logo atrás; o "falando" do PC cobre
            }
            "mostrar" -> {
                responder(listOf(ev.optString("titulo"), ev.optString("texto")).filter { it.isNotBlank() }
                    .joinToString("\n\n"), juntar = true)
            }
            "atividade" -> atividade.value = ev.optString("texto")
            "aviso" -> when (ev.optString("situacao")) {
                "limite" -> { responder("O limite do Claude acabou por agora."); esperando.value = false }
                "offline" -> { responder("O PC está sem internet."); esperando.value = false }
            }
            "erro" -> { responder(ev.optString("motivo")); esperando.value = false }
        }
    }
}

/**
 * "Dorme aí" e companhia: a MESMA lista do PC (`COMANDOS_DE_DORMIR`, no
 * assistente.py), contra a fala inteira, sem acento, pontuação e artigo.
 * "Dorme." casa; "o arquivo dorme na pasta" não.
 */
private val COMANDOS_DE_DORMIR = setOf(
    "dorme", "dorme ai", "dorme jarvis", "jarvis dorme", "vai dormir",
    "pode dormir", "pode ir dormir", "vai dormir jarvis", "pode dormir jarvis",
    "dormir", "descansa", "vai descansar", "pode descansar",
    "tchau", "tchau jarvis", "valeu pode dormir", "obrigado pode dormir",
    "volta dormir", "volta pra dormir", "volta para dormir",
    "dormi",  // o Whisper às vezes ouve o "dorme" assim (27/10/2026)
    "dorme friday", "friday dorme", "vai dormir friday", "pode dormir friday", "tchau friday",
)
private val SUPERFLUAS = setOf("o", "a", "os", "as", "um", "uma", "de", "do", "da", "no", "na")

fun eComandoDeDormir(texto: String): Boolean {
    val semAcento = java.text.Normalizer.normalize(texto.lowercase(), java.text.Normalizer.Form.NFD)
        .replace(Regex("\\p{Mn}+"), "")
    val limpo = semAcento.replace(Regex("[^\\w\\s]"), " ").trim().split(Regex("\\s+"))
    val palavras = limpo.filter { it.isNotEmpty() && it !in SUPERFLUAS }
    return palavras.joinToString(" ") in COMANDOS_DE_DORMIR
}
