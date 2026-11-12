package com.lelokz.painel

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.lelokz.jarvis.Atomo
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.YearMonth
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

// As cores da janela do Painel no PC (jarvis/youtube/Painel.qml).
private val Fundo = Color(0xFF0B0A10)
private val Sup = Color(0xFF15131D)
private val Sup2 = Color(0xFF1B1826)
private val Traco = Color(0xFF262037)
private val Trilho = Color(0xFF221D30)
private val Lado = Color(0xFF0F0D16)
private val Texto = Color(0xFFECE9F5)
private val Medio = Color(0xFFBDB6D0)
private val Fraco = Color(0xFF857D9C)
private val MuitoFraco = Color(0xFF5A536D)
private val Roxo = Color(0xFFA78BFA)
private val RoxoForte = Color(0xFF8B5CF6)
private val RoxoEscuro = Color(0xFF4A3D78)
private val Verde = Color(0xFF4ADE80)
private val Vermelho = Color(0xFFF87171)
private val Amarelo = Color(0xFFFBBF24)
private val Escuro = Color(0xFF120D22)

@OptIn(ExperimentalTextApi::class)
private val Inter = FontFamily(listOf(400, 500, 600, 700).map { p ->
    Font(R.font.inter, FontWeight(p), variationSettings = FontVariation.Settings(FontVariation.weight(p)))
})

private object Ic {
    private fun t(d: String): ImageVector = ImageVector.Builder(defaultWidth = 24.dp, defaultHeight = 24.dp,
        viewportWidth = 24f, viewportHeight = 24f).apply {
        addPath(PathParser().parsePathString(d).toNodes(), stroke = SolidColor(Color.White), strokeLineWidth = 1.8f,
            strokeLineCap = StrokeCap.Round, strokeLineJoin = StrokeJoin.Round)
    }.build()
    val casa = t("M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z")
    val cal = t("M6 5h12a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V8a3 3 0 0 1 3-3zM3 10h18M8 3v4M16 3v4")
    val prod = t("M4.5 4h2a1.5 1.5 0 0 1 1.5 1.5v13a1.5 1.5 0 0 1-1.5 1.5h-2A1.5 1.5 0 0 1 3 18.5v-13A1.5 1.5 0 0 1 4.5 4zM11.5 4h2A1.5 1.5 0 0 1 15 5.5v7a1.5 1.5 0 0 1-1.5 1.5h-2a1.5 1.5 0 0 1-1.5-1.5v-7A1.5 1.5 0 0 1 11.5 4zM18.5 4h1A1.5 1.5 0 0 1 21 5.5v10a1.5 1.5 0 0 1-1.5 1.5h-1a1.5 1.5 0 0 1-1.5-1.5v-10A1.5 1.5 0 0 1 18.5 4z")
    val vid = t("M6 5h12a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V8a3 3 0 0 1 3-3zM10 9l5 3-5 3z")
    val com = t("M4 5h16v11H9l-5 4z")
    val att = t("M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7")
    val volta = t("m15 18-6-6 6-6")
    val seta = t("m9 18 6-6-6-6")
    val mais = t("M12 5v14M5 12h14")
    val busca = t("M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zM20 20l-3.5-3.5")
    val clipe = t("m21 12-8.5 8.5a5 5 0 0 1-7-7L14 5a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 8")
    val coracao = t("M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.5-7 10-7 10z")
    val fechar = t("M6 6l12 12M18 6 6 18")
}

class MainActivity : ComponentActivity() {
    private val modelo: Modelo by viewModels()

    override fun onCreate(estado: Bundle?) {
        super.onCreate(estado)
        enableEdgeToEdge()
        setContent { Raiz(modelo) }
    }

    override fun onResume() { super.onResume(); modelo.aoAbrir() }
    override fun onPause() { super.onPause(); modelo.aoSair() }
}

// ---------------------------------------------------------------------------
// Pecinhas
// ---------------------------------------------------------------------------

@Composable
private fun T(texto: String, cor: Color = Texto, tam: Float = 14f, peso: FontWeight = FontWeight.Normal,
              modifier: Modifier = Modifier, linhas: Int = Int.MAX_VALUE, alinha: TextAlign? = null, altura: Float = 0f) {
    Text(texto, modifier, color = cor, fontSize = tam.sp, fontWeight = peso, fontFamily = Inter, maxLines = linhas,
        overflow = TextOverflow.Ellipsis, textAlign = alinha, lineHeight = if (altura > 0) altura.sp else (tam * 1.35f).sp)
}

@Composable
private fun Cap(texto: String, modifier: Modifier = Modifier, cor: Color = Fraco) =
    Text(texto.uppercase(), modifier, color = cor, fontSize = 10.5.sp, letterSpacing = 1.1.sp,
        fontWeight = FontWeight.Medium, fontFamily = Inter)

