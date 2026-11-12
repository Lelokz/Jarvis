package com.lelokz.painel

import android.app.Application
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * O cérebro do app: a ligação com o PC (a mesma do app da NOVA: link do
 * Tailscale + chave), o pacote do Painel, os pedidos e a atualização.
 */
class Modelo(private val app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("painel", Application.MODE_PRIVATE)
    private val cliente = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS).build()

    val configurado = mutableStateOf(prefs.contains("chave"))
    val pacote = mutableStateOf<Pacote?>(null)
    val carregando = mutableStateOf(false)
    val semConexao = mutableStateOf(false)
    val ocupado = mutableStateOf(false)            // falando com o YouTube (Salvar, Agendar…)
    val aviso = mutableStateOf("")
    val avisoBom = mutableStateOf(true)

    // A atualização (igual à do app da NOVA).
    val atualizacao = mutableIntStateOf(0)         // versionCode novo no PC (0 = nenhum)
    val avisoAtualizacao = mutableStateOf(false)
    val atualizando = mutableFloatStateOf(-1f)     // -1 parado, 0..1 baixando, 2 instalando

    private val thumbs = LruCache<String, Bitmap>(60)
    private var relogio: Job? = null

    private val base get() = prefs.getString("base", "")?.trimEnd('/') ?: ""
    private val chave get() = prefs.getString("chave", "") ?: ""

    /** Link ("https://jarvis.xxx.ts.net/#chave=...") ou base + chave vindos do app da NOVA. */
    fun configurar(baseNova: String, chaveNova: String): Boolean {
        val b = Regex("https?://[^\\s/#]+").find(baseNova)?.value ?: return false
        if (!Regex("[A-Za-z0-9_-]+").matches(chaveNova)) return false
        prefs.edit().putString("base", b).putString("chave", chaveNova).apply()
        configurado.value = true
        aoAbrir()
        return true
    }

    fun configurarPorLink(link: String): Boolean {
        val c = Regex("chave=([A-Za-z0-9_-]+)").find(link)?.groupValues?.get(1) ?: return false
        return configurar(link, c)
    }

    fun esquecer() {
        prefs.edit().clear().apply()
        pacote.value = null
        configurado.value = false
    }

    /** O app voltou pra frente: busca os dados, confere a versão e recarrega de minuto em minuto. */
    fun aoAbrir() {
        if (!configurado.value) return
        recarregar()
        viewModelScope.launch(Dispatchers.IO) { conferirVersao() }
        relogio?.cancel()
        relogio = viewModelScope.launch {
            while (isActive) { delay(60_000); recarregar(quieto = true) }
        }
    }

    fun aoSair() { relogio?.cancel() }

    fun recarregar(quieto: Boolean = false) {
        if (!quieto) carregando.value = true
        viewModelScope.launch(Dispatchers.IO) {
            val r = try {
                cliente.newCall(pedido("/painel/dados").build()).execute().use { resp ->
                    if (resp.code == 401) "chave" else if (!resp.isSuccessful) null
                    else lerPacote(JSONObject(resp.body?.string() ?: "{}"))
                }
            } catch (e: Exception) { null }
            withContext(Dispatchers.Main) {
                carregando.value = false
                when (r) {
                    is Pacote -> { pacote.value = r; semConexao.value = false }
                    "chave" -> { semConexao.value = true; avisar("A chave do PC mudou. Liga de novo pelo app da NOVA.", false) }
                    else -> semConexao.value = true
                }
            }
        }
    }

    private fun pedido(caminho: String) = Request.Builder().url(base + caminho).header("Authorization", "Bearer $chave")

    fun avisar(texto: String, bom: Boolean = true) { aviso.value = texto; avisoBom.value = bom }

    /** Um pedido pro PC (jarvis/youtube/remoto.py). `depois` roda com a resposta, na thread principal. */
    fun acao(campos: JSONObject, youtube: Boolean = false, depois: (Boolean) -> Unit = {}) {
        if (youtube) {
            if (ocupado.value) { avisar("Espera terminar o que está fazendo.", false); return }
            ocupado.value = true
        }
        viewModelScope.launch(Dispatchers.IO) {
            val r = try {
                cliente.newCall(pedido("/painel/acao")
                    .post(campos.toString().toRequestBody("application/json".toMediaType())).build()).execute().use {
                    JSONObject(it.body?.string() ?: "{}")
                }
            } catch (e: Exception) { JSONObject().put("ok", false).put("texto", "Sem conexão com o PC.") }
            withContext(Dispatchers.Main) {
                if (youtube) ocupado.value = false
                val ok = r.optBoolean("ok")
                val texto = r.optString("texto")
                if (texto.isNotEmpty()) avisar(texto, ok)
                depois(ok)
                recarregar(quieto = true)
            }
        }
    }

    fun sincronizar() = acao(JSONObject().put("acao", "sincronizar"), youtube = true)

    // -- as thumbs (com a chave, guardadas na memória) ----------------------------------

    fun thumbGuardada(caminho: String): Bitmap? = thumbs.get(caminho)

    suspend fun thumb(caminho: String): Bitmap? {
        thumbs.get(caminho)?.let { return it }
        return withContext(Dispatchers.IO) {
            try {
                cliente.newCall(pedido(caminho).build()).execute().use { r ->
                    if (!r.isSuccessful) null
                    else r.body?.bytes()?.let { b ->
                        val op = BitmapFactory.Options().apply { inSampleSize = 2 }   // 1280 → 640: sobra pro celular
                        BitmapFactory.decodeByteArray(b, 0, b.size, op)
                    }?.also { thumbs.put(caminho, it) }
                }
            } catch (e: Exception) { null }
        }
    }

    // -- atualização --------------------------------------------------------------------

    private suspend fun conferirVersao() {
        val noPc = try {
            cliente.newCall(Request.Builder().url("$base/painel/versao").build()).execute().use { r ->
                if (!r.isSuccessful) null else JSONObject(r.body?.string() ?: "{}").optInt("versionCode", -1).takeIf { it > 0 }
            }
        } catch (e: Exception) { null } ?: return
        val instalada = app.packageManager.getPackageInfo(app.packageName, 0).longVersionCode
        withContext(Dispatchers.Main) {
            atualizacao.intValue = if (noPc > instalada) noPc else 0
            if (atualizacao.intValue != 0 && prefs.getInt("atualizacao_avisada", 0) != noPc) avisoAtualizacao.value = true
        }
    }

    /** Fechou o aviso grande (sim ou não): não volta a abrir sozinho nesta versão. */
    fun fecharAvisoAtualizacao(atualizar: Boolean) {
        avisoAtualizacao.value = false
        prefs.edit().putInt("atualizacao_avisada", atualizacao.intValue).apply()
        if (!atualizar || atualizando.floatValue >= 0f) return
        if (!Atualizador.podeInstalar(app)) {
            avisar("Libera o Painel e toca em \"Atualização disponível\" de novo.", false)
            return
        }
        atualizando.floatValue = 0f
        val b = base
        viewModelScope.launch(Dispatchers.IO) {
            val erro = Atualizador.baixarEInstalar(app, "$b/painel.apk") { p ->
                viewModelScope.launch(Dispatchers.Main) { atualizando.floatValue = p }
            }
            withContext(Dispatchers.Main) {
                if (erro.isNotEmpty()) { avisar(erro, false); atualizando.floatValue = -1f }
                else atualizando.floatValue = 2f
            }
            delay(60_000)
            withContext(Dispatchers.Main) { if (atualizando.floatValue > 1f) atualizando.floatValue = -1f }
        }
    }
}
