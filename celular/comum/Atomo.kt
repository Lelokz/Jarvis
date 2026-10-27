package com.lelokz.jarvis

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.lerp
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt
import kotlin.math.tan
import kotlin.random.Random

/**
 * O átomo da NOVA no celular e no relógio (o definitivo, 27/10/2026): o mesmo
 * do site (site/atomo3d.js) e da janela (jarvis/interface/qml/atomo.js) —
 * núcleo geodésico, três argolas de formatos diferentes girando como moeda e
 * oito bolinhas com rastro. Sem 3D aqui: as rotações e a câmera são contas à
 * mão, projetadas num Canvas, igual ao atomo.js (este arquivo é a tradução dele).
 *
 * Ordem do desenho (o "atrás" do 3D): brilho em volta, o que fica atrás do
 * núcleo, o núcleo (opaco, esconde o de trás), e o que fica na frente.
 * Abaixo de 64 px vale o desenho simples: sem marcações, pontos nem malha.
 *
 * O estado vira número (escala, velocidade, brilho, cor), e todo número passa
 * por uma animação: nada troca num piscar.
 */
@Composable
fun Atomo(
    cor: Color,
    escala: Float,
    velocidade: Float,
    brilho: Float,
    @Suppress("UNUSED_PARAMETER") turbulencia: Float,   // do átomo antigo; o novo não usa
    nivel: Float,
    parado: Boolean,
    pulsando: Boolean,
    fundo: Color,
    modifier: Modifier = Modifier,
) {
    val corA by animateColorAsState(cor, tween(640), label = "cor")
    val escalaA by animateFloatAsState(escala, tween(520, easing = FastOutSlowInEasing), label = "escala")
    val velA by animateFloatAsState(velocidade, tween(900), label = "vel")
    val brilhoA by animateFloatAsState(brilho, tween(420), label = "brilho")
    val nivelA by animateFloatAsState(nivel, tween(120), label = "nivel")
    val apagado by animateFloatAsState(if (parado) 0.55f else 1f, tween(600), label = "apagado")
    val respiroT = rememberInfiniteTransition(label = "respiro")
    val respiroAnim by respiroT.animateFloat(
        1f, 0.94f, infiniteRepeatable(tween(2200), RepeatMode.Reverse), label = "respiro")
    val respiro = if (pulsando && !parado) respiroAnim else 1f

    // O tempo do átomo é SOMADO a cada quadro (como no PC): trocar a
    // velocidade vale no quadro seguinte, sem pulo.
    var tempo by remember { mutableFloatStateOf(3f) }
    var quadro by remember { mutableLongStateOf(0L) }
    val desenho = remember { DesenhoDoAtomo() }
    val vel by rememberUpdatedState(velA)
    val parou by rememberUpdatedState(parado)

    LaunchedEffect(Unit) {
        var antes = 0L
        while (true) {
            withFrameNanos { t ->
                val dt = if (antes == 0L) 0f else ((t - antes) / 1e9f).coerceAtMost(0.1f)
                antes = t
                if (!parou) { tempo += dt * vel; quadro = t }
            }
        }
    }

    Canvas(modifier) {
        if (quadro < 0L) return@Canvas // ler o quadro aqui faz redesenhar a cada quadro
        scale(escalaA * respiro, center) {
            with(desenho) {
                desenhar(tempo, corA.copy(alpha = 1f), fundo, brilhoA * (1f + nivelA * 0.6f) * apagado, 1f, apagado)
            }
        }
    }
}

// --- A geometria (igual à do atomo.js) ----------------------------------------

private const val RN = 0.62f        // raio do núcleo
private const val DIAMETRO = 4f     // o átomo inteiro, com a folga do brilho
private val TG = tan(16.0 * PI / 180).toFloat()   // metade do campo de visão (32°)
private const val N = 192           // pedaços de cada argola (múltiplo de 48, 6 e 3)
private const val TAU = (2 * PI).toFloat()

