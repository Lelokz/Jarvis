package com.lelokz.jarvis

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import kotlin.random.Random

/**
 * O "hey Jarvis" no celular: os mesmos modelos do PC (openWakeWord), com o
 * mesmo preparo do áudio. Conferido em Python contra a biblioteca do PC com
 * gravações reais do Léo: notas iguais (diferença máxima 0,001).
 *
 * A cada bloco de 80 ms (1280 amostras a 16 kHz): o mel dos últimos 1760
 * (o bloco + 3 quadros de contexto), um "embedding" dos últimos 76 quadros de
 * mel, e a nota do modelo nos últimos 16 embeddings.
 */
class DetectorHeyJarvis(ctx: Context) {
    private val env = OrtEnvironment.getEnvironment()
    private val opcoes = OrtSession.SessionOptions().apply { setIntraOpNumThreads(1) }
    private val melS = sessao(ctx, "melspectrogram.onnx")
    private val embS = sessao(ctx, "embedding_model.onnx")
    private val wwS = sessao(ctx, "hey_jarvis_v0.1.onnx")

    private var bruto = FloatArray(0)
    private val mels = ArrayDeque<FloatArray>()
    private val feats = ArrayDeque<FloatArray>()
    private var blocos = 0

    private fun sessao(ctx: Context, nome: String): OrtSession =
        env.createSession(ctx.assets.open(nome).use { it.readBytes() }, opcoes)

    init { zerar() }

    /** Como o openWakeWord começa: mel "neutro" e embeddings de ruído. */
    fun zerar() {
        bruto = FloatArray(0)
        mels.clear()
        repeat(76) { mels.addLast(FloatArray(32) { 1f }) }
        feats.clear()
        val rnd = Random(0)
        val ruido = FloatArray(64000) { (rnd.nextInt(2000) - 1000).toFloat() }
        val m = mel(ruido)
        var i = 0
        while (i + 76 <= m.size) {
            feats.addLast(embedding(m.subList(i, i + 76)))
            i += 8
        }
        blocos = 0
    }

    private fun mel(amostras: FloatArray): List<FloatArray> {
        OnnxTensor.createTensor(env, FloatBuffer.wrap(amostras), longArrayOf(1, amostras.size.toLong())).use { t ->
            melS.run(mapOf("input" to t)).use { r ->
                val fb = (r[0] as OnnxTensor).floatBuffer
                val n = fb.remaining() / 32
                return List(n) { FloatArray(32) { fb.get() / 10f + 2f } }
            }
        }
    }

    private fun embedding(janela: List<FloatArray>): FloatArray {
        val buf = FloatBuffer.allocate(76 * 32)
        for (q in janela) buf.put(q)
        buf.rewind()
        OnnxTensor.createTensor(env, buf, longArrayOf(1, 76, 32, 1)).use { t ->
            embS.run(mapOf("input_1" to t)).use { r ->
                val fb = (r[0] as OnnxTensor).floatBuffer
                return FloatArray(96) { fb.get() }
            }
        }
    }

    /** Um bloco de 1280 amostras (int16 em float) → a nota de 0 a 1. */
    fun bloco(x: FloatArray): Float {
        bruto = (bruto + x).let { if (it.size > 1760) it.copyOfRange(it.size - 1760, it.size) else it }
        for (q in mel(bruto)) mels.addLast(q)
        while (mels.size > 970) mels.removeFirst()
        feats.addLast(embedding(mels.toList().subList(mels.size - 76, mels.size)))
        while (feats.size > 120) feats.removeFirst()
        blocos++
        val buf = FloatBuffer.allocate(16 * 96)
        for (f in feats.toList().subList(feats.size - 16, feats.size)) buf.put(f)
        buf.rewind()
        val nota = OnnxTensor.createTensor(env, buf, longArrayOf(1, 16, 96)).use { t ->
            wwS.run(mapOf("x.1" to t)).use { r -> (r[0] as OnnxTensor).floatBuffer.get() }
        }
        return if (blocos < 5) 0f else nota
    }
}

/** O Silero VAD (o mesmo do PC): a chance de ter fala em 512 amostras (32 ms). */
class DetectorDeFala(ctx: Context) {
    private val env = OrtEnvironment.getEnvironment()
    private val s = env.createSession(ctx.assets.open("silero_vad.onnx").use { it.readBytes() },
        OrtSession.SessionOptions().apply { setIntraOpNumThreads(1) })
    private var h = FloatArray(128)
    private var c = FloatArray(128)

    fun zerar() { h = FloatArray(128); c = FloatArray(128) }

    fun chance(x512: FloatArray): Float {
        val entrada = FloatArray(512) { x512[it] / 32768f }
        OnnxTensor.createTensor(env, FloatBuffer.wrap(entrada), longArrayOf(1, 512)).use { ti ->
        OnnxTensor.createTensor(env, FloatBuffer.wrap(h), longArrayOf(2, 1, 64)).use { th ->
        OnnxTensor.createTensor(env, FloatBuffer.wrap(c), longArrayOf(2, 1, 64)).use { tc ->
        // "sr" é um escalar (forma vazia): o Long sozinho vira esse tensor.
        OnnxTensor.createTensor(env, 16000L).use { sr ->
            s.run(mapOf("input" to ti, "sr" to sr, "h" to th, "c" to tc)).use { r ->
                val p = (r[0] as OnnxTensor).floatBuffer.get()
                h = FloatArray(128).also { (r[1] as OnnxTensor).floatBuffer.get(it) }
                c = FloatArray(128).also { (r[2] as OnnxTensor).floatBuffer.get(it) }
                return p
            }
        }}}}
    }
}

