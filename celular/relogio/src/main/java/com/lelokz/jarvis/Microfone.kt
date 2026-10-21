package com.lelokz.jarvis

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * O microfone do relógio: grava PCM 16 kHz e entrega em pedaços de 160 ms,
 * que vão para o celular enquanto o Léo fala. O fim da frase quem decide é o
 * celular (`EscutaRemota`, com o Silero); aqui só liga, desliga e mede o
 * volume para o átomo crescer com a voz.
 *
 * Desliga sozinho depois de `SEGURANCA_MS`, se o celular nunca responder.
 */
class Microfone(
    private val aoPedaco: (ByteArray) -> Unit,
    private val aoNivel: (Float) -> Unit,
) {
    @Volatile private var ligado = false

    companion object {
        const val SEGURANCA_MS = 25000L
    }

    @SuppressLint("MissingPermission") // a tela pede antes
    fun ligar() {
        if (ligado) return
        ligado = true
        Thread({ laco() }, "microfone").start()
    }

    fun desligar() { ligado = false }

    @SuppressLint("MissingPermission")
    private fun laco() {
        val taxa = 16000
        val minimo = AudioRecord.getMinBufferSize(taxa, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, taxa,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minimo, 2560 * 4))
        if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); ligado = false; return }
        val bloco = ShortArray(2560)  // 160 ms
        val inicio = System.currentTimeMillis()
        rec.startRecording()
        try {
            while (ligado && System.currentTimeMillis() - inicio < SEGURANCA_MS) {
                var lidos = 0
                while (lidos < bloco.size) {
                    val n = rec.read(bloco, lidos, bloco.size - lidos)
                    if (n <= 0) break
                    lidos += n
                }
                if (lidos < bloco.size || !ligado) break
                val bb = ByteBuffer.allocate(bloco.size * 2).order(ByteOrder.LITTLE_ENDIAN)
                var soma = 0.0
                for (v in bloco) { bb.putShort(v); soma += v.toDouble() * v }
                aoPedaco(bb.array())
                val rms = Math.sqrt(soma / bloco.size) / 32768.0
                aoNivel(((20 * Math.log10(maxOf(rms, 1e-5)) + 50) / 40).toFloat().coerceIn(0f, 1f))
            }
        } finally {
            ligado = false
            rec.stop(); rec.release()
            aoNivel(0f)
        }
    }
}
