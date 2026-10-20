package com.lelokz.jarvis

import android.annotation.SuppressLint
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.Executors

/**
 * A voz do Jarvis: os pedaços chegam em PCM int16 mono (40 kHz da voz do
 * JARVIS, 24 kHz da Kokoro de reserva) e tocam em fila, numa thread só,
 * direto no AudioTrack. Sem o navegador no meio: nada de "toque na página
 * para liberar o som".
 */
class Voz {
    private val fila = Executors.newSingleThreadExecutor()
    private var trilha: AudioTrack? = null
    private var taxaAtual = 0

    fun tocar(taxa: Int, pcm: ByteArray) {
        fila.execute {
            val t = trilhaPara(taxa)
            var feito = 0
            while (feito < pcm.size) {
                val n = t.write(pcm, feito, pcm.size - feito)
                if (n <= 0) break
                feito += n
            }
        }
    }

    private fun trilhaPara(taxa: Int): AudioTrack {
        trilha?.let { if (taxa == taxaAtual) return it }
        trilha?.release()
        val minimo = AudioTrack.getMinBufferSize(
            taxa, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val nova = AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build())
            .setAudioFormat(AudioFormat.Builder()
                .setSampleRate(taxa)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .build())
            .setTransferMode(AudioTrack.MODE_STREAM)
            .setBufferSizeInBytes(maxOf(minimo, taxa)) // ~0,5 s de folga
            .build()
        nova.play()
        trilha = nova
        taxaAtual = taxa
        return nova
    }

    fun fechar() {
        fila.execute { trilha?.release(); trilha = null }
        fila.shutdown()
    }
}

/**
 * Segurar para falar: grava PCM 16 kHz mono (o que o Whisper do PC quer) e,
 * ao soltar, devolve um WAV. A porta remota converte qualquer formato, mas
 * WAV não gasta nada para montar.
 */
class Gravador {
    private val taxa = 16000
    private var gravacao: AudioRecord? = null
    private var thread: Thread? = null
    private val dados = ByteArrayOutputStream()
    @Volatile private var gravando = false

    @SuppressLint("MissingPermission") // a MainActivity pede antes
    fun comecar() {
        if (gravando) return
        val minimo = AudioRecord.getMinBufferSize(
            taxa, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val g = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, taxa,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minimo, 6400))
        if (g.state != AudioRecord.STATE_INITIALIZED) {
            g.release()
            return
        }
        dados.reset()
        gravacao = g
        gravando = true
        g.startRecording()
        thread = Thread {
            val buf = ByteArray(3200)
            while (gravando) {
                val n = g.read(buf, 0, buf.size)
                if (n > 0) synchronized(dados) { dados.write(buf, 0, n) }
            }
        }.also { it.start() }
    }

    /** Para e devolve o WAV, ou null se foi curto demais (toque sem querer). */
    fun parar(): ByteArray? {
        if (!gravando) return null
        gravando = false
        thread?.join(500)
        gravacao?.stop()
        gravacao?.release()
        gravacao = null
        val pcm = synchronized(dados) { dados.toByteArray() }
        if (pcm.size < taxa * 2 * 3 / 10) return null // menos de 0,3 s
        return wav(pcm)
    }

    private fun wav(pcm: ByteArray): ByteArray {
        val cab = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        cab.put("RIFF".toByteArray()).putInt(36 + pcm.size).put("WAVE".toByteArray())
        cab.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(1)
        cab.putInt(taxa).putInt(taxa * 2).putShort(2).putShort(16)
        cab.put("data".toByteArray()).putInt(pcm.size)
        return cab.array() + pcm
    }
}
