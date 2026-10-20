package com.lelokz.jarvis

import android.app.Application
import android.util.Base64
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.AndroidViewModel
import org.json.JSONObject

enum class Quem { VOCE, JARVIS, PAINEL, ATIVIDADE, AVISO }

data class Mensagem(val quem: Quem, val texto: String, val titulo: String = "")

/**
 * O estado do app: a conversa, o que o Jarvis está fazendo e a conexão.
 * Sobrevive a girar a tela (é um ViewModel); a conexão fecha só quando o app
 * fecha de verdade.
 */
class JarvisModelo(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("jarvis", Application.MODE_PRIVATE)

    val mensagens = mutableStateListOf<Mensagem>()
    val estado = mutableStateOf("conectando…")
    val conectado = mutableStateOf(false)
    val gravando = mutableStateOf(false)
    val configurado = mutableStateOf(prefs.contains("chave"))

    private val voz = Voz()
    private val gravador = Gravador()
    private var conexao: Conexao? = null

    init {
        if (configurado.value) conectar()
    }

    /** O link da página ("https://jarvis.xxx.ts.net/#chave=..."). */
    fun configurar(link: String): Boolean {
        val l = link.trim()
        val chave = l.substringAfter("chave=", "").substringBefore('&').trim()
        val base = l.substringBefore('#').trimEnd('/')
        if (chave.isEmpty() || !base.startsWith("http")) return false
        prefs.edit().putString("base", base).putString("chave", chave).apply()
        configurado.value = true
        conectar()
        return true
    }

    fun esquecer() {
        conexao?.fechar()
        conexao = null
        prefs.edit().clear().apply()
        mensagens.clear()
        configurado.value = false
    }

    private fun conectar() {
        conexao?.fechar()
        val base = prefs.getString("base", "") ?: return
        val chave = prefs.getString("chave", "") ?: return
        conexao = Conexao(base, chave, ::receber) { ok, motivo ->
            conectado.value = ok
            if (ok) {
                // O histórico vem de novo a cada conexão: começa do zero.
                mensagens.clear()
                estado.value = "conectando…"
            } else {
                estado.value = motivo
            }
        }.also { it.abrir() }
    }

    fun enviarTexto(texto: String) {
        val t = texto.trim()
        if (t.isEmpty()) return
        conexao?.enviar(JSONObject().put("pedir", "falar").put("texto", t))
    }

    fun comecarFala() {
        gravador.comecar()
        gravando.value = true
    }

    fun terminarFala() {
        gravando.value = false
        val wav = gravador.parar() ?: return
        conexao?.enviar(wav)
    }

    private fun receber(ev: JSONObject) {
        when (ev.optString("ev")) {
            "sessao" -> estado.value = "pronto"
            "estado" -> estado.value = when (val e = ev.optString("estado")) {
                "dormindo", "ouvindo" -> "pronto"
                "escutando" -> "escutando"
                "pensando" -> "pensando…"
                "falando" -> "falando"
                else -> e
            }
            "historico" -> {
                val falas = ev.optJSONArray("falas") ?: return
                for (i in 0 until falas.length()) {
                    val f = falas.getJSONObject(i)
                    when (f.optString("quem")) {
                        "voce" -> acrescentar(Mensagem(Quem.VOCE, f.optString("texto")))
                        "jarvis" -> acrescentar(Mensagem(Quem.JARVIS, f.optString("texto")))
                        else -> acrescentar(Mensagem(Quem.PAINEL, f.optString("texto"),
                            f.optString("titulo")))
                    }
                }
            }
            "voce_disse" -> acrescentar(Mensagem(Quem.VOCE, ev.optString("texto")))
            "jarvis_disse" -> acrescentar(Mensagem(Quem.JARVIS, ev.optString("texto")))
            "mostrar" -> acrescentar(Mensagem(Quem.PAINEL, ev.optString("texto"),
                ev.optString("titulo")))
            "atividade" -> {
                // Uma linha só, que vai sendo trocada: é o "o que ele está fazendo".
                val m = Mensagem(Quem.ATIVIDADE, "▸ " + ev.optString("texto"))
                if (mensagens.lastOrNull()?.quem == Quem.ATIVIDADE) mensagens[mensagens.lastIndex] = m
                else mensagens.add(m)
            }
            "voz" -> {
                val pcm = ev.optString("pcm")
                if (pcm.isNotEmpty()) voz.tocar(ev.optInt("taxa", 24000), Base64.decode(pcm, Base64.DEFAULT))
            }
            "aviso" -> when (ev.optString("situacao")) {
                "limite" -> acrescentar(Mensagem(Quem.AVISO, "O limite do Claude acabou por agora."))
                "offline" -> acrescentar(Mensagem(Quem.AVISO, "O PC está sem internet."))
            }
            "erro" -> acrescentar(Mensagem(Quem.AVISO, ev.optString("motivo")))
        }
    }

    private fun acrescentar(m: Mensagem) {
        // A linha de atividade some quando ele volta a falar.
        if (mensagens.lastOrNull()?.quem == Quem.ATIVIDADE && m.quem != Quem.VOCE) {
            mensagens.removeAt(mensagens.lastIndex)
        }
        mensagens.add(m)
    }

    override fun onCleared() {
        conexao?.fechar()
        voz.fechar()
        gravador.parar()
    }
}
