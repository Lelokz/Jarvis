package com.lelokz.jarvis

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * O ouvido do relógio: sem "hey Jarvis" (ficar ouvindo o dia todo acaba com a
 * bateria). Liga quando o app abre (o botão) ou depois que ele responde, grava
 * até a fala acabar e entrega o WAV. Quem decide o que é fala é o Silero, o
 * mesmo do PC e do celular.
 */
class Escuta(ctx: Context, private val aoNivel: (Float) -> Unit) {
    private val fala = DetectorDeFala(ctx)
    @Volatile private var encerrar = false
    @Volatile private var cancelar = false
    /** Já ouviu fala nesta escuta? (a voz dele chegando cancela só se não.) */
    @Volatile var falou = false
        private set

    companion object {
        const val SILENCIO_FIM_MS = 800L
        const val MAXIMO_MS = 15000L
    }

    /** O toque no átomo: para agora e entrega o que ouviu. */
    fun encerrar() { encerrar = true }

    /** Para e joga fora (a voz dele chegou antes de o Léo falar). */
    fun cancelar() { cancelar = true }

    /**
     * Grava até 0,8 s de silêncio depois da fala. Devolve o WAV, ou null se
     * ninguém falou em `desisteMs`. Bloqueia: chamar fora da thread principal.
     */
    @SuppressLint("MissingPermission") // a tela pede antes
    fun ouvir(desisteMs: Long): ByteArray? {
        encerrar = false; cancelar = false; falou = false
        fala.zerar()
        val taxa = 16000
        val minimo = AudioRecord.getMinBufferSize(taxa, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, taxa,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minimo, 2560 * 4))
        if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); return null }
        val bloco = ShortArray(1280)  // 80 ms
        val gravado = ByteArrayOutputStream()
        val inicio = System.currentTimeMillis()
        var ultimaFala = 0L
        var seguidos = 0
        rec.startRecording()
        try {
            while (!cancelar) {
                var lidos = 0
                while (lidos < 1280) {
                    val n = rec.read(bloco, lidos, 1280 - lidos)
                    if (n <= 0) break
                    lidos += n
                }
                if (lidos < 1280) return null
                val agora = System.currentTimeMillis()
                guardar(gravado, bloco)
                aoNivel(nivel(bloco))
                val x = FloatArray(1280) { bloco[it].toFloat() }
                val temFala = maxOf(fala.chance(x.copyOfRange(0, 512)), fala.chance(x.copyOfRange(512, 1024))) >= 0.5f
                // Dois blocos seguidos (160 ms) para valer: um estalo não é fala.
                if (temFala) seguidos++ else seguidos = 0
                if (seguidos >= 2) { falou = true; ultimaFala = agora }
                if (!falou) {
                    if (encerrar || agora - inicio >= desisteMs) return null
                    // Antes da fala, guarda só o último segundo (o começo da frase).
                    if (gravado.size() > taxa * 2 * 2) {
                        val b = gravado.toByteArray()
                        gravado.reset(); gravado.write(b, b.size - taxa * 2, taxa * 2)
                    }
                    continue
                }
                if (encerrar || agora - ultimaFala >= SILENCIO_FIM_MS || agora - inicio >= MAXIMO_MS) {
                    return wav(gravado.toByteArray())
                }
            }
            return null
        } finally {
            rec.stop(); rec.release()
            aoNivel(0f)
        }
    }

    private fun guardar(saida: ByteArrayOutputStream, bloco: ShortArray) {
        val bb = ByteBuffer.allocate(bloco.size * 2).order(ByteOrder.LITTLE_ENDIAN)
        for (v in bloco) bb.putShort(v)
        saida.write(bb.array())
    }

    private fun nivel(bloco: ShortArray): Float {
        var soma = 0.0
        for (v in bloco) soma += v.toDouble() * v
        val rms = Math.sqrt(soma / bloco.size) / 32768.0
        return ((20 * Math.log10(maxOf(rms, 1e-5)) + 50) / 40).toFloat().coerceIn(0f, 1f)
    }

    private fun wav(pcm: ByteArray): ByteArray {
        val cab = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        cab.put("RIFF".toByteArray()).putInt(36 + pcm.size).put("WAVE".toByteArray())
        cab.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(1)
        cab.putInt(16000).putInt(32000).putShort(2).putShort(16)
        cab.put("data".toByteArray()).putInt(pcm.size)
        return cab.array() + pcm
    }
}
