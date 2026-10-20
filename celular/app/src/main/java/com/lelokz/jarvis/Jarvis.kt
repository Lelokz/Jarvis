package com.lelokz.jarvis

import android.app.Application
import android.graphics.Bitmap
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Base64
import android.util.Size
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import android.content.Intent
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

enum class Quem { VOCE, JARVIS, PAINEL, ATIVIDADE, AVISO }

data class Mensagem(
    val quem: Quem,
    val texto: String,
    val titulo: String = "",
    val anexos: List<String> = emptyList(),
    val perguntando: Boolean = false,
)

/** Um anexo do clipe, esperando a mensagem: miniatura, nome e o ✕. */
data class Anexo(
    val local: Int,
    val uri: Uri,
    val nome: String,
    val miniatura: Bitmap?,
    val idServidor: Int? = null,   // o "id" do anexo_ok: já está no PC
    val erro: String = "",
)

/**
 * O app inteiro num lugar só: a conversa, o que o Jarvis está fazendo, a
 * conexão, os anexos e o ouvido do "hey Jarvis". UM por processo (`App`): a
 * tela e o serviço de fundo usam a mesma conexão e a mesma conversa, então o
 * "hey Jarvis" com a tela desligada aparece no chat quando o app abre.
 */
class Jarvis(private val app: Application) {
    private val viewModelScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private val prefs = app.getSharedPreferences("jarvis", Application.MODE_PRIVATE)

    val mensagens = mutableStateListOf<Mensagem>()
    val anexos = mutableStateListOf<Anexo>()
    val estado = mutableStateOf("dormindo")     // o do PC: pensando, falando...
    val conectado = mutableStateOf(false)
    val motivo = mutableStateOf("conectando…")
    val gravando = mutableStateOf(false)
    val tocando = mutableStateOf(false)         // a voz dele saindo AQUI
    val nivel = mutableFloatStateOf(0f)         // volume do microfone, 0 a 1
    val configurado = mutableStateOf(prefs.contains("chave"))
    // O botão de mudo do topo: resposta só em texto (lugar onde não dá para
    // ouvir). Fica salvo entre uma abertura e outra.
    val mudo = mutableStateOf(prefs.getBoolean("mudo", false))
    // "Sempre ouvindo": o "hey Jarvis" no celular, pelo ServicoOuvido.
    val sempreOuvindo = mutableStateOf(prefs.getBoolean("sempre_ouvindo", false))
    private var ouvido: Ouvido? = null

    private val principal = android.os.Handler(android.os.Looper.getMainLooper())
    private val voz = Voz { t -> principal.post { mudouTocando(t) } }
    private val gravador = Gravador { n -> principal.post { nivel.floatValue = n } }
    private var conexao: Conexao? = null
    private var proximoLocal = 1
    // Os anexos enviados esperando o "anexo_ok", na ordem (a porta responde
    // na mesma ordem em que recebeu).
    private val esperandoOk = ArrayDeque<Int>()
    // Os nomes que foram junto da última mensagem: aparecem no balão dela.
    private var nomesEnviados: List<String> = emptyList()

    /** O que o átomo mostra: o estado do PC, mais o que só o celular sabe. */
    val estadoVisivel: String
        get() = when {
            !conectado.value -> "sem_conexao"
            gravando.value -> "escutando"
            tocando.value -> "falando"
            estado.value == "pensando" -> "pensando"
            estado.value == "falando" -> "pensando" // gerando a voz: ainda não chegou aqui
            else -> "pronto"
        }

    init {
        if (configurado.value) conectar()
    }

    /** O link da página ("https://jarvis.xxx.ts.net/#chave=..."), com ou sem texto em volta. */
    fun configurar(link: String): Boolean {
        val chave = Regex("chave=([A-Za-z0-9_-]+)").find(link)?.groupValues?.get(1)
        val base = Regex("https?://[^\\s/#]+").find(link)?.value
        if (chave == null || base == null) return false
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
        anexos.clear()
        configurado.value = false
    }

    private fun conectar() {
        conexao?.fechar()
        val base = prefs.getString("base", "") ?: return
        val chave = prefs.getString("chave", "") ?: return
        conexao = Conexao(base, chave, aoReceber = ::receber) { ok, porque ->
            conectado.value = ok
            motivo.value = porque
            if (ok) {
                avisarMudo()
                // O histórico vem de novo a cada conexão: começa do zero. Os
                // anexos ainda não enviados sobem de novo (a porta nova não
                // conhece os da conexão que caiu).
                mensagens.clear()
                esperandoOk.clear()
                for (a in anexos.toList()) subir(a.copy(idServidor = null, erro = ""))
            }
        }.also { it.abrir() }
    }