@Composable
private fun Cartao(modifier: Modifier = Modifier, borda: Color = Traco, onClick: (() -> Unit)? = null,
                   conteudo: @Composable ColumnScope.() -> Unit) {
    val forma = RoundedCornerShape(16.dp)
    Column(modifier.fillMaxWidth().clip(forma).background(Sup).border(1.dp, borda, forma)
        .let { if (onClick != null) it.clickable(onClick = onClick) else it }
        .padding(horizontal = 16.dp, vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(10.dp), content = conteudo)
}

@Composable
private fun Chip(texto: String, on: Boolean, n: Int? = null, onClick: () -> Unit) {
    val forma = RoundedCornerShape(18.dp)
    Row(Modifier.clip(forma).background(if (on) Roxo.copy(alpha = 0.16f) else Sup)
        .border(1.dp, if (on) Color(0xFF5B4A8F) else Traco, forma).clickable(onClick = onClick)
        .padding(horizontal = 13.dp, vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
        T(texto, if (on) Texto else Medio, 13f, if (on) FontWeight.SemiBold else FontWeight.Normal)
        if (n != null) { Spacer(Modifier.width(5.dp)); T("$n", Fraco, 12f, FontWeight.Medium) }
    }
}

@Composable
private fun Botao(texto: String, modifier: Modifier = Modifier, forte: Boolean = false, cor: Color = Medio,
                  ativo: Boolean = true, onClick: () -> Unit) {
    val forma = RoundedCornerShape(12.dp)
    Box(modifier.clip(forma).background(if (forte) (if (ativo) Roxo else Roxo.copy(alpha = 0.4f)) else Sup2)
        .let { if (forte) it else it.border(1.dp, Traco, forma) }
        .clickable(enabled = ativo, onClick = onClick).padding(horizontal = 14.dp, vertical = 11.dp),
        contentAlignment = Alignment.Center) {
        T(texto, if (forte) Escuro else cor, 13.5f, FontWeight.SemiBold, linhas = 1)
    }
}

@Composable
private fun Icone(i: ImageVector, cor: Color = Medio, tam: Dp = 20.dp) =
    Icon(i, null, tint = cor, modifier = Modifier.size(tam))

@Composable
private fun Campo(valor: String, aoMudar: (String) -> Unit, dica: String = "", modifier: Modifier = Modifier,
                  linhas: Int = 1, teclado: KeyboardType = KeyboardType.Text, tam: Float = 14f) {
    val forma = RoundedCornerShape(12.dp)
    BasicTextField(valor, aoMudar, modifier.fillMaxWidth(), singleLine = linhas == 1, minLines = linhas,
        textStyle = TextStyle(color = Texto, fontSize = tam.sp, fontFamily = Inter, lineHeight = (tam * 1.45f).sp),
        cursorBrush = SolidColor(Roxo), keyboardOptions = KeyboardOptions(keyboardType = teclado),
        decorationBox = { dentro ->
            Box(Modifier.clip(forma).background(Sup2).border(1.dp, Color(0xFF2F2845), forma)
                .padding(horizontal = 13.dp, vertical = 11.dp)) {
                if (valor.isEmpty()) T(dica, Fraco, tam)
                dentro()
            }
        })
}

/** A barra de progresso roxa (a meta de inscritos, as análises). */
@Composable
private fun Barra(fracao: Float, modifier: Modifier = Modifier, altura: Dp = 8.dp) {
    Box(modifier.height(altura).clip(RoundedCornerShape(altura / 2)).background(Trilho)) {
        Box(Modifier.fillMaxWidth(fracao.coerceIn(0.01f, 1f)).height(altura).clip(RoundedCornerShape(altura / 2))
            .background(Brush.horizontalGradient(listOf(RoxoForte, Roxo))))
    }
}

@Composable
private fun Thumb(modelo: Modelo, caminho: String, largura: Dp, modifier: Modifier = Modifier, duracao: Int = 0) {
    var img by remember(caminho) { mutableStateOf(modelo.thumbGuardada(caminho)) }
    LaunchedEffect(caminho) { if (img == null && caminho.isNotEmpty()) img = modelo.thumb(caminho) }
    Box(modifier.width(largura).aspectRatio(16f / 9f).clip(RoundedCornerShape(9.dp)).background(Sup2)) {
        img?.let { Image(it.asImageBitmap(), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
        if (duracao > 0) T("%d:%02d".format(duracao / 60, duracao % 60), Color.White, 10.5f,
            modifier = Modifier.align(Alignment.BottomEnd).padding(5.dp).clip(RoundedCornerShape(4.dp))
                .background(Color.Black.copy(alpha = 0.8f)).padding(horizontal = 5.dp, vertical = 1.dp))
    }
}

private val SEM = listOf("dom", "seg", "ter", "qua", "qui", "sex", "sáb")
private fun semana(d: java.time.DayOfWeek) = SEM[d.value % 7]
private fun dh(z: ZonedDateTime) = "${semana(z.dayOfWeek)} ${z.dayOfMonth}/${z.monthValue} às %02d:%02d".format(z.hour, z.minute)
private fun ha(z: ZonedDateTime?): String {
    z ?: return ""
    val min = ChronoUnit.MINUTES.between(z, ZonedDateTime.now())
    return when {
        min < 60 -> "há ${maxOf(1, min)} min"
        min < 60 * 24 -> "há ${min / 60} h"
        min < 60 * 48 -> "ontem"
        else -> "há ${min / 60 / 24} dias"
    }
}
private val MESES = listOf("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
    "Setembro", "Outubro", "Novembro", "Dezembro")

// ---------------------------------------------------------------------------
// A raiz
// ---------------------------------------------------------------------------

@Composable
private fun Raiz(modelo: Modelo) {
    Box(Modifier.fillMaxSize().background(Fundo)) {
        if (!modelo.configurado.value) Ligar(modelo) else Painel(modelo)
        Aviso(modelo, Modifier.align(Alignment.TopCenter).statusBarsPadding().padding(top = 64.dp))
        if (modelo.avisoAtualizacao.value) AvisoAtualizacao(modelo)
    }
    LaunchedEffect(Atualizador.falhou.value) {
        if (Atualizador.falhou.value.isNotEmpty()) {
            modelo.avisar(Atualizador.falhou.value, false)
            modelo.atualizando.floatValue = -1f
            Atualizador.falhou.value = ""
        }
    }
}

/** A primeira vez: pega a ligação com o PC do app da NOVA (ou cola o link). */
@Composable
private fun Ligar(modelo: Modelo) {
    val contexto = LocalContext.current
    var link by remember { mutableStateOf("") }
    val pegar = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        val b = r.data?.getStringExtra("base").orEmpty()
        val c = r.data?.getStringExtra("chave").orEmpty()
        if (b.isEmpty() || c.isEmpty() || !modelo.configurar(b, c))
            modelo.avisar("O app da NOVA ainda não está ligado ao PC.", false)
    }
    Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding().padding(28.dp),
        verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Atomo(Roxo, 1f, 0.7f, 0.9f, 0f, 0f, false, true, Fundo, Modifier.size(150.dp))
        Spacer(Modifier.height(18.dp))
        T("Painel do Canal", Texto, 26f, FontWeight.SemiBold)
        Spacer(Modifier.height(8.dp))
        T("O teu canal no celular, ligado ao PC pela mesma conexão da NOVA.", Medio, 14.5f, alinha = TextAlign.Center)
        Spacer(Modifier.height(28.dp))
        Botao("Ligar pelo app da NOVA", Modifier.fillMaxWidth(), forte = true) {
            try {
                pegar.launch(Intent("com.lelokz.jarvis.LIGACAO").setPackage("com.lelokz.jarvis"))
            } catch (e: Exception) {
                modelo.avisar("Não achei o app da NOVA (atualiza ele primeiro).", false)
            }
        }
        Spacer(Modifier.height(22.dp))
        T("ou cola o link do PC (o mesmo do app da NOVA)", Fraco, 12.5f)
        Spacer(Modifier.height(8.dp))
        Campo(link, { link = it }, "https://…#chave=…")
        Spacer(Modifier.height(10.dp))
        Botao("Ligar com o link", Modifier.fillMaxWidth(), ativo = link.isNotBlank()) {
            if (!modelo.configurarPorLink(link)) modelo.avisar("Esse link não tem a chave.", false)
        }
    }
}

@Composable
private fun Aviso(modelo: Modelo, modifier: Modifier) {
    val texto = modelo.aviso.value
    LaunchedEffect(texto) { if (texto.isNotEmpty()) { delay(3600); modelo.aviso.value = "" } }
    AnimatedVisibility(texto.isNotEmpty(), modifier, enter = fadeIn(), exit = fadeOut()) {
        val forma = RoundedCornerShape(18.dp)
        Row(Modifier.padding(horizontal = 24.dp).clip(forma).background(Sup2).border(1.dp, Traco, forma)
            .padding(horizontal = 16.dp, vertical = 9.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(7.dp).clip(CircleShape).background(if (modelo.avisoBom.value) Verde else Vermelho))
            Spacer(Modifier.width(9.dp))
            T(texto, Medio, 13f)
        }
    }
}

/** "Atualização pendente": o mesmo aviso do app da NOVA, em roxo. */
@Composable
private fun AvisoAtualizacao(modelo: Modelo) {
    BackHandler { modelo.fecharAvisoAtualizacao(false) }
    Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.45f))
        .clickable(indication = null, interactionSource = remember { MutableInteractionSource() }) {},
        contentAlignment = Alignment.Center) {
        val forma = RoundedCornerShape(20.dp)
        Column(Modifier.padding(horizontal = 32.dp).fillMaxWidth().clip(forma).background(Sup2)
            .border(1.dp, Traco, forma).padding(22.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Atomo(Roxo, 1f, 0.8f, 1f, 0f, 0f, false, false, Sup2, Modifier.size(28.dp))
                Spacer(Modifier.width(10.dp))
                T("Atualização pendente", Texto, 17f, FontWeight.SemiBold)
            }
            Spacer(Modifier.height(10.dp))
            T("Tem uma versão nova do Painel do Canal. Deseja atualizar agora?", Medio, 14f, altura = 20f)
            Spacer(Modifier.height(20.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = { modelo.fecharAvisoAtualizacao(false) }, modifier = Modifier.weight(1f),
                    border = BorderStroke(1.dp, Traco)) { T("Não", Medio, 14f) }
                Button(onClick = { modelo.fecharAvisoAtualizacao(true) }, modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Roxo, contentColor = Escuro)) {
                    T("Sim", Escuro, 14f, FontWeight.SemiBold)
                }
            }
        }
    }
}