/**
 * O ouvido: um AudioRecord só, numa thread, em três modos.
 *
 * - ESPERANDO: só o detector do "hey Jarvis" (o que roda o dia todo).
 * - GRAVANDO: depois do "hey Jarvis" (ou na janela de conversa), grava até
 *   0,8 s de silêncio depois da fala (o Silero decide o que é fala), e
 *   entrega o WAV.
 * - JANELA: logo depois de ele responder, alguns segundos ouvindo SEM
 *   precisar do "hey Jarvis", como no PC; começou a falar, vira GRAVANDO.
 *
 * `pausado` (ele falando, ou o Léo segurando o átomo) ignora o microfone:
 * o celular não pode se ouvir.
 */
class Ouvido(
    ctx: Context,
    private val aoAcordar: () -> Unit,
    private val aoGravar: (Boolean) -> Unit,
    private val aoTerminar: (ByteArray) -> Unit,
    private val aoNivel: (Float) -> Unit,
) {
    private enum class Modo { ESPERANDO, GRAVANDO, JANELA }

    private val detector = DetectorHeyJarvis(ctx)
    private val fala = DetectorDeFala(ctx)
    @Volatile private var ligado = false
    @Volatile var pausado = false
    @Volatile private var modo = Modo.ESPERANDO
    @Volatile private var janelaAte = 0L
    private var thread: Thread? = null

    companion object {
        const val LIMIAR = 0.5f              // o mesmo do PC ([wakeword] limiar)
        const val REFRATARIO_MS = 1500L
        const val SILENCIO_FIM_MS = 800L
        const val SEM_FALA_DESISTE_MS = 5000L
        const val MAXIMO_MS = 15000L
        const val JANELA_MS = 7000L
    }

    @SuppressLint("MissingPermission") // o serviço só liga com a permissão dada
    fun ligar() {
        if (ligado) return
        ligado = true
        thread = Thread({ laco() }, "ouvido").apply { start() }
    }

    fun desligar() {
        ligado = false
        thread?.join(1000)
        thread = null
    }

    /** Depois que ele termina de responder: ouve sem precisar do "hey Jarvis". */
    fun abrirJanela() {
        if (modo == Modo.ESPERANDO) {
            janelaAte = System.currentTimeMillis() + JANELA_MS
            modo = Modo.JANELA
            fala.zerar()
        }
    }

    @SuppressLint("MissingPermission")
    private fun laco() {
        val taxa = 16000
        val minimo = AudioRecord.getMinBufferSize(taxa, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, taxa,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minimo, 2560 * 4))
        if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); ligado = false; return }
        rec.startRecording()
        val bloco = ShortArray(1280)
        val gravado = ByteArrayOutputStream()
        var refratarioAte = 0L
        var inicio = 0L
        var falou = false
        var ultimaFala = 0L
        var seguidos = 0
        var estavaPausado = false
        try {
            while (ligado) {
                var lidos = 0
                while (lidos < 1280 && ligado) {
                    val n = rec.read(bloco, lidos, 1280 - lidos)
                    if (n <= 0) break
                    lidos += n
                }
                if (lidos < 1280) continue
                val agora = System.currentTimeMillis()
                if (pausado) { estavaPausado = true; continue }
                if (estavaPausado) {
                    // Voltou de uma pausa: o que estava no detector é velho.
                    estavaPausado = false
                    detector.zerar()
                }
                val x = FloatArray(1280) { bloco[it].toFloat() }
                when (modo) {
                    Modo.ESPERANDO -> {
                        val nota = detector.bloco(x)
                        if (nota >= LIMIAR && agora >= refratarioAte) {
                            refratarioAte = agora + REFRATARIO_MS
                            aoAcordar()
                            comecar(gravado); inicio = agora; falou = false; seguidos = 0
                            modo = Modo.GRAVANDO
                        }
                    }
                    Modo.JANELA -> {
                        if (agora > janelaAte) { modo = Modo.ESPERANDO; detector.zerar(); continue }
                        if (temFala(x)) seguidos++ else seguidos = 0
                        guardar(gravado, bloco) // o começo da frase não pode se perder
                        if (seguidos >= 2) {
                            inicio = agora; falou = true; ultimaFala = agora
                            aoGravar(true)
                            modo = Modo.GRAVANDO
                        } else if (gravado.size() > 16000 * 2) {
                            // Só guarda o último segundo enquanto espera a fala.
                            val b = gravado.toByteArray()
                            gravado.reset(); gravado.write(b, b.size - 16000, 16000)
                        }
                    }
                    Modo.GRAVANDO -> {
                        guardar(gravado, bloco)
                        aoNivel(nivel(bloco))
                        if (temFala(x)) { falou = true; ultimaFala = agora }
                        val acabou = (falou && agora - ultimaFala >= SILENCIO_FIM_MS) ||
                            agora - inicio >= MAXIMO_MS
                        val desistiu = !falou && agora - inicio >= SEM_FALA_DESISTE_MS
                        if (acabou || desistiu) {
                            aoGravar(false); aoNivel(0f)
                            if (acabou) aoTerminar(wav(gravado.toByteArray()))
                            gravado.reset()
                            modo = Modo.ESPERANDO
                            detector.zerar()
                        }
                    }
                }
            }
        } finally {
            rec.stop(); rec.release()
        }
    }

    private fun comecar(gravado: ByteArrayOutputStream) {
        gravado.reset()
        fala.zerar()
        aoGravar(true)
    }

    /** Fala no bloco de 80 ms? O Silero olha de 512 em 512 (duas vezes por bloco). */
    private fun temFala(x: FloatArray): Boolean {
        val a = fala.chance(x.copyOfRange(0, 512))
        val b = fala.chance(x.copyOfRange(512, 1024))
        return maxOf(a, b) >= 0.5f
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
