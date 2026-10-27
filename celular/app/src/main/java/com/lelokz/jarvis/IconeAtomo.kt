package com.lelokz.jarvis

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.lerp
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * O átomo parado dos ícones (o avatar das respostas, o estado na gaveta): a
 * tradução do jarvis/interface/icone_atomo.py, o mesmo desenho da bandeja do
 * PC e do ícone do app. Não é um quadro do átomo animado: é uma pose feita
 * para ser lida pequena (as argolas abertas, uma bolinha em cada, a metade da
 * frente passando na frente do núcleo com um corte em volta).
 *
 * Os cortes apagam o que está atrás (BlendMode.Clear): quem desenha precisa de
 * uma camada própria (graphicsLayer com CompositingStrategy.Offscreen).
 */
object IconeAtomo {
    private const val INCLINA = 0.34f
    private const val NUCLEO = 0.25f
    // raio, largura do traço (fração do lado), onde fica a bolinha (× π), alongamento, sentido
    private val RAIO = floatArrayOf(0.96f, 0.80f, 0.88f)
    private val LARG = floatArrayOf(0.034f, 0.022f, 0.026f)
    private val BOLA = floatArrayOf(0.16f, 0.86f, 0.13f)
    private val ALONGA = floatArrayOf(1f, 1f, 1.08f)
    private val SENTIDO = floatArrayOf(1f, -1f, 1f)

    // A casca geodésica: um icosaedro subdividido uma vez, já girado na pose.
    private val geo: Pair<FloatArray, IntArray> by lazy {
        val f = ((1 + sqrt(5.0)) / 2).toFloat()
        val v = arrayListOf(
            floatArrayOf(-1f, f, 0f), floatArrayOf(1f, f, 0f), floatArrayOf(-1f, -f, 0f), floatArrayOf(1f, -f, 0f),
            floatArrayOf(0f, -1f, f), floatArrayOf(0f, 1f, f), floatArrayOf(0f, -1f, -f), floatArrayOf(0f, 1f, -f),
            floatArrayOf(f, 0f, -1f), floatArrayOf(f, 0f, 1f), floatArrayOf(-f, 0f, -1f), floatArrayOf(-f, 0f, 1f))
        fun unir(p: FloatArray): FloatArray { val m = sqrt(p[0] * p[0] + p[1] * p[1] + p[2] * p[2]); return floatArrayOf(p[0] / m, p[1] / m, p[2] / m) }
        for (i in v.indices) v[i] = unir(v[i])
        val faces = arrayOf(intArrayOf(0, 11, 5), intArrayOf(0, 5, 1), intArrayOf(0, 1, 7), intArrayOf(0, 7, 10), intArrayOf(0, 10, 11),
            intArrayOf(1, 5, 9), intArrayOf(5, 11, 4), intArrayOf(11, 10, 2), intArrayOf(10, 7, 6), intArrayOf(7, 1, 8),
            intArrayOf(3, 9, 4), intArrayOf(3, 4, 2), intArrayOf(3, 2, 6), intArrayOf(3, 6, 8), intArrayOf(3, 8, 9),
            intArrayOf(4, 9, 5), intArrayOf(2, 4, 11), intArrayOf(6, 2, 10), intArrayOf(8, 6, 7), intArrayOf(9, 8, 1))
        val meio = HashMap<Int, Int>()
        fun m(a: Int, b: Int): Int = meio.getOrPut(min(a, b) * 1000 + max(a, b)) {
            v.add(unir(floatArrayOf(v[a][0] + v[b][0], v[a][1] + v[b][1], v[a][2] + v[b][2]))); v.size - 1
        }
        val arestas = LinkedHashSet<Int>()
        for (t in faces) {
            val (a, b, c) = Triple(t[0], t[1], t[2])
            val ab = m(a, b); val bc = m(b, c); val ca = m(c, a)
            for (tri in arrayOf(intArrayOf(a, ab, ca), intArrayOf(b, bc, ab), intArrayOf(c, ca, bc), intArrayOf(ab, bc, ca)))
                for (i in 0 until 3) { val x = tri[i]; val y = tri[(i + 1) % 3]; arestas.add(min(x, y) * 1000 + max(x, y)) }
        }
        // A pose do núcleo: gira 0,35 em Y e 0,5 em X (como no PC).
        val cx = cos(0.5f); val sx = sin(0.5f); val cy = cos(0.35f); val sy = sin(0.35f)
        val pts = FloatArray(v.size * 3)
        v.forEachIndexed { i, p ->
            val x1 = p[0] * cy + p[2] * sy; val z1 = -p[0] * sy + p[2] * cy
            pts[i * 3] = x1; pts[i * 3 + 1] = p[1] * cx - z1 * sx; pts[i * 3 + 2] = p[1] * sx + z1 * cx
        }
        pts to arestas.flatMap { listOf(it / 1000, it % 1000) }.toIntArray()
    }