/** O retângulo pequeno no topo: versão nova (o aviso grande já fechado) ou a barrinha do download. */
@Composable
private fun RetanguloAtualizacao(modelo: Modelo, modifier: Modifier) {
    val forma = RoundedCornerShape(10.dp)
    val p = modelo.atualizando.floatValue
    Row(modifier.clip(forma).background(Sup2).border(1.dp, Traco, forma)
        .clickable(enabled = p < 0f) { modelo.avisoAtualizacao.value = true }
        .padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        when {
            p < 0f -> {
                Box(Modifier.size(7.dp).clip(CircleShape).background(Roxo))
                Spacer(Modifier.width(8.dp)); T("Atualização disponível", Medio, 12f)
            }
            p > 1f -> T("Instalando…", Medio, 12f)
            else -> {
                T("Baixando atualização", Medio, 12f); Spacer(Modifier.width(10.dp))
                Barra(p, Modifier.width(90.dp), 5.dp); Spacer(Modifier.width(8.dp))
                T("${(p * 100).toInt()}%", Texto, 12f)
            }
        }
    }
}

// ---------------------------------------------------------------------------
// O painel: topo, a página e a barra de baixo
// ---------------------------------------------------------------------------

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Painel(modelo: Modelo) {
    var aba by remember { mutableStateOf("inicio") }
    var ficha by remember { mutableStateOf<String?>(null) }        // id do vídeo aberto
    var card by remember { mutableStateOf<Card?>(null) }           // card aberto (id 0 = novo)
    var agendar by remember { mutableStateOf<Video?>(null) }       // "Mudar dia ou hora"
    val p = modelo.pacote.value

    BackHandler(aba != "inicio") { aba = if (aba == "analises") "inicio" else "inicio" }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Topo(modelo)
        val sopro = remember { Animatable(1f) }
        LaunchedEffect(aba) { sopro.snapTo(0f); sopro.animateTo(1f, tween(260, easing = FastOutSlowInEasing)) }
        Box(Modifier.weight(1f).fillMaxWidth().graphicsLayer {
            alpha = sopro.value; scaleX = 0.985f + 0.015f * sopro.value; scaleY = scaleX
        }) {
            when {
                p == null -> Vazio(if (modelo.semConexao.value) "Sem conexão com o PC.\nO PC está ligado?" else "Carregando…")
                !p.temDados -> Vazio(if (!p.conectado) "O canal ainda não foi conectado no PC." else "Sem dados ainda. Toca em atualizar lá em cima.")
                else -> when (aba) {
                    "cal" -> PaginaCalendario(modelo, p, { ficha = it.id }, { agendar = it }, { card = it })
                    "prod" -> PaginaProducao(modelo, p) { card = it }
                    "vid" -> PaginaVideos(modelo, p) { ficha = it.id }
                    "com" -> PaginaComentarios(modelo, p)
                    "analises" -> PaginaAnalises(modelo, p) { aba = "inicio" }
                    else -> PaginaInicio(modelo, p, { aba = it }, { ficha = it.id })
                }
            }
            val temAtualizacao = modelo.atualizacao.intValue != 0
            if (temAtualizacao || modelo.atualizando.floatValue >= 0f)
                RetanguloAtualizacao(modelo, Modifier.align(Alignment.TopCenter).padding(top = 4.dp))
        }
        Nav(aba, p?.naoLidos ?: 0) { aba = it }
    }

    val video = p?.videos?.firstOrNull { it.id == ficha }
    if (ficha != null && video != null) {
        ModalBottomSheet(onDismissRequest = { ficha = null }, containerColor = Sup,
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
            Ficha(modelo, video, { agendar = it }) { ficha = null }
        }
    }
    card?.let { c ->
        ModalBottomSheet(onDismissRequest = { card = null }, containerColor = Sup,
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
            EditorCard(modelo, c) { card = null }
        }
    }
    agendar?.let { v -> Agendar(modelo, v) { agendar = null } }
}

@Composable
private fun Vazio(texto: String) {
    Box(Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
        T(texto, Fraco, 14.5f, alinha = TextAlign.Center)
    }
}

@Composable
private fun Topo(modelo: Modelo) {
    val p = modelo.pacote.value
    val sub = when {
        modelo.ocupado.value -> "Falando com o YouTube…"
        modelo.semConexao.value -> "sem conexão com o PC"
        p == null -> "carregando…"
        p.atualizado <= 0 -> p.canal.titulo
        else -> {
            val min = ((System.currentTimeMillis() / 1000.0 - p.atualizado) / 60).toLong()
            "${p.canal.titulo} · atualizado " + when { min < 1 -> "agora"; min < 60 -> "há $min min"; min < 1440 -> "há ${min / 60} h"; else -> "há ${min / 1440} dias" }
        }
    }
    Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 10.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Atomo(Roxo, 1f, if (modelo.ocupado.value) 2.2f else 0.6f, if (modelo.semConexao.value) 0.3f else 0.9f, 0f, 0f,
            modelo.semConexao.value, false, Fundo, Modifier.size(36.dp))
        Spacer(Modifier.width(11.dp))
        Column(Modifier.weight(1f)) {
            T("Painel do Canal", Texto, 17f, FontWeight.SemiBold)
            T(sub, Fraco, 12f, linhas = 1)
        }
        val forma = RoundedCornerShape(12.dp)
        Box(Modifier.size(40.dp).clip(forma).background(Sup).border(1.dp, Traco, forma)
            .clickable(enabled = !modelo.ocupado.value) { modelo.sincronizar() }, contentAlignment = Alignment.Center) {
            Icone(Ic.att, if (modelo.ocupado.value) MuitoFraco else Medio)
        }
    }
}

