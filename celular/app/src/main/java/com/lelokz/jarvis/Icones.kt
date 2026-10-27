package com.lelokz.jarvis

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Os ícones da janela nova, com os MESMOS caminhos SVG do PC
 * (`jarvis/interface/qml/Tema.qml`, caixa de 24×24): o app e a janela têm a
 * mesma cara.
 */
object Icones {
    private fun traco(d: String, espessura: Float = 1.8f): ImageVector =
        ImageVector.Builder(defaultWidth = 24.dp, defaultHeight = 24.dp,
            viewportWidth = 24f, viewportHeight = 24f).apply {
            addPath(PathParser().parsePathString(d).toNodes(), stroke = SolidColor(Color.White),
                strokeLineWidth = espessura, strokeLineCap = StrokeCap.Round, strokeLineJoin = StrokeJoin.Round)
        }.build()

    private fun cheio(d: String): ImageVector =
        ImageVector.Builder(defaultWidth = 24.dp, defaultHeight = 24.dp,
            viewportWidth = 24f, viewportHeight = 24f).apply {
            addPath(PathParser().parsePathString(d).toNodes(), fill = SolidColor(Color.White))
        }.build()

    val menu = traco("M4 7h16M4 12h16M4 17h16", 2f)
    val mais = traco("M12 5v14M5 12h14", 2.6f)
    val lupa = traco("M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14M20 20l-3.5-3.5", 2f)
    val voz = traco("M9 6a3 3 0 0 1 6 0v5a3 3 0 0 1-6 0zM5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21")
    val relogio = traco("M10 6h4a4 4 0 0 1 4 4v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4v-4a4 4 0 0 1 4-4zM9 6l1-3h4l1 3M9 18l1 3h4l1-3")
    val celular = traco("M9.5 2.5h5a2.5 2.5 0 0 1 2.5 2.5v14a2.5 2.5 0 0 1-2.5 2.5h-5A2.5 2.5 0 0 1 7 19V5a2.5 2.5 0 0 1 2.5-2.5zM11 18.5h2")
    val teclado = traco("M5 6h14a2.5 2.5 0 0 1 2.5 2.5v7A2.5 2.5 0 0 1 19 18H5a2.5 2.5 0 0 1-2.5-2.5v-7A2.5 2.5 0 0 1 5 6zM7.5 14.5h9M6.5 10.5h1M10 10.5h1M13.5 10.5h1M17 10.5h1")
    val memoria = traco("M9 4a3 3 0 0 0-3 3v.2A3 3 0 0 0 4 10a3 3 0 0 0 1 2.2A3 3 0 0 0 6 17a3 3 0 0 0 3 3V4zM15 4a3 3 0 0 1 3 3v.2A3 3 0 0 1 20 10a3 3 0 0 1-1 2.2A3 3 0 0 1 18 17a3 3 0 0 1-3 3V4z")
    val ajustes = traco("M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4")
    val clipe = traco("M16.8 7.2L9 15a2.4 2.4 0 0 0 3.4 3.4L20 10.8a4.2 4.2 0 0 0-6-6L5.6 13.2a6.2 6.2 0 0 0 8.8 8.8L21 15.4", 1.7f)
    val enviar = traco("M12 19V5M5.5 11.5L12 5l6.5 6.5", 2.4f)
    val raio = cheio("M13 2.5L5 13.5h6l-1 8 8-11h-6z")
    val barras = cheio("M4 18h3v-3H4zM10.5 18h3v-7h-3zM17 18h3V7h-3z")
    val copiar = traco("M9 9h10a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-8a2 2 0 0 1-2-2zM5 15V5a2 2 0 0 1 2-2h8")
    val certo = traco("M5 12.5l4.5 4.5L19 7", 2.2f)
    val seta = traco("M7 10l5 5 5-5")
    val direita = traco("M10 7l5 5-5 5")
    val fechar = traco("M7 7l10 10M17 7L7 17")
    val som = traco("M4 9v6h4l5 4V5L8 9H4zM16 9a4 4 0 0 1 0 6")
    val mudo = traco("M4 9v6h4l5 4V5L8 9H4zM16.5 9.5l5 5M21.5 9.5l-5 5")

    fun daOrigem(o: String): ImageVector = when (o) {
        "voz" -> voz
        "relogio" -> relogio
        "celular" -> celular
        "nova" -> mais
        else -> teclado
    }
}

@Composable
fun Ic(v: ImageVector, cor: Color, tamanho: Dp = 20.dp, modifier: Modifier = Modifier) =
    Icon(v, contentDescription = null, tint = cor, modifier = modifier.size(tamanho))

/**
 * O átomo parado (o avatar das respostas, o estado na gaveta): o desenho dos
 * ícones (IconeAtomo.kt), o mesmo da bandeja do PC e do ícone do app. A camada
 * própria é para os cortes em volta das argolas apagarem só o átomo.
 */
@Composable
fun AtomoFixo(cor: Color, tamanho: Dp, modifier: Modifier = Modifier) {
    Canvas(modifier.size(tamanho).graphicsLayer(compositingStrategy = CompositingStrategy.Offscreen)) {
        with(IconeAtomo) { desenhar(cor) }
    }
}