private class Formato(val raio: Float, val largura: Float, val ex: Float, val ey: Float, val bola: Float,
                      val bolinhas: Int, val vel: Float, val giro: Float, val sentido: Int)

// 0 = a externa (faixa larga, marcações, 3 partes); 1 = a interna (fio duplo
// tracejado); 2 = a do meio (elipse com pontos).
private val FORMATOS = listOf(
    Formato(1.62f, 0.12f, 1f, 1f, 0.05f, 3, 0.13f, 0.5f, 1),
    Formato(1.3f, 0.05f, 1f, 1f, 0.038f, 2, 0.17f, -0.42f, -1),
    Formato(1.45f, 0.08f, 1.16f, 0.84f, 0.044f, 3, 0.15f, 0.6f, 1),
)
// As linhas de luz de cada argola (w através da faixa) e a força delas.
private val LINHAS = arrayOf(floatArrayOf(0.06f, 0.94f), floatArrayOf(0.25f, 0.75f), floatArrayOf(0.1f, 0.9f))
private val FORCA = floatArrayOf(1f, 1.1f, 1f)
private val ENCHE = floatArrayOf(0.11f, 0f, 0.07f)   // o fundo translúcido da faixa
private val TRECHOS = arrayOf(floatArrayOf(0f, 0.45f, 0.25f), floatArrayOf(0.45f, 0.75f, 0.6f), floatArrayOf(0.75f, 1f, 1f))

private fun fr(x: Float) = x - floor(x)
private fun mostra(i: Int, a: Float): Boolean {   // o vão / o tracejado de cada argola
    val fase = i * 0.37f
    return when (i) {
        0 -> fr(a * 3 + fase).let { it > 0.005f && it < 0.955f }
        1 -> fr(a * 48 + fase) < 0.62f
        else -> fr(a * 6 + fase).let { it > 0.004f && it < 0.979f }
    }
}

private val SEN = FloatArray(N + 1) { sin(it.toFloat() / N * TAU) }
private val COS = FloatArray(N + 1) { cos(it.toFloat() / N * TAU) }
private val MOSTRA = Array(3) { i -> BooleanArray(N) { k -> mostra(i, (k + 0.5f) / N) } }

/** A casca geodésica: icosaedro com cada face partida em 9 (o "detail 2" do three.js). */
private object Geodesica {
    val pontos: FloatArray
    val faces: IntArray
    val arestas: IntArray
    val n: Int