@Composable
private fun Nav(aba: String, naoLidos: Int, ir: (String) -> Unit) {
    val itens = listOf(Triple("inicio", Ic.casa, "Início"), Triple("cal", Ic.cal, "Calendário"),
        Triple("prod", Ic.prod, "Produção"), Triple("vid", Ic.vid, "Vídeos"), Triple("com", Ic.com, "Comentários"))
    Column(Modifier.fillMaxWidth().background(Lado)) {
        Box(Modifier.fillMaxWidth().height(1.dp).background(Traco))
        Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(top = 7.dp, bottom = 9.dp)) {
            for ((id, ic, nome) in itens) {
                val on = aba == id || (id == "inicio" && aba == "analises")
                Column(Modifier.weight(1f).clickable(indication = null, interactionSource = remember { MutableInteractionSource() }) { ir(id) },
                    horizontalAlignment = Alignment.CenterHorizontally) {
                    Box {
                        Box(Modifier.width(56.dp).height(30.dp).clip(RoundedCornerShape(15.dp))
                            .background(if (on) Roxo.copy(alpha = 0.18f) else Color.Transparent), contentAlignment = Alignment.Center) {
                            Icone(ic, if (on) Roxo else Fraco)
                        }
                        if (id == "com" && naoLidos > 0)
                            T(if (naoLidos > 99) "99+" else "$naoLidos", Color.White, 10f, FontWeight.SemiBold,
                                Modifier.align(Alignment.TopEnd).offset(x = 4.dp, y = (-3).dp).clip(RoundedCornerShape(9.dp))
                                    .background(RoxoForte).padding(horizontal = 6.dp, vertical = 1.dp))
                    }
                    Spacer(Modifier.height(4.dp))
                    T(nome, if (on) Texto else Fraco, 11f, if (on) FontWeight.SemiBold else FontWeight.Normal, linhas = 1)
                }
            }
        }
    }
}

@Composable
private fun Titulo(t: String, sub: String = "") {
    T(t, Texto, 24f, FontWeight.SemiBold)
    if (sub.isNotEmpty()) T(sub, Fraco, 13f, modifier = Modifier.offset(y = (-4).dp))
}

@Composable
private fun Rolavel(conteudo: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp), content = conteudo)
}

// ---------------------------------------------------------------------------
// Início
// ---------------------------------------------------------------------------

@Composable
private fun PaginaInicio(modelo: Modelo, p: Pacote, ir: (String) -> Unit, abrir: (Video) -> Unit) {
    val c = p.canal; val n = p.numeros
    Rolavel {
        Titulo("Início", "Os últimos 28 dias do canal")
        Cartao {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Cap("Inscritos", Modifier.weight(1f))
                if (c.meta > c.inscritos) T("faltam ${mil(c.meta - c.inscritos)} pros ${mil(c.meta)}", Roxo, 12.5f, FontWeight.SemiBold)
            }
            T(mil(c.inscritos), Texto, 30f, FontWeight.SemiBold)
            Barra(c.inscritos.toFloat() / c.meta.coerceAtLeast(1))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Numero("Views", mil(n.views28), n.viewsVar)
            Numero("Horas", mil(n.horas28), n.horasVar)
            Numero("Novos", "+${mil(n.inscritos28)}", null, n.inscritosAntes?.let { "antes +${mil(it)}" } ?: "")
        }
        Cartao(onClick = { ir("analises") }) {
            Row(Modifier.fillMaxWidth()) { Cap("Views por dia", Modifier.weight(1f)); T("Análises ›", Roxo, 13f, FontWeight.SemiBold) }
            val dias = p.dias.takeLast(28)
            val maior = (dias.maxOfOrNull { it.views } ?: 1L).coerceAtLeast(1L)
            Canvas(Modifier.fillMaxWidth().height(80.dp)) {
                if (dias.isEmpty()) return@Canvas
                val passo = size.width / dias.size
                dias.forEachIndexed { i, d ->
                    val h = maxOf(3f, d.views.toFloat() / maior * (size.height - 4f))
                    drawRoundRect(if (i == dias.lastIndex) Roxo else RoxoEscuro, Offset(i * passo + passo * 0.15f, size.height - h),
                        Size(passo * 0.7f, h), CornerRadius(3f, 3f))
                }
            }
        }
        val agendados = p.videos.filter { it.agendado != null }.sortedBy { it.agendado }
        Cartao {
            Row(Modifier.fillMaxWidth()) { Cap("Próximos agendados", Modifier.weight(1f)); T("Calendário ›", Roxo, 13f, FontWeight.SemiBold, Modifier.clickable { ir("cal") }) }
            if (agendados.isEmpty()) T("Nenhum vídeo agendado.", Fraco, 13f)
            for (v in agendados.take(3)) LinhaVideo(modelo, v, 96.dp) { abrir(v) }
        }
        val novo = p.comentarios.firstOrNull { !it.lido && it.pergunta } ?: p.comentarios.firstOrNull { !it.lido }
        Cartao(onClick = { ir("com") }) {
            Row(Modifier.fillMaxWidth()) { Cap("Comentários novos", Modifier.weight(1f)); T("${p.naoLidos} ›", Roxo, 13f, FontWeight.SemiBold) }
            if (novo == null) T("Tudo lido.", Fraco, 13f)
            else {
                T("“${novo.texto}”", Medio, 14f, linhas = 3)
                T(novo.autor + if (novo.pergunta) " · pergunta" else "", Fraco, 12f)
            }
        }
    }
}

@Composable
private fun RowScope.Numero(cap: String, valor: String, variacao: Int?, rodape: String = "") {
    val forma = RoundedCornerShape(16.dp)
    Column(Modifier.weight(1f).clip(forma).background(Sup).border(1.dp, Traco, forma).padding(horizontal = 12.dp, vertical = 11.dp)) {
        Cap(cap)
        Spacer(Modifier.height(5.dp))
        T(valor, Texto, 19f, FontWeight.SemiBold, linhas = 1)
        when {
            variacao != null -> T(if (variacao >= 0) "▲ $variacao%" else "▼ ${-variacao}%", if (variacao >= 0) Verde else Vermelho, 11.5f)
            rodape.isNotEmpty() -> T(rodape, Fraco, 11.5f)
        }
    }
}

