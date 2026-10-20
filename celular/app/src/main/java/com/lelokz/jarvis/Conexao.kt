package com.lelokz.jarvis

import android.os.Handler
import android.os.Looper
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * O WebSocket da porta remota do Jarvis (`porta_remota.py` no PC), pelo
 * Tailscale. Fala o protocolo da ponte (`jarvis/ponte/protocolo.py`): a
 * primeira mensagem é a chave; depois chegam os eventos, um por mensagem.
 *
 * Caiu (internet, PC desligado), tenta de novo sozinha, esperando cada vez
 * mais (1 s, 2 s, 4 s... até 15 s). Os avisos chegam na thread principal.
 */
class Conexao(
    private val base: String,
    private val chave: String,
    private val aoReceber: (JSONObject) -> Unit,
    private val aoMudar: (conectado: Boolean, motivo: String) -> Unit,
) {
    private val principal = Handler(Looper.getMainLooper())
    private val cliente = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()
    private var ws: WebSocket? = null
    private var espera = 1000L
    private var fechada = false

    fun abrir() {
        fechada = false
        val url = base.trimEnd('/').replaceFirst("https://", "wss://")
            .replaceFirst("http://", "ws://") + "/ws"
        ws = cliente.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                espera = 1000L
                webSocket.send(JSONObject()
                    .put("chave", chave)
                    .put("historico", 80)
                    .put("quem", "celular-app")
                    .toString())
                principal.post { aoMudar(true, "") }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                val ev = try { JSONObject(text) } catch (e: Exception) { return }
                principal.post { aoReceber(ev) }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                caiu(if (code == 4401) "chave errada" else "conexão fechada")
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                caiu("sem conexão com o PC")
            }
        })
    }

    private fun caiu(motivo: String) {
        principal.post { aoMudar(false, motivo) }
        if (fechada || motivo == "chave errada") return
        principal.postDelayed({ if (!fechada) abrir() }, espera)
        espera = (espera * 2).coerceAtMost(15000L)
    }

    fun enviar(json: JSONObject): Boolean = ws?.send(json.toString()) ?: false

    fun enviar(audio: ByteArray): Boolean = ws?.send(audio.toByteString()) ?: false

    fun fechar() {
        fechada = true
        ws?.close(1000, "tchau")
        ws = null
    }
}