    private fun clara(cor: Color, k: Float) = lerp(cor, Color.White, k)

    fun DrawScope.desenhar(cor: Color) {
        val lado = min(size.width, size.height)
        val c = Offset(size.width / 2, size.height / 2)
        val k = lado / 2 * (if (lado >= 64) 0.9f else 0.97f)
        val minusculo = lado < 24
        val detalhe = lado >= 96
        val medio = lado >= 40
        val grosso = if (lado < 40) 1.6f else 1f
        fun px(f: Float) = max(f * lado * grosso, if (lado < 24) 1.3f else 1.5f)
        val luz = clara(cor, 0.55f)

        fun ponto(i: Int, t: Float): Offset {
            val rx = RAIO[i] * ALONGA[i]; val ry = RAIO[i] * INCLINA / ALONGA[i]
            val x = cos(t) * rx; val y = sin(t) * ry
            val fi = i * PI.toFloat() / 3 - PI.toFloat() / 6
            return Offset(c.x + k * (x * cos(fi) - y * sin(fi)), c.y + k * (x * sin(fi) + y * cos(fi)))
        }
        fun caminho(i: Int, t0: Float, t1: Float, n: Int = 120) = Path().apply {
            val p0 = ponto(i, t0); moveTo(p0.x, p0.y)
            for (j in 1..n) { val p = ponto(i, t0 + (t1 - t0) * j / n); lineTo(p.x, p.y) }
        }

        fun argola(i: Int, frente: Boolean) {
            val t0 = if (frente) 0f else PI.toFloat()
            val t1 = t0 + PI.toFloat()
            val w = px(LARG[i])
            val tom = if (frente) cor else cor.copy(alpha = 0.55f)
            val partes = ArrayList<Pair<Float, Float>>()
            if (detalhe && i == 0) {   // a externa: 3 partes com vãos
                val vao = 0.10f
                for (s in 0 until 3) {
                    val a0 = s * 2 * PI.toFloat() / 3 + vao / 2 + 0.4f
                    val a1 = (s + 1) * 2 * PI.toFloat() / 3 - vao / 2 + 0.4f
                    for (d in floatArrayOf(0f, 2 * PI.toFloat())) {
                        val lo = max(a0 - d, t0); val hi = min(a1 - d, t1)
                        if (lo < hi) partes.add(lo to hi)
                    }
                }
            } else partes.add(t0 to t1)
            for ((a0, a1) in partes) {
                val path = caminho(i, a0, a1)
                if (frente && medio)   // o corte: some o que está atrás, em volta do traço
                    drawPath(path, Color.Black, style = Stroke(w + px(0.022f), cap = StrokeCap.Round), blendMode = BlendMode.Clear)
                when {
                    detalhe && i == 0 -> {   // faixa larga: corpo fraco e as duas bordas acesas
                        drawPath(path, tom.copy(alpha = tom.alpha * 0.35f), style = Stroke(w * 1.9f, cap = StrokeCap.Butt))
                        for (b in intArrayOf(-1, 1)) {
                            val q = Path()
                            val n = 120
                            for (j in 0..n) {
                                val t = a0 + (a1 - a0) * j / n
                                val p = ponto(i, t)
                                val pa = ponto(i, a0 + (a1 - a0) * max(j - 1, 0) / n)
                                val pb = ponto(i, a0 + (a1 - a0) * min(j + 1, n) / n)
                                val dx = pb.x - pa.x; val dy = pb.y - pa.y
                                val m = hypot(dx, dy).takeIf { it > 0 } ?: 1f
                                val ox = p.x - dy / m * w * 0.8f * b; val oy = p.y + dx / m * w * 0.8f * b
                                if (j == 0) q.moveTo(ox, oy) else q.lineTo(ox, oy)
                            }
                            drawPath(q, tom, style = Stroke(w * 0.42f, cap = StrokeCap.Butt))
                        }
                    }
                    detalhe && i == 1 ->     // a interna: tracejada
                        drawPath(path, tom, style = Stroke(w, cap = StrokeCap.Butt,
                            pathEffect = PathEffect.dashPathEffect(floatArrayOf(2.2f * w, 1.4f * w))))
                    else -> drawPath(path, tom, style = Stroke(w, cap = StrokeCap.Round))
                }
                if (detalhe && i == 2)   // a do meio: pontos de luz
                    for (j in 0 until 12) {
                        val t = j * 2 * PI.toFloat() / 12 + 0.26f
                        if (t in a0..a1 || (t - 2 * PI.toFloat()) in a0..a1) drawCircle(luz, w * 0.6f, ponto(i, t))
                    }
            }
        }

        fun bolinha(i: Int) {
            val t = BOLA[i] * PI.toFloat()
            val r = px(if (lado >= 40) 0.038f else 0.034f)
            // o rastro: um arco atrás da bolinha, afinando e apagando
            val n = if (minusculo) 0 else 26
            val comp = 1.3f
            for (j in 0 until n) {
                val a = t - SENTIDO[i] * comp * (1 - j.toFloat() / n)
                val b = t - SENTIDO[i] * comp * (1 - (j + 1).toFloat() / n)
                val f = (j + 1).toFloat() / n
                drawLine(luz.copy(alpha = f.pow(1.6f)), ponto(i, a), ponto(i, b),
                    strokeWidth = max(r * 1.3f * (0.25f + 0.75f * f), 0.8f), cap = StrokeCap.Round)
            }
            val o = ponto(i, t)
            if (medio) drawCircle(Color.Black, r + px(0.016f), o, blendMode = BlendMode.Clear)
            drawCircle(Brush.radialGradient(0f to Color.White, 0.55f to clara(cor, 0.75f), 1f to luz, center = o, radius = r), r, o)
        }

        fun nucleo() {
            val rn = k * NUCLEO
            if (medio) drawCircle(Color.Black, rn + px(0.03f), c, blendMode = BlendMode.Clear)
            val brilho = Offset(c.x - rn * 0.3f, c.y - rn * 0.35f)
            val fundo = if (minusculo) Brush.radialGradient(0f to clara(cor, 0.6f), 1f to cor, center = brilho, radius = rn * 1.25f)
            else Brush.radialGradient(0f to clara(cor, 0.35f), 0.55f to lerp(Color.Black, cor, 0.45f), 1f to lerp(Color.Black, cor, 0.22f),
                center = brilho, radius = rn * 1.25f)
            drawCircle(fundo, rn, c)
            if (detalhe) {   // a casca geodésica: só as arestas da frente
                val (p, ar) = geo
                for (e in ar.indices step 2) {
                    val a = ar[e]; val b = ar[e + 1]
                    val z = (p[a * 3 + 2] + p[b * 3 + 2]) / 2
                    if (z < 0.05f) continue
                    drawLine(cor.copy(alpha = 0.25f + 0.5f * z), Offset(c.x + p[a * 3] * rn, c.y - p[a * 3 + 1] * rn),
                        Offset(c.x + p[b * 3] * rn, c.y - p[b * 3 + 1] * rn), strokeWidth = max(lado / 300, 0.8f))
                }
            }
            drawCircle(luz, rn, c, style = Stroke(px(0.016f)))
        }

        for (i in 0 until 3) argola(i, false)
        nucleo()
        for (i in 0 until 3) argola(i, true)
        for (i in 0 until 3) bolinha(i)
    }
}