@Composable
private fun LinhaVideo(modelo: Modelo, v: Video, largura: Dp = 112.dp, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).clickable(onClick = onClick),
        verticalAlignment = Alignment.CenterVertically) {
        Thumb(modelo, v.thumb, largura, duracao = if (largura > 100.dp) v.duracao else 0)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            T(v.titulo, Texto, 14f, FontWeight.Medium, linhas = 2)
            Spacer(Modifier.height(3.dp))
            when {
                v.agendado != null -> T("Agendado · ${dh(v.agendado)}", Amarelo, 12f)
                else -> T("${mil(v.views)} views · ${ha(v.publicado)}" + if (v.visibilidade != "public") " · ${nomeVis(v.visibilidade).lowercase()}" else "", Fraco, 12f)
            }
            if (v.comparacao.isNotEmpty() && v.agendado == null)
                T(v.comparacao.substringBefore(" ("), if (v.comparacao.contains("acima")) Verde else Fraco, 12f)
        }
    }
}

private fun nomeVis(v: String) = when (v) { "public" -> "Público"; "unlisted" -> "Não listado"; else -> "Privado" }

// ---------------------------------------------------------------------------
// Calendário
// ---------------------------------------------------------------------------

@Composable
private fun PaginaCalendario(modelo: Modelo, p: Pacote, abrir: (Video) -> Unit, mudar: (Video) -> Unit, abrirCard: (Card) -> Unit) {
    val hoje = LocalDate.now()
    var mes by remember { mutableStateOf(YearMonth.now()) }
    var dia by remember { mutableStateOf(hoje) }
    val postados = p.videos.filter { it.agendado == null && it.publicado != null && it.visibilidade == "public" }
    val agendados = p.videos.filter { it.agendado != null }
    val planejados = p.cards.filter { it.data.isNotEmpty() && it.coluna != "postado" }
    fun doDia(d: LocalDate) = Triple(postados.filter { it.publicado!!.toLocalDate() == d },
        agendados.filter { it.agendado!!.toLocalDate() == d },
        planejados.filter { runCatching { LocalDate.parse(it.data) }.getOrNull() == d })
    val ultimo = postados.maxByOrNull { it.publicado!! }
    val semVideo = ultimo?.let { ChronoUnit.DAYS.between(it.publicado!!.toLocalDate(), hoje) }
    Rolavel {
        Titulo("Calendário", listOfNotNull(semVideo?.let { "Faz $it ${if (it == 1L) "dia" else "dias"} desde o último vídeo" },
            "${agendados.size} agendado${if (agendados.size == 1) "" else "s"}").joinToString(" · "))
        Row(verticalAlignment = Alignment.CenterVertically) {
            T("${MESES[mes.monthValue - 1]} ${mes.year}", Texto, 17f, FontWeight.SemiBold, Modifier.weight(1f))
            BotaoQuadrado(Ic.volta) { mes = mes.minusMonths(1) }
            Spacer(Modifier.width(8.dp))
            BotaoQuadrado(Ic.seta) { mes = mes.plusMonths(1) }
        }
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row { for (s in SEM) T(s.take(1).uppercase(), Fraco, 11f, modifier = Modifier.weight(1f), alinha = TextAlign.Center) }
            val primeiro = mes.atDay(1)
            val inicio = primeiro.minusDays((primeiro.dayOfWeek.value % 7).toLong())
            var d = inicio
            while (d <= mes.atEndOfMonth()) {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    repeat(7) {
                        val este = d
                        val (po, ag, pl) = doDia(este)
                        val ehHoje = este == hoje
                        val forma = RoundedCornerShape(10.dp)
                        Column(Modifier.weight(1f).height(46.dp).clip(forma)
                            .background(if (ehHoje) Roxo else Color.Transparent)
                            .let { if (este == dia && !ehHoje) it.border(1.5.dp, Roxo, forma) else it }
                            .clickable { dia = este; if (este.month != mes.month) mes = YearMonth.from(este) }
                            .padding(top = 6.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            T("${este.dayOfMonth}", when { ehHoje -> Escuro; este.month != mes.month -> MuitoFraco; else -> Medio },
                                13f, if (ehHoje) FontWeight.Bold else FontWeight.Normal)
                            Spacer(Modifier.height(4.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(3.dp)) {
                                val pontos = po.map { Roxo } + ag.map { Amarelo } + pl.map { Verde }
                                for (c in pontos.take(3)) Box(Modifier.size(5.dp).clip(CircleShape).background(if (ehHoje) Escuro else c))
                            }
                        }
                        d = d.plusDays(1)
                    }
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            for ((c, n) in listOf(Roxo to "Postado", Amarelo to "Agendado", Verde to "Planejado")) Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(7.dp).clip(CircleShape).background(c)); Spacer(Modifier.width(5.dp)); T(n, Fraco, 12f)
            }
        }
        val (po, ag, pl) = doDia(dia)
        Cartao {
            Cap(if (dia == hoje) "Hoje" else "Dia ${dia.dayOfMonth} · ${semana(dia.dayOfWeek)}")
            if (po.isEmpty() && ag.isEmpty() && pl.isEmpty()) T("Nada nesse dia.", Fraco, 13f)
            for (v in ag) {
                LinhaVideo(modelo, v, 96.dp) { abrir(v) }
                ConfirmarDuplo(modelo, v, mudar)
            }
            for (v in po) LinhaVideo(modelo, v, 96.dp) { abrir(v) }
            for (k in pl) Row(Modifier.fillMaxWidth().clickable { abrirCard(k) }, verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(8.dp).clip(CircleShape).background(Verde)); Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    T(k.titulo, Texto, 14f, FontWeight.Medium)
                    T("Planejado · ${COLUNAS.firstOrNull { it.first == k.coluna }?.second ?: k.coluna}", Fraco, 12f)
                }
            }
        }
    }
}

/** "Mudar dia ou hora" e "Desagendar" (toca duas vezes pra confirmar: nada de pop-up). */
@Composable
private fun ConfirmarDuplo(modelo: Modelo, v: Video, mudar: (Video) -> Unit) {
    var confirmando by remember(v.id) { mutableStateOf(false) }
    LaunchedEffect(confirmando) { if (confirmando) { delay(4000); confirmando = false } }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Botao("Mudar dia ou hora", Modifier.weight(1f)) { mudar(v) }
        Botao(if (confirmando) "Toca de novo" else "Desagendar", Modifier.weight(1f), cor = Color(0xFFFF9A9A)) {
            if (!confirmando) confirmando = true
            else { confirmando = false; modelo.acao(JSONObject().put("acao", "desagendar").put("video", v.id), youtube = true) }
        }
    }
}

