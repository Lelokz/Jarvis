package com.lelokz.jarvis

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * O ouvido do relógio: sem "hey Jarvis" (ficar ouvindo o dia todo acaba com a
 * bateria). Liga quando o app abre (o botão) ou depois que ele responde, grava
 * até a fala acabar e entrega o WAV.
 *
 * Fala é o volume subir 12 dB acima do barulho do ambiente. NÃO é o Silero do
 * celular: o onnxruntime quebra (SIGBUS) no relógio, que roda em 32 bits.
 */
class Escuta(private val aoNivel: (Float) -> Unit) {
    @Volatile private var encerrar = false
    @Volatile private var cancelar = false
    /** Já ouviu fala nesta escuta? (a voz dele chegando cancela só se não.) */
    @Volatile var falou = false
        private set
    /** Por que a última escuta parou e quanto durou (vai para o log do PC). */
    var motivo = ""
        private set
    var duracaoMs = 0L
        private set

    companion object {
        const val SILENCIO_FIM_MS = 700L
        const val MAXIMO_MS = 12000L
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
        encerrar = false; cancelar = false; falou = false; motivo = "cancelada"
        var ruido = Double.NaN // o barulho do ambiente, em dB: começa no 1º bloco e vai se ajustando
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
                if (lidos < 1280) { motivo = "microfone falhou"; return null }
                val agora = System.currentTimeMillis()
                guardar(gravado, bloco)
                aoNivel(nivel(bloco))
                val db = decibeis(bloco)
                if (ruido.isNaN()) ruido = db
                val temFala = db > ruido + 12.0 && db > -50.0
                // O ruído desce rápido (silêncio) e sobe em ~1,5 s: acompanha a rua
                // ficando mais barulhenta, e não aprende a fala (as pausas entre
                // as sílabas puxam ele para baixo).
                ruido = if (db < ruido) ruido * 0.7 + db * 0.3 else ruido * 0.95 + db * 0.05
                // Dois blocos seguidos (160 ms) para valer: um estalo não é fala.
                if (temFala) seguidos++ else seguidos = 0
                if (seguidos >= 2) { falou = true; ultimaFala = agora }
                if (!falou) {
                    if (encerrar || agora - inicio >= desisteMs) {
                        motivo = if (encerrar) "toque sem fala" else "ninguém falou"
                        return null
                    }
                    // Antes da fala, guarda só o último segundo (o começo da frase).
                    if (gravado.size() > taxa * 2 * 2) {
                        val b = gravado.toByteArray()
                        gravado.reset(); gravado.write(b, b.size - taxa * 2, taxa * 2)
                    }
                    continue
                }
                if (encerrar || agora - ultimaFala >= SILENCIO_FIM_MS || agora - inicio >= MAXIMO_MS) {
                    motivo = when {
                        encerrar -> "toque"
                        agora - ultimaFala >= SILENCIO_FIM_MS -> "silêncio"
                        else -> "tempo máximo"
                    }
                    return wav(gravado.toByteArray())
                }
            }
            return null
        } finally {
            duracaoMs = System.currentTimeMillis() - inicio
            rec.stop(); rec.release()
            aoNivel(0f)
        }
    }

    private fun guardar(saida: ByteArrayOutputStream, bloco: ShortArray) {
        val bb = ByteBuffer.allocate(bloco.size * 2).order(ByteOrder.LITTLE_ENDIAN)
        for (v in bloco) bb.putShort(v)
        saida.write(bb.array())
    }

    private fun decibeis(bloco: ShortArray): Double {
        var soma = 0.0
        for (v in bloco) soma += v.toDouble() * v
        val rms = Math.sqrt(soma / bloco.size) / 32768.0
        return 20 * Math.log10(maxOf(rms, 1e-5))
    }

    private fun nivel(bloco: ShortArray): Float =
        ((decibeis(bloco) + 50) / 40).toFloat().coerceIn(0f, 1f)

    private fun wav(pcm: ByteArray): ByteArray {
        val cab = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        cab.put("RIFF".toByteArray()).putInt(36 + pcm.size).put("WAVE".toByteArray())
        cab.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(1)
        cab.putInt(16000).putInt(32000).putShort(2).putShort(16)
        cab.put("data".toByteArray()).putInt(pcm.size)
        return cab.array() + pcm
    }
}
