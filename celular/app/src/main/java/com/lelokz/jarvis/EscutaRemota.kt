package com.lelokz.jarvis

import android.content.Context
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * O fim da frase do relógio, decidido aqui no celular com o Silero (no
 * relógio o onnxruntime quebra: ele é 32 bits). O relógio manda o microfone
 * em pedaços enquanto o Léo fala; quando a frase acaba, a fala já está toda
 * aqui e vai para o PC na hora, sem esperar subir pelo Bluetooth.
 *
 * O tempo é contado pelo ÁUDIO (80 ms por bloco), não pelo relógio de parede:
 * os pedaços chegam pelo Bluetooth em rajadas.
 */
class EscutaRemota(ctx: Context) {
    private val fala by lazy { DetectorDeFala(ctx) }
    private val gravado = ByteArrayOutputStream()
    private val resto = ByteArrayOutputStream()   // o pedaço que não fechou um bloco
    private var ativa = false
    private var desisteMs = 6000L
    private var tempo = 0L        // ms de áudio desde o começo
    private var ultimaFala = 0L
    private var seguidos = 0
    /** Já ouviu fala nesta escuta? */
    var falou = false
        private set

    companion object {
        const val SILENCIO_FIM_MS = 700L
        const val MAXIMO_MS = 15000L
        private const val BLOCO = 2560          // 1280 amostras, 80 ms
    }

    fun comecar(desisteMs: Long) {
        this.desisteMs = desisteMs
        gravado.reset(); resto.reset()
        tempo = 0; ultimaFala = 0; seguidos = 0
        falou = false
        fala.zerar()
        ativa = true
    }

    /** Um pedaço do microfone do relógio. Devolve o motivo do fim, ou null se continua. */
    fun pedaco(pcm: ByteArray): String? {
        if (!ativa) return null
        resto.write(pcm)
        val bytes = resto.toByteArray()
        resto.reset()
        var i = 0
        while (i + BLOCO <= bytes.size) {
            val fim = bloco(bytes, i)
            i += BLOCO
            if (fim != null) { ativa = false; return fim }
        }
        resto.write(bytes, i, bytes.size - i)
        return null
    }

    private fun bloco(b: ByteArray, off: Int): String? {
        tempo += 80
        gravado.write(b, off, BLOCO)
        val x = FloatArray(1280) {
            ((b[off + 2 * it + 1].toInt() shl 8) or (b[off + 2 * it].toInt() and 0xff)).toShort().toFloat()
        }
        // Como no Ouvido do celular: o Silero olha de 512 em 512, duas vezes por bloco.
        val tem = maxOf(fala.chance(x.copyOfRange(0, 512)), fala.chance(x.copyOfRange(512, 1024))) >= 0.5f
        if (tem) seguidos++ else seguidos = 0
        if (seguidos >= 2) { falou = true; ultimaFala = tempo }
        if (!falou) {
            if (tempo >= desisteMs) return "ninguém falou"
            // Antes da fala, guarda só o último segundo (o começo da frase).
            if (gravado.size() > 32000 * 2) {
                val g = gravado.toByteArray()
                gravado.reset(); gravado.write(g, g.size - 32000, 32000)
            }
            return null
        }
        if (tempo - ultimaFala >= SILENCIO_FIM_MS) return "silêncio"
        if (tempo >= MAXIMO_MS) return "tempo máximo"
        return null
    }

    /** O toque no átomo: termina agora. */
    fun encerrar(): String {
        ativa = false
        return if (falou) "toque" else "toque sem fala"
    }

    fun cancelar() { ativa = false }

    /** Quanto áudio esta escuta teve (para o log). */
    val duracaoMs: Long get() = tempo

    fun wav(): ByteArray {
        val pcm = gravado.toByteArray()
        val cab = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        cab.put("RIFF".toByteArray()).putInt(36 + pcm.size).put("WAVE".toByteArray())
        cab.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(1)
        cab.putInt(16000).putInt(32000).putShort(2).putShort(16)
        cab.put("data".toByteArray()).putInt(pcm.size)
        return cab.array() + pcm
    }
}