@Composable
private fun BotaoQuadrado(i: ImageVector, onClick: () -> Unit) {
    val forma = RoundedCornerShape(10.dp)
    Box(Modifier.size(36.dp).clip(forma).background(Sup).border(1.dp, Traco, forma).clickable(onClick = onClick),
        contentAlignment = Alignment.Center) { Icone(i, Medio, 18.dp) }
}

/** Data e hora pra agendar (o mesmo "dd/mm/aaaa" e "hh:mm" da janela do PC). */
@Composable
private fun Agendar(modelo: Modelo, v: Video, fechar: () -> Unit) {
    val base = v.agendado ?: ZonedDateTime.now().plusDays(1).withHour(18).withMinute(0)
    var data by remember { mutableStateOf(base.format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))) }
    var hora by remember { mutableStateOf(base.format(DateTimeFormatter.ofPattern("HH:mm"))) }
    BackHandler(onBack = fechar)
    Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.5f))
        .clickable(indication = null, interactionSource = remember { MutableInteractionSource() }) { fechar() }
        .imePadding(), contentAlignment = Alignment.Center) {
        val forma = RoundedCornerShape(20.dp)
        Column(Modifier.padding(horizontal = 28.dp).fillMaxWidth().clip(forma).background(Sup2).border(1.dp, Traco, forma)
            .clickable(indication = null, interactionSource = remember { MutableInteractionSource() }) {}
            .padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            T(if (v.agendado != null) "Mudar dia ou hora" else "Agendar", Texto, 17f, FontWeight.SemiBold)
            T(v.titulo, Medio, 13.5f, linhas = 2)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Column(Modifier.weight(1.4f)) { Cap("Dia"); Spacer(Modifier.height(6.dp)); Campo(data, { data = it }, "dd/mm/aaaa", teclado = KeyboardType.Number) }
                Column(Modifier.weight(1f)) { Cap("Hora"); Spacer(Modifier.height(6.dp)); Campo(hora, { hora = it }, "hh:mm", teclado = KeyboardType.Number) }
            }
            T("O vídeo fica privado até a hora e sai sozinho.", Fraco, 12.5f)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Botao("Cancelar", Modifier.weight(1f)) { fechar() }
                Botao("Agendar", Modifier.weight(1f), forte = true, ativo = !modelo.ocupado.value) {
                    modelo.acao(JSONObject().put("acao", "agendar").put("video", v.id).put("data", data.trim()).put("hora", hora.trim()),
                        youtube = true) { ok -> if (ok) fechar() }
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Produção
// ---------------------------------------------------------------------------

@Composable
private fun PaginaProducao(modelo: Modelo, p: Pacote, abrir: (Card) -> Unit) {
    var coluna by remember { mutableStateOf("ideia") }
    val i = COLUNAS.indexOfFirst { it.first == coluna }
    val cards = p.cards.filter { it.coluna == coluna }
    var arrasto by remember { mutableStateOf(0f) }
    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().pointerInput(coluna) {
            detectHorizontalDragGestures(onDragEnd = {
                if (arrasto < -120 && i < COLUNAS.lastIndex) coluna = COLUNAS[i + 1].first
                if (arrasto > 120 && i > 0) coluna = COLUNAS[i - 1].first
                arrasto = 0f
            }) { _, dx -> arrasto += dx }
        }.padding(start = 16.dp, end = 16.dp, top = 4.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Titulo("Produção", "Da ideia até postado. Arrasta pro lado pra trocar de etapa.")
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for ((id, nome) in COLUNAS) Chip(nome, id == coluna, p.cards.count { it.coluna == id }) { coluna = id }
            }
            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp),
                contentPadding = PaddingValues(bottom = 90.dp)) {
                if (cards.isEmpty()) item { Vazio("Nada em ${COLUNAS[i].second.lowercase()}.") }
                items(cards, key = { it.id }) { c ->
                    Cartao(onClick = { abrir(c) }) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            T(c.titulo, Texto, 15f, FontWeight.Medium, Modifier.weight(1f))
                            if (c.jogo.isNotEmpty()) T(c.jogo, Medio, 11f, modifier = Modifier.clip(RoundedCornerShape(8.dp))
                                .background(Sup2).border(1.dp, Traco, RoundedCornerShape(8.dp)).padding(horizontal = 8.dp, vertical = 2.dp))
                        }
                        if (c.notas.isNotEmpty()) T(c.notas, Medio, 13f, linhas = 3)
                        if (c.data.isNotEmpty()) T("Planejado pra ${runCatching { LocalDate.parse(c.data).let { "${it.dayOfMonth}/${it.monthValue}" } }.getOrDefault(c.data)}", Verde, 12f)
                        for (a in c.arquivos) Row(verticalAlignment = Alignment.CenterVertically) {
                            Icone(Ic.clipe, Fraco, 15.dp); Spacer(Modifier.width(6.dp)); T(a.substringAfterLast('/'), Fraco, 12.5f, linhas = 1)
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (i > 0) Botao("‹ ${COLUNAS[i - 1].second}", Modifier.weight(1f)) {
                                modelo.acao(JSONObject().put("acao", "mover_card").put("card", c.id).put("coluna", COLUNAS[i - 1].first))
                            }
                            if (i < COLUNAS.lastIndex) Botao("${COLUNAS[i + 1].second} ›", Modifier.weight(1.4f), forte = true) {
                                modelo.acao(JSONObject().put("acao", "mover_card").put("card", c.id).put("coluna", COLUNAS[i + 1].first))
                            }
                        }
                    }
                }
            }
        }
        Row(Modifier.align(Alignment.BottomEnd).padding(18.dp).clip(RoundedCornerShape(18.dp)).background(Roxo)
            .clickable { abrir(Card(0, "", "", coluna, "", "", emptyList(), "")) }
            .padding(horizontal = 18.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
            Icone(Ic.mais, Escuro, 18.dp); Spacer(Modifier.width(8.dp))
            T(if (coluna == "ideia") "Nova ideia" else "Novo card", Escuro, 14f, FontWeight.SemiBold)
        }
    }
}

