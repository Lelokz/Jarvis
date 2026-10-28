package com.lelokz.jarvis

import android.app.Application
import android.graphics.Bitmap
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Base64
import android.util.Size
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableIntStateOf
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
import okhttp3.MediaType.Companion.toMediaType
import okio.source
import org.json.JSONObject

enum class Quem { VOCE, JARVIS, PAINEL, ATIVIDADE, AVISO }

data class Mensagem(
    val quem: Quem,
    val texto: String,
    val titulo: String = "",
    val anexos: List<String> = emptyList(),
    val perguntando: Boolean = false,
    val opcoes: List<String> = emptyList(),   // as da pergunta: viram botões
    val origem: String = "",                  // voz, texto, celular...
    val quando: Double = System.currentTimeMillis() / 1000.0,
    val passos: List<String> = emptyList(),   // ATIVIDADE: o que ele fez, em ordem
    val escrevendo: Boolean = false,          // o texto ainda está chegando
    val bloco: Int = 0,
)

/** Uma conversa da gaveta: uma sessão do Claude Code no PC. */
/** Uma memória da lista (beta 0.14.5): a do Jarvis/Friday, um grupo, uma pessoa. */
/** O estado de uma conexão (aba Conexões dos Ajustes; vem do PC, jarvis/conexoes.py). */
data class EstadoConexao(val id: String, val estado: String, val detalhe: String)

data class MemoriaItem(val id: String, val titulo: String, val tipo: String, val atualizado: String)

/** A memória aberta para editar; `versao` é a que veio do PC (para o conflito). */
data class MemoriaAberta(val id: String, val titulo: String, val texto: String, val versao: String)