    fun alternarMudo() {
        mudo.value = !mudo.value
        prefs.edit().putBoolean("mudo", mudo.value).apply()
        if (mudo.value) voz.parar()
        avisarMudo()
    }

    private fun avisarMudo() {
        conexao?.enviar(JSONObject().put("pedir", "mudo").put("mudo", mudo.value))
    }

    // -- anexos -----------------------------------------------------------

    fun anexar(uri: Uri) {
        val local = proximoLocal++
        viewModelScope.launch {
            val (nome, miniatura) = withContext(Dispatchers.IO) { nomeDe(uri) to miniaturaDe(uri) }
            val a = Anexo(local, uri, nome, miniatura)
            anexos.add(a)
            subir(a)
        }
    }

    private fun subir(a: Anexo) {
        trocar(a)
        viewModelScope.launch {
            val dados = withContext(Dispatchers.IO) {
                try {
                    app.contentResolver.openInputStream(a.uri)?.use { it.readBytes() }
                } catch (e: Exception) { null } catch (e: OutOfMemoryError) { null }
            }
            when {
                dados == null -> trocar(a.copy(erro = "não consegui ler"))
                dados.size > 64 * 1024 * 1024 -> trocar(a.copy(erro = "maior que 64 MB"))
                anexos.none { it.local == a.local } -> {} // tirou antes de subir
                else -> {
                    val c = conexao ?: return@launch
                    c.enviar(JSONObject().put("pedir", "anexo").put("nome", a.nome))
                    c.enviar(dados)
                    esperandoOk.addLast(a.local)
                }
            }
        }
    }

    fun tirarAnexo(a: Anexo) {
        anexos.removeAll { it.local == a.local }
        a.idServidor?.let { conexao?.enviar(JSONObject().put("pedir", "anexo_cancelar").put("id", it)) }
    }

    private fun trocar(a: Anexo) {
        val i = anexos.indexOfFirst { it.local == a.local }
        if (i >= 0) anexos[i] = a
    }

    /** Todos os anexos já chegaram no PC (sem erro)? Só então dá para enviar. */
    val anexosProntos: Boolean
        get() = anexos.all { it.idServidor != null || it.erro.isNotEmpty() }

    private fun usarAnexos() {
        nomesEnviados = anexos.filter { it.idServidor != null }.map { it.nome }
        anexos.clear() // a porta junta ao pedido que vai agora e esquece
    }

    private fun nomeDe(uri: Uri): String = try {
        app.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            ?.use { if (it.moveToFirst()) it.getString(0) else null }
    } catch (e: Exception) { null } ?: "anexo"

    private fun miniaturaDe(uri: Uri): Bitmap? = try {
        app.contentResolver.loadThumbnail(uri, Size(192, 192), null)
    } catch (e: Exception) { null }

    // -- falar e escrever -----------------------------------------------------

    fun enviarTexto(texto: String) {
        val t = texto.trim().ifEmpty { if (anexos.isNotEmpty()) "Olha isso." else return }
        if (!anexosProntos) return
        usarAnexos()
        conexao?.enviar(JSONObject().put("pedir", "falar").put("texto", t))
    }

    private var segurandoAtomo = false

    fun comecarFala() {
        segurandoAtomo = true
        ouvido?.pausado = true // um microfone de cada vez
        gravador.comecar()
        gravando.value = true
    }

    fun terminarFala() {
        gravando.value = false
        nivel.floatValue = 0f
        segurandoAtomo = false
        ouvido?.pausado = tocando.value
        val wav = gravador.parar() ?: return
        usarAnexos()
        conexao?.enviar(wav)
    }

    // -- "sempre ouvindo" -------------------------------------------------------

    /** Liga ou desliga o serviço (o botão do topo). As permissões a tela pede antes. */
    fun alternarSempreOuvindo(ligar: Boolean) {
        sempreOuvindo.value = ligar
        prefs.edit().putBoolean("sempre_ouvindo", ligar).apply()
        val i = Intent(app, ServicoOuvido::class.java)
        if (ligar) {
            if (Build.VERSION.SDK_INT >= 26) app.startForegroundService(i) else app.startService(i)
        } else {
            app.stopService(i)
        }
    }