@Composable
private fun EditorCard(modelo: Modelo, c: Card, fechar: () -> Unit) {
    var titulo by remember { mutableStateOf(c.titulo) }
    var jogo by remember { mutableStateOf(c.jogo) }
    var notas by remember { mutableStateOf(c.notas) }
    var coluna by remember { mutableStateOf(c.coluna) }
    var data by remember { mutableStateOf(runCatching { LocalDate.parse(c.data).format(DateTimeFormatter.ofPattern("dd/MM/yyyy")) }.getOrDefault("")) }
    var confirmando by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).imePadding().padding(horizontal = 18.dp)
        .padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        T(if (c.id == 0) "Card novo" else "Card", Texto, 20f, FontWeight.SemiBold)
        Cap("Título"); Campo(titulo, { titulo = it }, "Ex.: Doors Hotel+ com o Lucas")
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) { Cap("Jogo"); Campo(jogo, { jogo = it }, "Doors") }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) { Cap("Data planejada"); Campo(data, { data = it }, "dd/mm/aaaa", teclado = KeyboardType.Number) }
        }
        Cap("Etapa")
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for ((id, nome) in COLUNAS) Chip(nome, id == coluna) { coluna = id }
        }
        Cap("Notas"); Campo(notas, { notas = it }, "O que falta, ideia de thumb…", linhas = 3)
        if (c.arquivos.isNotEmpty()) {
            Cap("Arquivos (no PC)")
            for (a in c.arquivos) Row(verticalAlignment = Alignment.CenterVertically) {
                Icone(Ic.clipe, Fraco, 15.dp); Spacer(Modifier.width(6.dp)); T(a.substringAfterLast('/'), Medio, 13f, linhas = 1)
            }
        }
        Spacer(Modifier.height(4.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            if (c.id != 0) Botao(if (confirmando) "Toca de novo" else "Apagar", Modifier.weight(1f), cor = Color(0xFFFF9A9A)) {
                if (!confirmando) confirmando = true
                else modelo.acao(JSONObject().put("acao", "apagar_card").put("card", c.id)) { ok -> if (ok) fechar() }
            }
            Botao("Salvar", Modifier.weight(1f), forte = true, ativo = titulo.isNotBlank()) {
                val iso = data.trim().takeIf { it.isNotEmpty() }?.let {
                    runCatching { LocalDate.parse(it, DateTimeFormatter.ofPattern("dd/MM/yyyy")).toString() }.getOrNull()
                }
                if (data.isNotBlank() && iso == null) { modelo.avisar("A data é dd/mm/aaaa (ex.: 20/11/2026).", false); return@Botao }
                val campos = JSONObject().put("titulo", titulo).put("jogo", jogo).put("notas", notas).put("coluna", coluna).put("data", iso ?: "")
                val pedido = if (c.id == 0) JSONObject().put("acao", "criar_card").put("campos", campos)
                             else JSONObject().put("acao", "salvar_card").put("card", c.id).put("campos", campos)
                modelo.acao(pedido) { ok -> if (ok) fechar() }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Vídeos e a ficha
// ---------------------------------------------------------------------------

@Composable
private fun PaginaVideos(modelo: Modelo, p: Pacote, abrir: (Video) -> Unit) {
    var busca by remember { mutableStateOf("") }
    var filtro by remember { mutableStateOf("todos") }
    val agendados = p.videos.filter { it.agendado != null }.sortedBy { it.agendado }
    val outros = p.videos.filter { it.agendado == null }
    val lista = (agendados + outros).filter {
        (filtro == "todos" || (filtro == "agendados" && it.agendado != null) || (filtro == "publicos" && it.agendado == null && it.visibilidade == "public")) &&
            (busca.isBlank() || it.titulo.contains(busca.trim(), ignoreCase = true))
    }
    Column(Modifier.fillMaxSize().padding(start = 16.dp, end = 16.dp, top = 4.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Titulo("Vídeos")
        Box {
            Campo(busca, { busca = it }, "      Procurar vídeo")
            Box(Modifier.padding(start = 13.dp, top = 12.dp)) { if (busca.isEmpty()) Icone(Ic.busca, Fraco, 18.dp) }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Chip("Todos", filtro == "todos", p.videos.size) { filtro = "todos" }
            Chip("Agendados", filtro == "agendados", agendados.size) { filtro = "agendados" }
            Chip("Públicos", filtro == "publicos", outros.count { it.visibilidade == "public" }) { filtro = "publicos" }
        }
        LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(14.dp), contentPadding = PaddingValues(bottom = 24.dp)) {
            if (lista.isEmpty()) item { Vazio(if (p.videos.isEmpty()) "O canal ainda não tem vídeos." else "Nenhum vídeo com isso.") }
            items(lista, key = { it.id }) { v -> LinhaVideo(modelo, v) { abrir(v) } }
        }
    }
}

@Composable
private fun Ficha(modelo: Modelo, v: Video, agendar: (Video) -> Unit, fechar: () -> Unit) {
    val contexto = LocalContext.current
    var titulo by remember(v.id) { mutableStateOf(v.titulo) }
    var descricao by remember(v.id) { mutableStateOf(v.descricao) }
    var tags by remember(v.id) { mutableStateOf(v.tags.joinToString(", ")) }
    var vis by remember(v.id) { mutableStateOf(v.visibilidade) }
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).imePadding().padding(horizontal = 18.dp)
        .padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(Modifier.fillMaxWidth()) { Thumb(modelo, v.thumb, 2000.dp, Modifier.fillMaxWidth(), v.duracao) }
        if (v.agendado == null) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Numero("Views", mil(v.views), null); Numero("Likes", mil(v.likes), null); Numero("Coment.", mil(v.comentarios), null)
        }
        if (v.comparacao.isNotEmpty()) T(v.comparacao, if (v.comparacao.contains("acima")) Verde else Fraco, 12.5f)
        if (v.agendado != null) {
            T("Agendado pra ${dh(v.agendado)}", Amarelo, 14f, FontWeight.Medium)
            ConfirmarDuplo(modelo, v, agendar)
        }
        Cap("Título"); Campo(titulo, { titulo = it })
        T("${titulo.length}/100", if (titulo.length > 100) Vermelho else Fraco, 11.5f, modifier = Modifier.align(Alignment.End).offset(y = (-6).dp))
        Cap("Descrição"); Campo(descricao, { descricao = it }, linhas = 4, tam = 13.5f)
        Cap("Tags (separadas por vírgula)"); Campo(tags, { tags = it }, tam = 13.5f)
        Cap("Visibilidade")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for (k in listOf("public", "unlisted", "private")) Chip(nomeVis(k), vis == k) { vis = k }
        }
        if (v.agendado != null && vis != "private") T("Mudando pra ${nomeVis(vis)}, ele sai AGORA e deixa de estar agendado.", Amarelo, 12.5f)
        if (v.agendado == null && v.visibilidade == "private") Botao("Agendar", Modifier.fillMaxWidth()) { agendar(v) }
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Botao("Abrir no YouTube", Modifier.weight(1f)) {
                try { contexto.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://youtu.be/${v.id}"))) } catch (e: Exception) { }
            }
            Botao(if (modelo.ocupado.value) "Salvando…" else "Salvar", Modifier.weight(1f), forte = true,
                ativo = !modelo.ocupado.value && titulo.isNotBlank() && titulo.length <= 100) {
                modelo.acao(JSONObject().put("acao", "salvar").put("video", v.id).put("titulo", titulo)
                    .put("descricao", descricao).put("tags", tags).put("visibilidade", vis), youtube = true) { ok -> if (ok) fechar() }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Comentários
// ---------------------------------------------------------------------------

private val CORES_AVATAR = listOf(Color(0xFF3B2F63), Color(0xFF2F4A63), Color(0xFF63304A), Color(0xFF2F6352), Color(0xFF63502F))

@Composable
private fun PaginaComentarios(modelo: Modelo, p: Pacote) {
    var filtro by remember { mutableStateOf(if (p.naoLidos > 0) "naolidos" else "todos") }
    var respondendo by remember { mutableStateOf<String?>(null) }
    var resposta by remember { mutableStateOf("") }
    val lista = p.comentarios.filter {
        when (filtro) { "naolidos" -> !it.lido; "perguntas" -> it.pergunta && !it.respondido; else -> true }
    }
    Column(Modifier.fillMaxSize().padding(start = 16.dp, end = 16.dp, top = 4.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) { Titulo("Comentários") }
            if (p.naoLidos > 0) T("Marcar todos lidos", Roxo, 13f, FontWeight.SemiBold,
                Modifier.clickable { modelo.acao(JSONObject().put("acao", "todos_lidos")) })
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Chip("Não lidos", filtro == "naolidos", p.naoLidos) { filtro = "naolidos" }
            Chip("Perguntas", filtro == "perguntas", p.comentarios.count { it.pergunta && !it.respondido }) { filtro = "perguntas" }
            Chip("Todos", filtro == "todos") { filtro = "todos" }
        }
        LazyColumn(Modifier.weight(1f).imePadding(), verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(bottom = 24.dp)) {
            if (lista.isEmpty()) item { Vazio("Nada por aqui.") }
            items(lista, key = { it.id }) { c ->
                val aberto = respondendo == c.id
                Cartao(borda = if (aberto) Color(0xFF4B3D7A) else Traco) {
                    Row(verticalAlignment = Alignment.Top) {
                        val letra = c.autor.trimStart('@').take(1).uppercase().ifEmpty { "?" }
                        Box(Modifier.size(34.dp).clip(CircleShape).background(CORES_AVATAR[(c.autor.hashCode() and 0xffff) % CORES_AVATAR.size]),
                            contentAlignment = Alignment.Center) { T(letra, Texto, 14f, FontWeight.SemiBold) }
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                T(c.autor, Medio, 12.5f, FontWeight.SemiBold, linhas = 1, modifier = Modifier.weight(1f, fill = false))
                                T(" · ${ha(c.quando)}", Fraco, 12.5f)
                                if (c.pergunta) T(" · pergunta", Amarelo, 12.5f)
                                if (!c.lido) { Spacer(Modifier.width(6.dp)); Box(Modifier.size(6.dp).clip(CircleShape).background(Roxo)) }
                            }
                            Spacer(Modifier.height(3.dp))
                            T(c.texto, Texto, 14f)
                            Spacer(Modifier.height(3.dp))
                            T("em ${c.videoTitulo}", Fraco, 12f, linhas = 1)
                        }
                    }
                    if (aberto) {
                        Campo(resposta, { resposta = it }, "Escreve a resposta…", linhas = 2)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Botao("Cancelar", Modifier.weight(1f)) { respondendo = null; resposta = "" }
                            Botao(if (modelo.ocupado.value) "Publicando…" else "Responder", Modifier.weight(1f), forte = true,
                                ativo = resposta.isNotBlank() && !modelo.ocupado.value) {
                                modelo.acao(JSONObject().put("acao", "responder").put("comentario", c.id).put("texto", resposta.trim()),
                                    youtube = true) { ok -> if (ok) { respondendo = null; resposta = "" } }
                            }
                        }
                    } else Row(Modifier.padding(start = 46.dp), horizontalArrangement = Arrangement.spacedBy(18.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        T(if (c.respondido) "Respondido" else "Responder", if (c.respondido) Verde else Roxo, 12.5f, FontWeight.SemiBold,
                            Modifier.clickable { respondendo = c.id; resposta = "" })
                        if (!c.lido) T("Lido", Medio, 12.5f, modifier = Modifier.clickable {
                            modelo.acao(JSONObject().put("acao", "lido").put("comentario", c.id))
                        })
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icone(Ic.coracao, Fraco, 14.dp); Spacer(Modifier.width(4.dp)); T("${c.likes}", Fraco, 12.5f)
                        }
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Análises
// ---------------------------------------------------------------------------

@Composable
private fun PaginaAnalises(modelo: Modelo, p: Pacote, voltar: () -> Unit) {
    val a = p.analises
    Rolavel {
        Row(Modifier.clickable(onClick = voltar), verticalAlignment = Alignment.CenterVertically) {
            Icone(Ic.volta, Roxo, 18.dp); T("Início", Roxo, 13.5f, FontWeight.SemiBold)
        }
        Titulo("Análises", "Últimos 28 dias · o YouTube entrega com ~2 dias de atraso")
        Cartao {
            Cap("Os que mais deram views")
            if (a.top.isEmpty()) T("Sem dados ainda.", Fraco, 13f)
            a.top.take(5).forEachIndexed { i, t ->
                val v = p.videos.firstOrNull { it.id == t.video }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    T("${i + 1}", Fraco, 14f, FontWeight.SemiBold, Modifier.width(18.dp))
                    Thumb(modelo, v?.thumb ?: "", 76.dp)
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        T(v?.titulo ?: t.video, Texto, 13f, FontWeight.Medium, linhas = 1)
                        Row { T("${mil(t.views)} views · ", Fraco, 12f); T("+${mil(t.inscritos)} inscritos", Verde, 12f) }
                    }
                }
            }
        }
        Barras("De onde vêm as views", a.origens, porcento = true)
        Barras("Quem assiste · idade", a.idades, jaPorcento = true)
        Barras("De onde são", a.paises, porcento = true)
        Barras("Onde assistem", a.aparelhos, porcento = true)
    }
}

@Composable
private fun Barras(titulo: String, lista: List<Fatia>, porcento: Boolean = false, jaPorcento: Boolean = false) {
    if (lista.isEmpty()) return
    val maior = lista.maxOf { it.valor }.coerceAtLeast(0.0001)
    val soma = lista.sumOf { it.valor }.coerceAtLeast(0.0001)
    Cartao {
        Cap(titulo)
        for (f in lista.take(5)) Row(verticalAlignment = Alignment.CenterVertically) {
            T(f.nome, Medio, 13f, linhas = 1, modifier = Modifier.width(120.dp))
            Barra((f.valor / maior).toFloat(), Modifier.weight(1f), 10.dp)
            T(when { jaPorcento -> "${f.valor.toInt()}%"; porcento -> "${(f.valor / soma * 100).toInt()}%"; else -> mil(f.valor.toLong()) },
                Fraco, 12f, modifier = Modifier.width(48.dp), alinha = TextAlign.End)
        }
    }
}