    init {
        val p = ((1 + sqrt(5.0)) / 2).toFloat()
        val v = arrayOf(floatArrayOf(-1f, p, 0f), floatArrayOf(1f, p, 0f), floatArrayOf(-1f, -p, 0f), floatArrayOf(1f, -p, 0f),
            floatArrayOf(0f, -1f, p), floatArrayOf(0f, 1f, p), floatArrayOf(0f, -1f, -p), floatArrayOf(0f, 1f, -p),
            floatArrayOf(p, 0f, -1f), floatArrayOf(p, 0f, 1f), floatArrayOf(-p, 0f, -1f), floatArrayOf(-p, 0f, 1f))
        val f = arrayOf(intArrayOf(0, 11, 5), intArrayOf(0, 5, 1), intArrayOf(0, 1, 7), intArrayOf(0, 7, 10), intArrayOf(0, 10, 11),
            intArrayOf(1, 5, 9), intArrayOf(5, 11, 4), intArrayOf(11, 10, 2), intArrayOf(10, 7, 6), intArrayOf(7, 1, 8),
            intArrayOf(3, 9, 4), intArrayOf(3, 4, 2), intArrayOf(3, 2, 6), intArrayOf(3, 6, 8), intArrayOf(3, 8, 9),
            intArrayOf(4, 9, 5), intArrayOf(2, 4, 11), intArrayOf(6, 2, 10), intArrayOf(8, 6, 7), intArrayOf(9, 8, 1))
        val pts = ArrayList<Float>(); val chave = HashMap<String, Int>(); val fcs = ArrayList<Int>()
        fun ponto(x0: Float, y0: Float, z0: Float): Int {
            val m = sqrt(x0 * x0 + y0 * y0 + z0 * z0); val x = x0 / m; val y = y0 / m; val z = z0 / m
            val k = "${Math.round(x * 1e4)},${Math.round(y * 1e4)},${Math.round(z * 1e4)}"
            return chave.getOrPut(k) { pts.add(x * RN); pts.add(y * RN); pts.add(z * RN); pts.size / 3 - 1 }
        }
        val d = 3
        for (face in f) {
            val a = v[face[0]]; val b = v[face[1]]; val c = v[face[2]]
            val grade = Array(d + 1) { l -> IntArray(d + 1 - l) { m ->
                val u = l.toFloat() / d; val w = m.toFloat() / d
                ponto(a[0] + (b[0] - a[0]) * u + (c[0] - a[0]) * w, a[1] + (b[1] - a[1]) * u + (c[1] - a[1]) * w,
                      a[2] + (b[2] - a[2]) * u + (c[2] - a[2]) * w)
            } }
            for (l in 0 until d) for (m in 0 until d - l) {
                fcs.add(grade[l][m]); fcs.add(grade[l + 1][m]); fcs.add(grade[l][m + 1])
                if (m < d - l - 1) { fcs.add(grade[l + 1][m]); fcs.add(grade[l + 1][m + 1]); fcs.add(grade[l][m + 1]) }
            }
        }
        val ars = ArrayList<Int>(); val vista = HashSet<Int>()
        for (i in fcs.indices step 3) for (e in 0 until 3) {
            val x0 = fcs[i + e]; val x1 = fcs[i + (e + 1) % 3]; val k = min(x0, x1) * 1000 + max(x0, x1)
            if (vista.add(k)) { ars.add(x0); ars.add(x1) }
        }
        pontos = pts.toFloatArray(); faces = fcs.toIntArray(); arestas = ars.toIntArray(); n = pontos.size / 3
    }
}

// Matriz 3×3 (linha a linha) e produto.
private fun mul(a: FloatArray, b: FloatArray) = FloatArray(9) { k ->
    val l = k / 3; val c = k % 3
    a[l * 3] * b[c] + a[l * 3 + 1] * b[3 + c] + a[l * 3 + 2] * b[6 + c]
}
private fun rx(a: Float): FloatArray { val c = cos(a); val s = sin(a); return floatArrayOf(1f, 0f, 0f, 0f, c, -s, 0f, s, c) }
private fun ry(a: Float): FloatArray { val c = cos(a); val s = sin(a); return floatArrayOf(c, 0f, s, 0f, 1f, 0f, -s, 0f, c) }
private fun rz(a: Float): FloatArray { val c = cos(a); val s = sin(a); return floatArrayOf(c, -s, 0f, s, c, 0f, 0f, 0f, 1f) }

/** Quem desenha: guarda o sorteio dos painéis do núcleo e as contas de cada quadro. */
class DesenhoDoAtomo {
    private val sorteio = FloatArray(Geodesica.faces.size / 3) { Random.nextFloat() }
    private val px = FloatArray(Geodesica.n); private val py = FloatArray(Geodesica.n); private val pz = FloatArray(Geodesica.n)
    // Por argola: a (círculo em x), b (círculo em y), c (através da faixa): 9 números.
    private val arg = Array(3) { FloatArray(9) }
    private val larg = FloatArray(3)
    private val pt = FloatArray(4)
    private val voltaA = FloatArray((N + 1) * 3); private val voltaB = FloatArray((N + 1) * 3)
    private var cx = 0f; private var cy = 0f; private var esc = 0f
    private val camZ = (DIAMETRO / 2) / TG