data class Conversa(val id: String, val titulo: String, val quando: Double, val origem: String,
                    val fixada: Boolean = false)

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

    val mensagens = mutableStateListOf<Mensagem>()       // a conversa de agora
    val mensagensVendo = mutableStateListOf<Mensagem>()  // uma antiga, aberta na gaveta
    val anexos = mutableStateListOf<Anexo>()
    // A janela nova (beta 0.6): as conversas, o que está escolhido e o uso.
    val conversas = mutableStateListOf<Conversa>()
    val conversaAtual = mutableStateOf("")
    val vendo = mutableStateOf("")           // "" = a de agora; senão, o id da antiga
    val pagina = mutableStateOf("chat")      // "chat", "memoria", "ajustes"
    val abaAjustes = mutableStateOf("")      // a categoria aberta nos Ajustes ("" = a lista)
    val modelo = mutableStateOf("auto")
    val esforco = mutableStateOf("medium")
    val memoriaTexto = mutableStateOf("")
    // A aba Memórias (beta 0.14.5): a lista, a aberta, e o conflito (o Jarvis
    // mudou o arquivo enquanto o Léo editava: o texto e a versão dele).
    val memorias = mutableStateListOf<MemoriaItem>()
    val memoriasCarregando = mutableStateOf(false)
    val memoriaAberta = mutableStateOf<MemoriaAberta?>(null)
    val memoriaConflito = mutableStateOf<Pair<String, String>?>(null)
    val memoriaSalvando = mutableStateOf(false)
    val usoCinco = mutableStateOf(-1.0)
    val voltaCinco = mutableStateOf(0.0)
    val usoSemana = mutableStateOf(-1.0)
    val voltaSemana = mutableStateOf(0.0)
    // Atualização: o versionCode mais novo no PC (0 = está em dia) e se o
    // aviso grande está aberto. O grande sai uma vez por versão; depois fica
    // só o retângulo no topo.
    val atualizacao = mutableStateOf(0)
    // O download da atualização: -1 = parado; 0 a 1 = baixando; 2 = instalando.
    // Enquanto não for -1, tocar de novo não começa outro (beta 0.11.5).
    val atualizando = mutableStateOf(-1f)
    // O pedido de desbloquear o PC esperando o Sim/Não (o id), ou "".
    val desbloqueio = mutableStateOf("")
    // Como o Jarvis chama quem usa e o nome do computador (vêm do PC, no
    // evento "ajustes"; beta 0.12.5). Guardados para o app abrir já com eles.
    val nomeUsuario = mutableStateOf(prefs.getString("nome_usuario", "") ?: "")
    val nomePc = mutableStateOf(prefs.getString("nome_pc", "") ?: "")
    // O Jarvis no grupo da família (beta 0.13.0): configurado no PC? ligado?
    val temGrupo = mutableStateOf(prefs.getBoolean("tem_grupo", false))
    val grupoLigado = mutableStateOf(false)
    // O volume da voz NO PC e o estado das conexões (do evento "ajustes"; beta 0.17.0).
    val volumeVoz = mutableIntStateOf(100)
    // O PC tem o perfil da voz do dono (null = PC antigo, que não manda).
    val reconheceVoz = mutableStateOf<Boolean?>(null)
    val conexoes = mutableStateOf<List<EstadoConexao>>(emptyList())
    // O pedido de alguém do grupo esperando o Sim: (id, quem, pedido).
    val pedidoGrupo = mutableStateOf<Triple<String, String, String>?>(null)
    val avisoAtualizacao = mutableStateOf(false)
    val aviso = mutableStateOf("")           // recado rápido (erro, "mandada pra lixeira")
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
        Novidades.agendar(app)
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
        conexao = Conexao(base, chave, janela = true, aoReceber = ::receber) { ok, porque ->
            conectado.value = ok
            motivo.value = porque
            if (ok) {
                avisarMudo()
                viewModelScope.launch(Dispatchers.IO) { Novidades.buscar(app); conferirVersao(); conferirDesbloqueio(); conferirPedidos() }
                // O histórico vem de novo a cada conexão: começa do zero. Os
                // anexos ainda não enviados sobem de novo (a porta nova não
                // conhece os da conexão que caiu).
                mensagens.clear()
                esperandoOk.clear()
                pedirConversas()
                for (a in anexos.toList()) subir(a.copy(idServidor = null, erro = ""))
            }
        }.also { it.abrir() }
    }

    private suspend fun conferirVersao() {
        val noPc = Novidades.versaoNoPc(app) ?: return
        val instalada = app.packageManager.getPackageInfo(app.packageName, 0).longVersionCode
        withContext(Dispatchers.Main) {
            atualizacao.value = if (noPc > instalada) noPc else 0
            if (atualizacao.value != 0 && prefs.getInt("atualizacao_avisada", 0) != noPc) avisoAtualizacao.value = true
        }
    }

    /** Tem pedido de desbloquear esperando? (ao conectar e ao tocar na notificação) */
    fun conferirPedidos() {
        viewModelScope.launch(Dispatchers.IO) {
            val p = Novidades.pedidoPendente(app)
            withContext(Dispatchers.Main) { pedidoGrupo.value = p }
        }
    }

    fun responderPedido(sim: Boolean) {
        val p = pedidoGrupo.value ?: return
        pedidoGrupo.value = null
        viewModelScope.launch(Dispatchers.IO) {
            val r = Novidades.responderPedido(app, p.first, sim)
            withContext(Dispatchers.Main) {
                aviso.value = when (r) {
                    "aprovado" -> "Liberado: o Jarvis vai fazer."
                    "recusado" -> "Recusado. O Jarvis avisa no grupo."
                    "expirou" -> "Esse pedido já expirou."
                    else -> "Sem conexão com o PC."
                }
            }
        }
    }

    /** Os ajustes de novo (o estado das conexões de agora). */
    fun pedirAjustes() {
        conexao?.enviar(JSONObject().put("pedir", "ajustes"))
    }

    fun mudarVolumeVoz(v: Int) {
        volumeVoz.intValue = v
        conexao?.enviar(JSONObject().put("pedir", "ajustes").put("volume_voz", v.coerceIn(0, 100)))
    }

    fun alternarGrupo() {
        conexao?.enviar(JSONObject().put("pedir", "ajustes").put("grupo_ligado", !grupoLigado.value))
    }

    fun conferirDesbloqueio() {
        viewModelScope.launch(Dispatchers.IO) {
            val id = Novidades.desbloqueioPendente(app) ?: ""
            withContext(Dispatchers.Main) { desbloqueio.value = id }
        }
    }

    fun responderDesbloqueio(sim: Boolean) {
        val id = desbloqueio.value
        desbloqueio.value = ""
        if (id.isEmpty()) return
        viewModelScope.launch(Dispatchers.IO) {
            val r = Novidades.responderDesbloqueio(app, id, sim)
            withContext(Dispatchers.Main) {
                aviso.value = when (r) {
                    "desbloqueado" -> "PC desbloqueado."
                    "recusado" -> "Tudo bem, o PC continua bloqueado."
                    "expirou" -> "Esse pedido já expirou."
                    "falhou" -> "Não consegui desbloquear o PC."
                    else -> "Sem conexão com o PC."
                }
            }
        }
    }

    /** Fechou o aviso grande (sim ou não): não volta a abrir sozinho nesta versão. */
    fun fecharAvisoAtualizacao(atualizar: Boolean) {
        avisoAtualizacao.value = false
        prefs.edit().putInt("atualizacao_avisada", atualizacao.value).apply()
        if (atualizar) {
            if (atualizando.value >= 0f) return  // já está baixando ou instalando
            val base = prefs.getString("base", "")?.trimEnd('/') ?: return
            // Primeira vez: o Android pede para liberar o Jarvis a instalar.
            if (!Atualizador.podeInstalar(app)) {
                aviso.value = "Libera a NOVA e toca em \"Atualização disponível\" de novo."
                return
            }
            atualizando.value = 0f
            viewModelScope.launch(Dispatchers.IO) {
                val erro = Atualizador.baixarEInstalar(app, base) { p ->
                    viewModelScope.launch(Dispatchers.Main) { atualizando.value = p }
                }
                withContext(Dispatchers.Main) {
                    if (erro.isNotEmpty()) { aviso.value = erro; atualizando.value = -1f }
                    else atualizando.value = 2f
                }
            }
        }
    }

    /** O mesmo "Seu nome" da janela: o nome é um só, guardado no PC. */
    fun mudarNome(nome: String) {
        conexao?.enviar(JSONObject().put("pedir", "ajustes").put("nome", nome.trim().take(30)))
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

    // -- compartilhar com o Jarvis (beta 0.10.5) ------------------------------

    /** Texto ou link que chegou por "Compartilhar": vai para a barra de escrever. */
    val textoCompartilhado = mutableStateOf("")

    /** O "Compartilhar → Jarvis" de outro app: anexos viram anexos, link e texto
     *  vão para a barra. Ele escreve o que quer junto e manda. */
    fun receberCompartilhado(intent: Intent) {
        if (!configurado.value) return
        val uris = mutableListOf<Uri>()
        @Suppress("DEPRECATION")
        when (intent.action) {
            Intent.ACTION_SEND -> (if (Build.VERSION.SDK_INT >= 33)
                intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                else intent.getParcelableExtra(Intent.EXTRA_STREAM) as? Uri)?.let { uris += it }
            Intent.ACTION_SEND_MULTIPLE -> (if (Build.VERSION.SDK_INT >= 33)
                intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
                else intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM))?.let { uris += it }
            else -> return
        }
        // Sempre na conversa de agora.
        pagina.value = "chat"
        if (vendo.value.isNotEmpty()) abrir("")
        uris.take(10).forEach { anexar(it) }
        val texto = listOfNotNull(intent.getStringExtra(Intent.EXTRA_SUBJECT),
            intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString())
            .filter { it.isNotBlank() }.distinct().joinToString("\n")
        if (texto.isNotBlank()) textoCompartilhado.value = texto
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

    // Os anexos sobem pelo /anexo da porta, aos pedaços (beta 0.11.5): o vídeo
    // de um minuto passa de 64 MB e não cabia na memória pelo WebSocket.
    private val clienteDeAnexos = okhttp3.OkHttpClient.Builder()
        .writeTimeout(10, java.util.concurrent.TimeUnit.MINUTES)
        .readTimeout(2, java.util.concurrent.TimeUnit.MINUTES).build()
    private val MAX_ANEXO = 500L * 1024 * 1024

    /** O token do arquivo no PC, ou o erro (começando com "!"). Roda fora da thread principal. */
    private fun subirArquivo(a: Anexo): String {
        val base = prefs.getString("base", null)?.trimEnd('/') ?: return "!sem o link do PC"
        val chave = prefs.getString("chave", null) ?: return "!sem a chave"
        val tamanho = try {
            app.contentResolver.query(a.uri, arrayOf(OpenableColumns.SIZE), null, null, null)
                ?.use { if (it.moveToFirst() && !it.isNull(0)) it.getLong(0) else -1L } ?: -1L
        } catch (e: Exception) { -1L }
        if (tamanho > MAX_ANEXO) return "!maior que 500 MB"
        val corpo = object : okhttp3.RequestBody() {
            override fun contentType() = "application/octet-stream".toMediaType()
            override fun contentLength() = tamanho
            override fun writeTo(sink: okio.BufferedSink) {
                app.contentResolver.openInputStream(a.uri)?.use { sink.writeAll(it.source()) }
                    ?: throw java.io.IOException("não abriu")
            }
        }
        val url = "$base/anexo?nome=" + Uri.encode(a.nome)
        return try {
            clienteDeAnexos.newCall(okhttp3.Request.Builder().url(url).post(corpo)
                .header("Authorization", "Bearer $chave").build()).execute().use { r ->
                val j = JSONObject(r.body?.string() ?: "{}")
                if (r.isSuccessful) j.optString("token") else "!" + j.optString("erro", "o PC recusou")
            }
        } catch (e: Exception) {
            "!não consegui mandar"
        }
    }

    private fun subir(a: Anexo) {
        trocar(a)
        viewModelScope.launch {
            val token = withContext(Dispatchers.IO) { subirArquivo(a) }
            when {
                token.startsWith("!") || token.isEmpty() -> trocar(a.copy(erro = token.removePrefix("!").ifEmpty { "falhou" }))
                anexos.none { it.local == a.local } -> {} // tirou enquanto subia (o PC apaga em 14 dias)
                else -> {
                    val c = conexao ?: return@launch
                    c.enviar(JSONObject().put("pedir", "anexo_pronto").put("token", token).put("nome", a.nome))
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
        mandarOuEsperar(JSONObject().put("pedir", "falar").put("texto", t))
    }

    // -- a janela nova: conversas, cérebro, Parar -------------------------------

    // Escreveu (ou falou) numa conversa antiga: primeiro o PC volta pra ela, e
    // o pedido só vai quando a "conversa_atual" chegar com esse id. Mandar
    // junto faria a fala sumir da tela quando a conversa fosse recarregada.
    private var esperandoContinuar = ""
    private var pendente: Any? = null   // JSONObject (texto) ou ByteArray (fala)

    private fun mandarOuEsperar(pedido: Any) {
        val antiga = vendo.value
        if (antiga.isEmpty()) {
            enviarAgora(pedido)
            return
        }
        esperandoContinuar = antiga
        pendente = pedido
        conexao?.enviar(JSONObject().put("pedir", "continuar").put("id", antiga))
    }

    private fun enviarAgora(pedido: Any) {
        when (pedido) {
            is JSONObject -> conexao?.enviar(pedido)
            is ByteArray -> conexao?.enviar(pedido)
        }
    }

    fun pedirConversas() { conexao?.enviar(JSONObject().put("pedir", "conversas")) }

    fun abrir(id: String) {
        pagina.value = "chat"
        if (id.isEmpty() || id == conversaAtual.value) { vendo.value = ""; return }
        vendo.value = id
        mensagensVendo.clear()
        conexao?.enviar(JSONObject().put("pedir", "abrir").put("id", id))
    }

    fun novaConversa() {
        pagina.value = "chat"
        if (vendo.value.isEmpty() && mensagens.isEmpty()) return  // já está num chat novo
        vendo.value = ""
        conexao?.enviar(JSONObject().put("pedir", "nova"))
    }

    fun renomear(id: String, titulo: String) {
        if (titulo.isBlank()) return
        conexao?.enviar(JSONObject().put("pedir", "renomear").put("id", id).put("titulo", titulo.trim()))
    }

    /** Fixa (ou solta) no topo da gaveta, como na janela do PC (beta 0.12.0). */
    fun fixar(id: String, sim: Boolean) {
        conexao?.enviar(JSONObject().put("pedir", "fixar").put("id", id).put("fixar", sim))
    }

    fun apagar(id: String) {
        if (vendo.value == id) vendo.value = ""
        conexao?.enviar(JSONObject().put("pedir", "apagar").put("id", id))
        aviso.value = "Conversa mandada pra lixeira"
    }

    fun escolherModelo(m: String) {
        modelo.value = m
        conexao?.enviar(JSONObject().put("pedir", "cerebro").put("modelo", m))
    }

    fun escolherEsforco(e: String) {
        esforco.value = e
        conexao?.enviar(JSONObject().put("pedir", "cerebro").put("esforco", e))
    }

    // O Parar cala aqui na hora (o que já chegou e está na fila) e manda o PC
    // parar; o que ainda vier no caminho, nos próximos instantes, não toca.
    private var calarVozAte = 0.0
    fun parar() {
        voz.parar()
        calarVozAte = agora() + 1.5
        conexao?.enviar(JSONObject().put("pedir", "parar"))
    }

    fun pedirMemoria() { pedirMemorias() }

    /** A lista das memórias (a aba Memórias). */
    fun pedirMemorias() {
        memoriaAberta.value = null
        memoriaConflito.value = null
        memoriasCarregando.value = memorias.isEmpty()
        conexao?.enviar(JSONObject().put("pedir", "memorias"))
    }

    fun abrirMemoria(item: MemoriaItem) {
        memoriaAberta.value = MemoriaAberta(item.id, item.titulo, "", "")
        conexao?.enviar(JSONObject().put("pedir", "ler_memoria").put("id", item.id))
    }

    /** Salva o que foi editado; `versao` vazia = a que abriu (o normal). */
    fun salvarMemoria(texto: String, versao: String = "") {
        val aberta = memoriaAberta.value ?: return
        memoriaSalvando.value = true
        memoriaConflito.value = null
        val enviou = conexao?.enviar(JSONObject().put("pedir", "salvar_memoria").put("id", aberta.id)
            .put("texto", texto).put("versao", versao.ifEmpty { aberta.versao }))
        if (enviou != true) { memoriaSalvando.value = false; aviso.value = "Sem conexão com o PC: não salvou" }
    }

    /** No conflito: fica com a versão que o Jarvis escreveu. */
    fun usarMemoriaDoJarvis() {
        val (texto, versao) = memoriaConflito.value ?: return
        memoriaAberta.value = memoriaAberta.value?.copy(texto = texto, versao = versao)
        memoriaConflito.value = null
    }

    /** Quem responde: "jarvis" ou "friday" (o seletor; vale também para a voz no PC). */
    fun escolherPersona(p: String) {
        personaAtiva.value = p
        conexao?.enviar(JSONObject().put("pedir", "cerebro").put("persona", p))
    }

    /** Ele está trabalhando no pedido ou falando (o enviar vira Parar). */
    val trabalhando: Boolean
        get() = conectado.value && vendo.value.isEmpty() &&
            (estado.value == "pensando" || estado.value == "falando")

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
        mandarOuEsperar(wav)
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
    // As mesmas regras da janela do PC (jarvis/interface/qml/Falas.qml).

    // A resposta formatada chega como painel sem título e, logo depois, a
    // versão FALADA dela: essa não entra (até este instante).
    private var pularFalaAte = 0.0
    private fun agora() = System.currentTimeMillis() / 1000.0

    private fun receber(ev: JSONObject) {
        when (ev.optString("ev")) {
            "sessao" -> estado.value = "dormindo"
            "estado" -> estado.value = ev.optString("estado")
            "historico" -> preencher(mensagens, ev.optJSONArray("falas"))
            "conversa_atual" -> {
                val id = ev.optString("id")
                conversaAtual.value = id
                if (ev.has("falas")) {
                    preencher(mensagens, ev.optJSONArray("falas"))
                    if (vendo.value == id) vendo.value = ""
                    if (esperandoContinuar == id) {
                        esperandoContinuar = ""
                        vendo.value = ""
                        pendente?.let { enviarAgora(it) }
                        pendente = null
                    }
                }
                pedirConversas()
            }
            "conversas" -> {
                val lista = ev.optJSONArray("lista") ?: return
                conversas.clear()
                for (i in 0 until lista.length()) {
                    val c = lista.getJSONObject(i)
                    conversas.add(Conversa(c.optString("id"), c.optString("titulo").ifEmpty { "Conversa" },
                        c.optDouble("quando", 0.0), c.optString("origem"), c.optBoolean("fixada", false)))
                }
            }
            "conversa" -> if (ev.optString("id") == vendo.value) preencher(mensagensVendo, ev.optJSONArray("falas"))
            "cerebro" -> {
                modelo.value = ev.optString("modelo", modelo.value)
                esforco.value = ev.optString("esforco", esforco.value)
                // A persona ativa (beta 0.14.5): "hey Friday" no PC deixa o app rosa também.
                personaAtiva.value = ev.optString("persona", "jarvis")
                ev.optString("cor_persona").takeIf { it.length == 7 && it.startsWith("#") }?.let {
                    runCatching { corDaFriday.value = androidx.compose.ui.graphics.Color(android.graphics.Color.parseColor(it)) }
                }
            }
            "memorias" -> {
                memoriasCarregando.value = false
                memorias.clear()
                val lista = ev.optJSONArray("lista")
                for (i in 0 until (lista?.length() ?: 0)) {
                    val m = lista!!.getJSONObject(i)
                    memorias.add(MemoriaItem(m.optString("id"), m.optString("titulo"), m.optString("tipo"), m.optString("atualizado")))
                }
            }
            "memoria_aberta" -> if (ev.optString("id") == memoriaAberta.value?.id) {
                memoriaAberta.value = MemoriaAberta(ev.optString("id"), ev.optString("titulo"), ev.optString("texto"), ev.optString("versao"))
            }
            "memoria_salva" -> if (ev.optString("id") == memoriaAberta.value?.id) {
                memoriaSalvando.value = false
                if (ev.optBoolean("ok")) {
                    memoriaAberta.value = memoriaAberta.value?.copy(texto = ev.optString("texto"), versao = ev.optString("versao"))
                    aviso.value = "Memória salva"
                } else if (ev.optBoolean("conflito")) {
                    memoriaConflito.value = ev.optString("texto") to ev.optString("versao")
                }
            }
            "desbloqueio" -> {
                desbloqueio.value = ev.optString("id")
                Novidades.notificarDesbloqueio(app)
            }
            "aprovacao" -> {
                pedidoGrupo.value = Triple(ev.optString("id"), ev.optString("quem"), ev.optString("pedido"))
                Novidades.notificarPedido(app, ev.optString("quem"), ev.optString("pedido"))
            }
            "notificacao" -> viewModelScope.launch(Dispatchers.IO) { Novidades.buscar(app) }
            "ajustes" -> {
                nomeUsuario.value = ev.optString("nome", "")
                temGrupo.value = ev.optString("grupo_jid", "").isNotEmpty()
                grupoLigado.value = ev.optBoolean("grupo_ligado", false)
                prefs.edit().putBoolean("tem_grupo", temGrupo.value).apply()
                nomePc.value = ev.optString("pc", "")
                volumeVoz.intValue = ev.optInt("volume_voz", volumeVoz.intValue)
                reconheceVoz.value = if (ev.has("reconhece_voz")) ev.optBoolean("reconhece_voz") else null
                ev.optJSONArray("conexoes")?.let { lista ->
                    conexoes.value = (0 until lista.length()).mapNotNull { i ->
                        lista.optJSONObject(i)?.let { EstadoConexao(it.optString("id"), it.optString("estado"), it.optString("detalhe")) }
                    }
                }
                prefs.edit().putString("nome_usuario", nomeUsuario.value).putString("nome_pc", nomePc.value).apply()
            }
            "uso" -> {
                ev.optJSONObject("cinco_horas")?.let {
                    usoCinco.value = it.optDouble("uso", -1.0); voltaCinco.value = it.optDouble("volta_em", 0.0)
                }
                ev.optJSONObject("semana")?.let {
                    usoSemana.value = it.optDouble("uso", -1.0); voltaSemana.value = it.optDouble("volta_em", 0.0)
                }
            }
            "memoria" -> memoriaTexto.value = ev.optString("texto")
            "voce_disse" -> {
                fecharPerguntas()
                mensagens.add(Mensagem(Quem.VOCE, ev.optString("texto"), anexos = nomesEnviados,
                    origem = ev.optString("origem")))
                nomesEnviados = emptyList()
            }
            "jarvis_disse" -> {
                // Aviso de WhatsApp é só no PC (decisão do Léo): aqui nem aparece.
                if (ev.optString("acao").startsWith("whatsapp:")) return
                val opcoes = ev.optJSONArray("opcoes")?.let { a -> List(a.length()) { a.getString(it) } } ?: emptyList()
                falaDele(ev.optString("texto"), ev.optBoolean("perguntando"), opcoes)
            }
            "mostrar" -> painel(ev.optString("titulo"), ev.optString("texto"))
            "atividade" -> {
                val t = ev.optString("texto")
                val i = mensagens.lastIndex
                if (i >= 0 && mensagens[i].quem == Quem.ATIVIDADE) {
                    mensagens[i] = mensagens[i].copy(texto = t, passos = mensagens[i].passos + t)
                } else {
                    mensagens.add(Mensagem(Quem.ATIVIDADE, t, passos = listOf(t)))
                }
            }
            "escrevendo" -> {
                if (ev.optBoolean("fim")) encerrarEscrita(ev.optBoolean("descartar"))
                else escrever(ev.optInt("bloco"), ev.optString("delta"))
            }
            "voz" -> {
                val pcm = ev.optString("pcm")
                if (pcm.isNotEmpty() && !mudo.value && agora() >= calarVozAte) voz.tocar(ev.optInt("taxa", 24000), Base64.decode(pcm, Base64.DEFAULT))
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
                "limite" -> mensagens.add(Mensagem(Quem.AVISO, "O limite do Claude acabou por agora."))
                "offline" -> mensagens.add(Mensagem(Quem.AVISO, "O PC está sem internet."))
            }
            "erro" -> {
                esperandoContinuar = ""
                pendente = null
                aviso.value = ev.optString("motivo")
            }
        }
    }

    private fun fecharPerguntas() {
        for (i in mensagens.indices) if (mensagens[i].perguntando) mensagens[i] = mensagens[i].copy(perguntando = false)
    }

    private fun falaDele(texto: String, perguntando: Boolean, opcoes: List<String>) {
        if (agora() < pularFalaAte) {
            // A versão falada do painel que acabou de chegar.
            pularFalaAte = 0.0
            if (perguntando) {
                val j = mensagens.indexOfLast { it.quem == Quem.PAINEL }
                if (j >= 0) mensagens[j] = mensagens[j].copy(perguntando = true, opcoes = opcoes)
            }
            return
        }
        fecharPerguntas()
        if (fecharEscrita(Quem.JARVIS, texto, perguntando, opcoes)) return
        mensagens.add(Mensagem(Quem.JARVIS, texto, perguntando = perguntando, opcoes = opcoes))
    }

    private fun painel(titulo: String, texto: String) {
        fecharPerguntas()
        if (titulo.isEmpty()) {
            pularFalaAte = agora() + 15
            if (fecharEscrita(Quem.PAINEL, texto, false, emptyList())) return
        }
        mensagens.add(Mensagem(Quem.PAINEL, texto, titulo))
    }

    // -- o texto chegando em pedaços ----------------------------------------------

    private fun escrever(bloco: Int, delta: String) {
        val i = mensagens.indexOfLast { it.escrevendo && it.bloco == bloco }
        if (i >= 0) mensagens[i] = mensagens[i].copy(texto = mensagens[i].texto + delta)
        else mensagens.add(Mensagem(Quem.JARVIS, delta, escrevendo = true, bloco = bloco))
    }

    /** O texto inteiro chegou: troca a fala que estava sendo escrita (a mais antiga aberta). */
    private fun fecharEscrita(quem: Quem, texto: String, perguntando: Boolean, opcoes: List<String>): Boolean {
        val i = mensagens.indexOfFirst { it.escrevendo }
        if (i < 0) return false
        mensagens[i] = mensagens[i].copy(quem = quem, texto = texto, escrevendo = false,
            perguntando = perguntando, opcoes = opcoes)
        return true
    }

    private fun encerrarEscrita(descartar: Boolean) {
        for (i in mensagens.indices.reversed()) {
            if (!mensagens[i].escrevendo) continue
            if (descartar) mensagens.removeAt(i) else mensagens[i] = mensagens[i].copy(escrevendo = false)
        }
    }

    /** A conversa que JÁ existia (histórico, conversa retomada ou aberta). */
    private fun preencher(lista: MutableList<Mensagem>, falas: org.json.JSONArray?) {
        lista.clear()
        pularFalaAte = 0.0
        if (falas == null) return
        for (k in 0 until falas.length()) {
            val f = falas.getJSONObject(k)
            val quando = f.optDouble("quando", agora())
            val texto = f.optString("texto")
            when (f.optString("quem")) {
                "voce" -> lista.add(Mensagem(Quem.VOCE, texto, origem = f.optString("origem"), quando = quando))
                "atividade" -> {
                    val ultima = lista.lastOrNull()
                    if (ultima?.quem == Quem.ATIVIDADE) lista[lista.lastIndex] = ultima.copy(texto = texto, passos = ultima.passos + texto)
                    else lista.add(Mensagem(Quem.ATIVIDADE, texto, passos = listOf(texto), quando = quando))
                }
                "jarvis" -> {
                    if (f.optString("acao").startsWith("whatsapp:")) continue
                    // Na conversa ao vivo, a fala que repete o painel não entra.
                    val antes = lista.lastOrNull()
                    if (antes?.quem == Quem.PAINEL && antes.titulo.isEmpty() && kotlin.math.abs(quando - antes.quando) < 15) continue
                    val opcoes = f.optJSONArray("opcoes")?.let { a -> List(a.length()) { a.getString(it) } } ?: emptyList()
                    lista.add(Mensagem(Quem.JARVIS, texto, quando = quando,
                        perguntando = f.optBoolean("perguntando") && k == falas.length() - 1, opcoes = opcoes))
                }
                else -> lista.add(Mensagem(Quem.PAINEL, texto, f.optString("titulo"), quando = quando))
            }
        }
    }
}
