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
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.scale
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin
import kotlin.random.Random

/**
 * O átomo da janela do PC (`jarvis/interface/qml/Esfera.qml`), no celular.
 *
 * Cada anel é desenhado em DUAS METADES: a de trás antes do núcleo, a da
 * frente depois. O que anima é o achatamento da elipse, como um aro girando
 * em torno do eixo horizontal; quando ele passa de perfil, as metades trocam,
 * e a troca é invisível porque as duas coincidem numa linha. O disco opaco
 * do meio é o que faz o "atrás" existir.
 *
 * O estado vira número (escala, velocidade, brilho, turbulência, cor), e todo
 * número passa por uma animação: nada troca num piscar.
 */
private data class Anel(val vel: Float, val fase: Float, val raio: Float, val inclinacao: Float)

// Os mesmos três anéis do PC. 36000 × 0,73 e × 1,31 fecham voltas inteiras.
private val ANEIS = listOf(
    Anel(1.00f, 0f, 0.46f, 0f),
    Anel(0.73f, 90f, 0.39f, 62f),
    Anel(1.31f, 210f, 0.32f, 121f),
)

private class Particula(var x: Float, var y: Float, var vx: Float, var vy: Float,
                        var vida: Float, val frente: Boolean)

@Composable
fun Atomo(
    cor: Color,
    escala: Float,
    velocidade: Float,
    brilho: Float,
    turbulencia: Float,
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
    val turbA by animateFloatAsState(turbulencia, tween(700), label = "turb")
    val nivelA by animateFloatAsState(nivel, tween(120), label = "nivel")
    val respiroT = rememberInfiniteTransition(label = "respiro")
    val respiroAnim by respiroT.animateFloat(
        1f, 1.055f, infiniteRepeatable(tween(2600), RepeatMode.Reverse), label = "respiro")
    val respiro = if (pulsando && !parado) respiroAnim else 1f

    // O giro é SOMADO a cada quadro (como no PC): trocar a velocidade vale no
    // quadro seguinte, sem pulo.
    var giro by remember { mutableFloatStateOf(0f) }
    var quadro by remember { mutableLongStateOf(0L) }
    val particulas = remember { ArrayList<Particula>() }
    var acumulado by remember { mutableFloatStateOf(0f) }
    val vel by rememberUpdatedState(velA)
    val turb by rememberUpdatedState(turbA)
    val niv by rememberUpdatedState(nivelA)
    val parou by rememberUpdatedState(parado)

    LaunchedEffect(Unit) {
        var antes = 0L
        while (true) {
            withFrameNanos { t ->
                val dt = if (antes == 0L) 0f else ((t - antes) / 1e9f).coerceAtMost(0.1f)
                antes = t
                if (!parou) {
                    giro = (giro + dt * 40f * vel) % 36000f
                    // Partículas: nascem num anel em volta do núcleo e se espalham.
                    acumulado += dt * (7f + turb * 26f + niv * 16f) * 2f
                    while (acumulado >= 1f && particulas.size < 90) {
                        acumulado -= 1f
                        val a = Random.nextFloat() * 2f * PI.toFloat()
                        val r = 0.18f + Random.nextFloat() * 0.28f
                        val m = (4f + turb * 26f + niv * 10f + (Random.nextFloat() - 0.5f) * 8f) / 300f
                        val d = Random.nextFloat() * 2f * PI.toFloat()
                        particulas.add(Particula(cos(a) * r, sin(a) * r, cos(d) * m, sin(d) * m,
                            2.8f, Random.nextBoolean()))
                    }
                    val it = particulas.iterator()
                    while (it.hasNext()) {
                        val p = it.next()
                        p.vida -= dt
                        if (p.vida <= 0f) it.remove() else { p.x += p.vx * dt; p.y += p.vy * dt }
                    }
                }
                quadro = t
            }
        }
    }

    Canvas(modifier) {
        if (quadro < 0L) return@Canvas // ler o quadro aqui faz redesenhar a cada quadro
        val lado = size.minDimension
        val c = center
        scale(escalaA * respiro * (1f + nivelA * 0.08f), c) {
            // Halo: o brilho borrado do PC, feito com um gradiente largo.
            drawCircle(
                Brush.radialGradient(
                    listOf(corA.copy(alpha = 0.20f * brilhoA), Color.Transparent),
                    center = c, radius = lado * 0.55f),
                radius = lado * 0.55f, center = c)
            for (anel in ANEIS) meioAnel(anel, giro, lado, corA, brilhoA, atras = true)
            particulas(particulas, frente = false, lado, corA, alpha = 0.55f)
            drawCircle(fundo, radius = lado * 0.25f, center = c)
            drawCircle(
                Brush.radialGradient(
                    0f to corA.copy(alpha = 0.62f * brilhoA),
                    0.6f to corA.copy(alpha = 0.14f * brilhoA),
                    1f to Color.Transparent,
                    center = c, radius = lado * (0.27f + nivelA * 0.04f)),
                radius = lado * 0.30f, center = c)
            particulas(particulas, frente = true, lado, corA, alpha = 1f)
            for (anel in ANEIS) meioAnel(anel, giro, lado, corA, brilhoA, atras = false)
        }
    }
}

private fun DrawScope.meioAnel(anel: Anel, giro: Float, lado: Float, cor: Color, brilho: Float, atras: Boolean) {
    val angulo = (giro * anel.vel + anel.fase) * PI.toFloat() / 180f
    val cosseno = cos(angulo)
    val rx = lado * anel.raio
    // Nunca zera de todo: um aro exatamente de perfil some, e some feio.
    val ry = maxOf(lado * 0.012f, rx * abs(cosseno))
    val metadeDeCima = atras == (cosseno >= 0f)
    rotate(anel.inclinacao, center) {
        drawArc(
            color = cor.copy(alpha = ((if (atras) 0.26f else 0.52f) * brilho).coerceAtMost(1f)),
            startAngle = if (metadeDeCima) 180f else 0f,
            sweepAngle = 180f,
            useCenter = false,
            topLeft = Offset(center.x - rx, center.y - ry),
            size = Size(rx * 2, ry * 2),
            style = Stroke(width = (if (atras) 1.2f else 1.7f) * density, cap = StrokeCap.Round),
        )
    }
}

private fun DrawScope.particulas(lista: List<Particula>, frente: Boolean, lado: Float, cor: Color, alpha: Float) {
    for (p in lista) {
        if (p.frente != frente) continue
        val f = p.vida / 2.8f
        drawCircle(
            cor.copy(alpha = alpha * f),
            radius = 1.6f * density * f,
            center = Offset(center.x + p.x * lado, center.y + p.y * lado),
        )
    }
}