    /** Ponto (u em sen/cos, w de 0 a 1) da argola i na tela: pt = [x, y, z, escala]. */
    private fun ponto(i: Int, s: Float, c: Float, w: Float) {
        val m = arg[i]; val ww = w - 0.5f
        val x = s * m[0] - c * m[3] + ww * m[6]; val y = s * m[1] - c * m[4] + ww * m[7]; val z = s * m[2] - c * m[5] + ww * m[8]
        val f = esc / (camZ - z)
        pt[0] = cx + x * f; pt[1] = cy - y * f; pt[2] = z; pt[3] = f
    }
    private fun volta(i: Int, w: Float, saida: FloatArray) {
        for (q in 0..N) { ponto(i, SEN[q], COS[q], w); saida[q * 3] = pt[0]; saida[q * 3 + 1] = pt[1]; saida[q * 3 + 2] = pt[2] }
    }

    fun DrawScope.desenhar(t: Float, cor: Color, fundo: Color, brilho: Float, traco: Float, opaco: Float) {
        val lado = size.minDimension; cx = center.x; cy = center.y
        esc = (lado / 2) / TG
        val simples = lado < 64 * density
        val ra = mul(rx(sin(t * 0.17f) * 0.12f), ry(sin(t * 0.22f) * 0.35f))   // o balanço do átomo inteiro
        val fino = max(if (simples) 1f else 0.8f, lado * 0.0026f) * (if (simples) 1.4f else 1f)
        val branco = Color.White
        val mais = BlendMode.Plus

        // O brilho em volta do núcleo (o halo do 3D).
        val rh = 1.7f * esc / camZ
        drawCircle(Brush.radialGradient(0f to cor.copy(alpha = 0.30f * brilho), 0.22f to cor.copy(alpha = 0.12f * brilho),
            1f to cor.copy(alpha = 0f), center = center, radius = rh), radius = rh, center = center, blendMode = mais)

        for (i in 0 until 3) {
            val f = FORMATOS[i]
            val m = mul(ra, mul(rz(i * PI.toFloat() / 3), rx(1.2f + i * 0.7f + t * f.giro)))
            val r0 = f.raio * f.ex; val r1 = f.raio * f.ey; val l = f.largura * traco
            larg[i] = l
            arg[i][0] = m[0] * r0; arg[i][1] = m[3] * r0; arg[i][2] = m[6] * r0
            arg[i][3] = m[1] * r1; arg[i][4] = m[4] * r1; arg[i][5] = m[7] * r1
            arg[i][6] = m[2] * l; arg[i][7] = m[5] * l; arg[i][8] = m[8] * l
        }

        fun argola(i: Int, frente: Boolean) {
            val vis = MOSTRA[i]
            val ws = if (simples) floatArrayOf(0.5f) else LINHAS[i]
            for (w in ws) {
                volta(i, w, voltaA)
                val caminho = Path(); var ligado = false
                for (k in 0 until N) {
                    val aqui = (simples || vis[k]) && ((voltaA[k * 3 + 2] + voltaA[k * 3 + 5]) >= 0f) == frente
                    if (aqui) {
                        if (!ligado) caminho.moveTo(voltaA[k * 3], voltaA[k * 3 + 1])
                        caminho.lineTo(voltaA[k * 3 + 3], voltaA[k * 3 + 4])
                    }
                    ligado = aqui
                }
                drawPath(caminho, cor.copy(alpha = (0.6f * (if (simples) 1.6f else FORCA[i])).coerceAtMost(1f)),
                    style = Stroke(fino * (if (i == 0) 1.3f else 1.1f), cap = StrokeCap.Round, join = StrokeJoin.Round), blendMode = mais)
            }
            if (simples) return
            if (ENCHE[i] > 0f) {   // o fundo translúcido da faixa (entre as bordas)
                volta(i, 0f, voltaA); volta(i, 1f, voltaB)
                val caminho = Path()
                for (k in 0 until N) {
                    if (!vis[k] || ((voltaA[k * 3 + 2] + voltaB[k * 3 + 5]) >= 0f) != frente) continue
                    caminho.moveTo(voltaA[k * 3], voltaA[k * 3 + 1]); caminho.lineTo(voltaA[k * 3 + 3], voltaA[k * 3 + 4])
                    caminho.lineTo(voltaB[k * 3 + 3], voltaB[k * 3 + 4]); caminho.lineTo(voltaB[k * 3], voltaB[k * 3 + 1]); caminho.close()
                }
                drawPath(caminho, cor.copy(alpha = ENCHE[i]), blendMode = mais)
            }
            if (i == 0) {   // as marcações da externa (atravessando o meio da faixa)
                val caminho = Path()
                for (k in 0 until 120) {
                    val a = (k + 0.04f) / 120
                    if (!mostra(0, a)) continue
                    val s = sin(a * TAU); val c = cos(a * TAU)
                    ponto(0, s, c, 0.3f)
                    if ((pt[2] >= 0f) != frente) continue
                    caminho.moveTo(pt[0], pt[1]); ponto(0, s, c, 0.7f); caminho.lineTo(pt[0], pt[1])
                }
                drawPath(caminho, cor.copy(alpha = 0.3f), style = Stroke(fino * 0.8f, cap = StrokeCap.Round), blendMode = mais)
            }
            if (i == 2) {   // os pontos de luz da elipse (18)
                for (k in 0 until 18) {
                    val a = fr((k + 0.5f - 0.74f) / 18)
                    if (!mostra(2, a)) continue
                    ponto(2, sin(a * TAU), cos(a * TAU), 0.5f)
                    if ((pt[2] >= 0f) != frente) continue
                    val r = max(0.8f, larg[2] * 0.24f * pt[3]); val c = Offset(pt[0], pt[1])
                    drawCircle(cor.copy(alpha = 0.25f), r * 2.4f, c, blendMode = mais)
                    drawCircle(lerp(cor, branco, 0.4f).copy(alpha = 0.95f), r, c, blendMode = mais)
                }
            }
        }

        // As bolinhas e os rastros (o rastro fica ATRÁS dela, no sentido de onde
        // veio): três trechos por rastro, mais grossos e fortes perto dela.
        fun bolinhas(i: Int, frente: Boolean) {
            val f = FORMATOS[i]; val bola = f.bola * sqrt(if (simples) 2.5f else traco); val comp = 0.55f / f.bolinhas
            for (b in 0 until f.bolinhas) {
                val u = i * 0.3f + t * f.vel * f.sentido + b.toFloat() / f.bolinhas
                for (tr in TRECHOS) {
                    val kk = tr[2]; val um = u - f.sentido * comp * (1 - (tr[0] + tr[1]) / 2)
                    ponto(i, sin(um * TAU), cos(um * TAU), 0.5f)
                    if ((pt[2] >= 0f) != frente) continue
                    val escala = pt[3]
                    val caminho = Path()
                    for (j in 0..5) {
                        val uu = u - f.sentido * comp * (1 - (tr[0] + (tr[1] - tr[0]) * j / 5))
                        ponto(i, sin(uu * TAU), cos(uu * TAU), 0.5f)
                        if (j == 0) caminho.moveTo(pt[0], pt[1]) else caminho.lineTo(pt[0], pt[1])
                    }
                    val lg = max(0.8f, bola * 0.9f * (0.2f + 0.8f * kk) * escala)
                    drawPath(caminho, cor.copy(alpha = (kk * kk * 0.22f * brilho).coerceIn(0f, 1f)),
                        style = Stroke(lg * 4.5f, cap = StrokeCap.Round, join = StrokeJoin.Round), blendMode = mais)
                    drawPath(caminho, lerp(cor, branco, kk * 0.6f).copy(alpha = (kk * kk * 1.7f).coerceAtMost(1f)),
                        style = Stroke(lg * 1.3f, cap = StrokeCap.Round, join = StrokeJoin.Round), blendMode = mais)
                }
                ponto(i, sin(u * TAU), cos(u * TAU), 0.5f)
                if ((pt[2] >= 0f) != frente) continue
                val rb = max(1.2f, bola * pt[3]); val c = Offset(pt[0], pt[1])
                drawCircle(Brush.radialGradient(0f to lerp(cor, branco, 0.7f).copy(alpha = (0.8f * brilho).coerceIn(0f, 1f)),
                    0.3f to cor.copy(alpha = (0.3f * brilho).coerceIn(0f, 1f)), 1f to cor.copy(alpha = 0f), center = c, radius = rb * 6),
                    rb * 6, c, blendMode = mais)
                drawCircle(lerp(cor, branco, 0.75f).copy(alpha = opaco), rb, c, blendMode = mais)
            }
        }

        for (i in 0 until 3) { argola(i, false); bolinhas(i, false) }

        // O núcleo: disco opaco (esconde o que está atrás) com a borda acesa.
        val rn = RN * esc / camZ
        drawCircle(Brush.radialGradient(
            0f to lerp(fundo, lerp(cor, branco, 0.45f), 0.42f * opaco), 0.55f to lerp(fundo, cor, 0.24f * opaco),
            0.86f to lerp(fundo, cor, 0.42f * opaco), 1f to lerp(fundo, cor, 0.85f * opaco),
            center = Offset(cx - rn * 0.15f, cy - rn * 0.2f), radius = rn), rn, center)
        // O brilho da borda, vazando para fora (o bloom do 3D).
        drawCircle(Brush.radialGradient(0.56f to cor.copy(alpha = 0f), 0.68f to cor.copy(alpha = 0.32f * brilho),
            1f to cor.copy(alpha = 0f), center = center, radius = rn * 1.45f), rn * 1.45f, center, blendMode = mais)

        if (!simples) {
            // A casca geodésica (só a metade da frente: a de trás fica escondida).
            val mn = mul(ra, mul(rx(t * 0.05f), ry(t * 0.12f))); val g = Geodesica.pontos
            for (i in 0 until Geodesica.n) {
                val x = g[i * 3]; val y = g[i * 3 + 1]; val z = g[i * 3 + 2]
                val zz = mn[6] * x + mn[7] * y + mn[8] * z; val f = esc / (camZ - zz)
                px[i] = cx + (mn[0] * x + mn[1] * y + mn[2] * z) * f; py[i] = cy - (mn[3] * x + mn[4] * y + mn[5] * z) * f; pz[i] = zz
            }
            val fc = Geodesica.faces
            for (i in fc.indices step 3) {   // os painéis que acendem devagar
                var on = sin(t * 0.6f + sorteio[i / 3] * 40) * 0.5f + 0.5f
                if (on < 0.83f || pz[fc[i]] + pz[fc[i + 1]] + pz[fc[i + 2]] < 0f) continue
                on = (on - 0.82f) / 0.18f
                val tri = Path().apply { moveTo(px[fc[i]], py[fc[i]]); lineTo(px[fc[i + 1]], py[fc[i + 1]]); lineTo(px[fc[i + 2]], py[fc[i + 2]]); close() }
                drawPath(tri, cor.copy(alpha = on * on * (3 - 2 * on) * 0.35f), blendMode = mais)
            }
            val ar = Geodesica.arestas; val malha = Path()
            for (i in ar.indices step 2) {
                if (pz[ar[i]] + pz[ar[i + 1]] < -0.05f) continue
                malha.moveTo(px[ar[i]], py[ar[i]]); malha.lineTo(px[ar[i + 1]], py[ar[i + 1]])
            }
            drawPath(malha, lerp(cor, branco, 0.15f).copy(alpha = 0.55f * opaco), style = Stroke(max(0.6f, lado * 0.0018f)), blendMode = mais)
            val rp = max(0.7f, lado * 0.0025f); val no = lerp(cor, branco, 0.4f).copy(alpha = 0.9f * opaco)
            for (i in 0 until Geodesica.n) if (pz[i] > 0f) drawCircle(no, rp, Offset(px[i], py[i]), blendMode = mais)
        }

        for (i in 0 until 3) { argola(i, true); bolinhas(i, true) }
    }
}