    /** Chamado pelo serviço, já em primeiro plano e com a permissão do microfone. */
    fun iniciarOuvido() {
        if (ouvido != null) return
        ouvido = Ouvido(
            app,
            aoAcordar = { principal.post { acordou() } },
            aoGravar = { g -> principal.post { gravando.value = g } },
            aoTerminar = { wav -> principal.post { usarAnexos(); conexao?.enviar(wav) } },
            aoNivel = { n -> principal.post { nivel.floatValue = n } },
        ).also { it.pausado = tocando.value; it.ligar() }
        diag("ouvido ligado")
    }

    fun pararOuvido() {
        ouvido?.desligar()
        ouvido = null
    }

    private fun acordou() {
        // Sem voz: vibra, para responder rápido e não fazer barulho.
        val v = app.getSystemService(Vibrator::class.java)
        if (Build.VERSION.SDK_INT >= 26) v?.vibrate(VibrationEffect.createOneShot(60, 200)) else @Suppress("DEPRECATION") v?.vibrate(60)
        diag("hey jarvis")
    }

    private fun mudouTocando(t: Boolean) {
        tocando.value = t
        val o = ouvido ?: return
        // Ele falando: o celular não pode se ouvir. Terminou: uns segundos
        // ouvindo sem precisar do "hey Jarvis", como no PC.
        o.pausado = t || segurandoAtomo
        if (!t) o.abrirJanela()
    }

    /** Um recado para o log do PC (logs/porta-remota.log): o que o app viu. */
    fun diag(motivo: String) {
        conexao?.enviar(JSONObject().put("diag", JSONObject().put("motivo", motivo)))
    }

    // -- o que chega do PC ----------------------------------------------------

    private fun receber(ev: JSONObject) {
        when (ev.optString("ev")) {
            "sessao" -> estado.value = "dormindo"
            "estado" -> estado.value = ev.optString("estado")
            "historico" -> {
                val falas = ev.optJSONArray("falas") ?: return
                for (i in 0 until falas.length()) {
                    val f = falas.getJSONObject(i)
                    when (f.optString("quem")) {
                        "voce" -> acrescentar(Mensagem(Quem.VOCE, f.optString("texto")))
                        "jarvis" -> if (!f.optString("acao").startsWith("whatsapp:"))
                            acrescentar(Mensagem(Quem.JARVIS, f.optString("texto")))
                        else -> acrescentar(Mensagem(Quem.PAINEL, f.optString("texto"),
                            f.optString("titulo")))
                    }
                }
            }
            "voce_disse" -> {
                acrescentar(Mensagem(Quem.VOCE, ev.optString("texto"), anexos = nomesEnviados))
                nomesEnviados = emptyList()
            }
            "jarvis_disse" -> {
                // Aviso de WhatsApp é só no PC (decisão do Léo): aqui nem aparece.
                if (ev.optString("acao").startsWith("whatsapp:")) return
                acrescentar(Mensagem(Quem.JARVIS, ev.optString("texto"),
                    perguntando = ev.optBoolean("perguntando")))
            }
            "mostrar" -> acrescentar(Mensagem(Quem.PAINEL, ev.optString("texto"),
                ev.optString("titulo")))
            "atividade" -> {
                // Uma linha só, que vai sendo trocada: é o "o que ele está fazendo".
                val m = Mensagem(Quem.ATIVIDADE, ev.optString("texto"))
                if (mensagens.lastOrNull()?.quem == Quem.ATIVIDADE) mensagens[mensagens.lastIndex] = m
                else mensagens.add(m)
            }
            "voz" -> {
                val pcm = ev.optString("pcm")
                if (pcm.isNotEmpty() && !mudo.value) voz.tocar(ev.optInt("taxa", 24000), Base64.decode(pcm, Base64.DEFAULT))
            }
            "anexo_ok", "anexo_erro" -> {
                val local = esperandoOk.removeFirstOrNull() ?: return
                val a = anexos.firstOrNull { it.local == local }
                if (a == null) {
                    // Tirou enquanto subia: apaga lá também.
                    if (ev.has("id")) conexao?.enviar(JSONObject().put("pedir", "anexo_cancelar")
                        .put("id", ev.getInt("id")))
                } else if (ev.optString("ev") == "anexo_ok") {
                    trocar(a.copy(idServidor = ev.getInt("id")))
                } else {
                    trocar(a.copy(erro = ev.optString("motivo")))
                }
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


}
