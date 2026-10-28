package com.lelokz.jarvis

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.net.Uri
import android.content.Intent
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.ui.graphics.vector.ImageVector
import kotlin.math.roundToInt
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.material3.Switch
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.rememberDrawerState
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.Calendar

// As cores da janela do PC (jarvis/interface/qml/Tema.qml), as mesmas.
private val Fundo = Color(0xFF0A0C10)
private val Lateral = Color(0xFF0D1016)
private val Superficie = Color(0xFF131821)
private val Superficie2 = Color(0xFF181E29)
private val Realce = Color(0xFF1F2738)
private val Traco = Color(0xFF1F2734)
private val TracoForte = Color(0xFF2A3446)
private val Texto = Color(0xFFE6EBF2)
private val TextoMedio = Color(0xFFB9C1CF)
private val Fraco = Color(0xFF7E879B)
private val MuitoFraco = Color(0xFF4D5568)
private val Perigo = Color(0xFFFF6B6B)
private val Pergunta = Color(0xFFFFB454)
// A persona ativa (beta 0.14.5): cada uma tem a sua cor, a Friday a dela
// (rosa, do config do PC) e o Jarvis o azul. (A "Cor de destaque" dos
// Ajustes saiu na beta 0.15.5.)
val personaAtiva = mutableStateOf("jarvis")
val corDaFriday = mutableStateOf(Color(0xFFFF6FB5))
private val CorDoJarvis = Color(0xFF4DA3FF)
private val Azul: Color get() = if (personaAtiva.value == "friday") corDaFriday.value else CorDoJarvis
private val Roxo = Color(0xFF9B7BFF)

// A Inter, a fonte da janela do PC (licença OFL). Variável: o peso funciona.
@OptIn(ExperimentalTextApi::class)
private val Inter = FontFamily(
    listOf(400, 500, 600, 700).map { p ->
        Font(R.font.inter, FontWeight(p), variationSettings = FontVariation.Settings(FontVariation.weight(p)))
    }
)

/** Uma cor por estado, as mesmas do PC: dá para saber o que ele faz sem ler. */
private fun corDoEstado(e: String) = when (e) {
    "pronto" -> Azul
    "escutando" -> Color(0xFF38D39F)
    "pensando" -> Roxo
    "falando" -> Pergunta
    else -> Color(0xFF39435A)
}

private fun rotuloDoEstado(e: String) = when (e) {
    "pronto" -> "SEGURA PRA FALAR"
    "escutando" -> "ESCUTANDO VOCÊ"
    "pensando" -> "PENSANDO"
    "falando" -> "FALANDO"
    else -> "SEM CONEXÃO"
}

private val nomesModelo = mapOf("auto" to "Automático", "haiku" to "Haiku", "sonnet" to "Sonnet", "opus" to "Opus")
private val nomesEsforco = mapOf("low" to "Baixo", "medium" to "Médio", "high" to "Alto",
    "xhigh" to "Muito alto", "max" to "Máximo")

private fun hora(seg: Double): String {
    if (seg <= 0) return ""
    val c = Calendar.getInstance().apply { timeInMillis = (seg * 1000).toLong() }
    return "%02d:%02d".format(c.get(Calendar.HOUR_OF_DAY), c.get(Calendar.MINUTE))
}

private fun grupoDe(quando: Double): String {
    val hoje = Calendar.getInstance().apply {
        set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0); set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
    }.timeInMillis / 1000.0
    val dia = 86400.0
    return when {
        quando >= hoje -> "Hoje"
        quando >= hoje - dia -> "Ontem"
        quando >= hoje - 6 * dia -> "Esta semana"
        quando >= hoje - 30 * dia -> "Este mês"
        else -> "Mais antigas"
    }
}

class MainActivity : ComponentActivity() {
    private fun temMicrofone() = ContextCompat.checkSelfPermission(
        this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        if (intent.getBooleanExtra("desbloqueio", false)) (application as App).jarvis.conferirDesbloqueio()
        if (intent.getBooleanExtra("aprovacao", false)) (application as App).jarvis.conferirPedidos()
        (application as App).jarvis.receberCompartilhado(intent)
        (application as App).jarvis.ligarPorLink(intent)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (intent?.getBooleanExtra("desbloqueio", false) == true) (application as App).jarvis.conferirDesbloqueio()
        if (intent?.getBooleanExtra("aprovacao", false) == true) (application as App).jarvis.conferirPedidos()
        if (savedInstanceState == null) intent?.let {
            (application as App).jarvis.receberCompartilhado(it)
            (application as App).jarvis.ligarPorLink(it)
        }
        enableEdgeToEdge()
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(background = Fundo, surface = Fundo)) {
                CompositionLocalProvider(LocalTextStyle provides TextStyle(fontFamily = Inter)) {
                    val modelo = (application as App).jarvis
                    // Estava "sempre ouvindo" quando fechou: garante o serviço de pé.
                    LaunchedEffect(Unit) {
                        if (modelo.sempreOuvindo.value && temMicrofone()) modelo.alternarSempreOuvindo(true)
                    }
                    Box(Modifier.fillMaxSize().background(Fundo)) {
                        if (modelo.configurado.value) Tela(modelo)
                        else Box(Modifier.safeDrawingPadding()) { Entrada(modelo) }
                    }
                }
            }
        }
    }
}

/** A primeira vez: colar o link da página, que já traz a chave. */
@Composable
fun Entrada(modelo: Jarvis) {
    var link by remember { mutableStateOf("") }
    var erro by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            AtomoFixo(Azul, 28.dp)
            Spacer(Modifier.width(10.dp))
            Text("NOVA", color = Texto, fontSize = 22.sp, fontWeight = FontWeight.Bold, letterSpacing = 4.sp)
        }
        Spacer(Modifier.height(8.dp))
        Text("Escaneia o QR da janela do PC (Ajustes → Conexões → Celular) com a câmera, ou cola o link da NOVA aqui.",
            color = Fraco, fontSize = 14.sp)
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(
            value = link, onValueChange = { link = it; erro = false },
            modifier = Modifier.fillMaxWidth(), singleLine = true,
            placeholder = { Text("https://jarvis…ts.net/#chave=…") }, isError = erro,
            colors = OutlinedTextFieldDefaults.colors(
                focusedTextColor = Texto, unfocusedTextColor = Texto,
                focusedBorderColor = Azul, unfocusedBorderColor = Traco, cursorColor = Azul),
        )
        if (erro) Text("Esse link não tem a chave.", color = Perigo, fontSize = 13.sp)
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = { erro = !modelo.configurar(link) },
            colors = ButtonDefaults.buttonColors(containerColor = Azul, contentColor = Fundo),
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Entrar") }
    }
}

// -- a tela: gaveta, topo e a página ---------------------------------------------

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun Tela(modelo: Jarvis) {
    val gaveta = rememberDrawerState(DrawerValue.Closed)
    val escopo = rememberCoroutineScope()
    var seletores by remember { mutableStateOf(false) }
    val contexto = LocalContext.current

    // As notificações (avisos do PC, pedidos do grupo) precisam da permissão (Android 13+): pede uma
    // vez só, na primeira abertura desta versão.
    val pedirNotificacao = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
    LaunchedEffect(Unit) {
        val prefs = contexto.getSharedPreferences("jarvis", android.content.Context.MODE_PRIVATE)
        if (android.os.Build.VERSION.SDK_INT >= 33 && !prefs.getBoolean("pediu_notificacao", false) &&
            ContextCompat.checkSelfPermission(contexto, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED) {
            prefs.edit().putBoolean("pediu_notificacao", true).apply()
            pedirNotificacao.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    // Voltar: fecha a gaveta, sai da conversa antiga ou da página.
    BackHandler(enabled = gaveta.isOpen || modelo.vendo.value.isNotEmpty() || modelo.pagina.value != "chat") {
        when {
            gaveta.isOpen -> escopo.launch { gaveta.close() }
            // Uma memória aberta: o voltar volta para a lista das Memórias.
            modelo.pagina.value == "memoria" && modelo.memoriaAberta.value != null -> modelo.pedirMemorias()
            // Num passo a passo das Conexões: o voltar volta para os cartões.
            modelo.pagina.value == "ajustes" && modelo.passoConexao.value.isNotEmpty() -> modelo.fecharPasso()
            // Dentro de uma categoria dos Ajustes: o voltar volta para a lista delas.
            modelo.pagina.value == "ajustes" && modelo.abaAjustes.value.isNotEmpty() -> modelo.abaAjustes.value = ""
            modelo.pagina.value != "chat" -> modelo.pagina.value = "chat"
            else -> modelo.abrir("")
        }
    }

    ModalNavigationDrawer(
        drawerState = gaveta,
        // Gravando, o arrastar não abre a gaveta (o dedo é do átomo).
        gesturesEnabled = gaveta.isOpen || !modelo.gravando.value,
        drawerContent = {
            ModalDrawerSheet(drawerContainerColor = Lateral, drawerShape = RoundedCornerShape(0.dp),
                modifier = Modifier.width(310.dp)) {
                Gaveta(modelo) { escopo.launch { gaveta.close() } }
            }
        },
    ) {
        Box(Modifier.fillMaxSize().background(Fundo).safeDrawingPadding()) {
            Column(Modifier.fillMaxSize().imePadding()) {
                Topo(modelo, abrirGaveta = { escopo.launch { gaveta.open() } }, abrirSeletores = { seletores = true })
                when (modelo.pagina.value) {
                    "memoria" -> PaginaMemoria(modelo)
                    "ajustes" -> PaginaAjustes(modelo)
                    else -> Chat(modelo) { seletores = true }
                }
            }
            val temAtualizacao = modelo.atualizacao.value != 0
            if (temAtualizacao || modelo.atualizando.value >= 0f) RetanguloAtualizacao(modelo, Modifier.align(Alignment.TopCenter).padding(top = 58.dp))
            Aviso(modelo, Modifier.align(Alignment.TopCenter).padding(top = if (temAtualizacao) 100.dp else 64.dp))
        }
    }

    if (modelo.avisoAtualizacao.value) AvisoAtualizacao(modelo)
    if (modelo.desbloqueio.value.isNotEmpty()) AvisoDesbloqueio(modelo)
    modelo.pedidoGrupo.value?.let { AvisoPedido(modelo, it.second, it.third) }

    if (seletores) {
        ModalBottomSheet(
            onDismissRequest = { seletores = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = Superficie2,
        ) { Seletores(modelo) }
    }
}

/** O retângulo pequeno no topo: tem versão nova e o aviso grande já foi
 *  fechado. Baixando, vira a barrinha do download (e não abre o aviso de novo). */
@Composable
private fun RetanguloAtualizacao(modelo: Jarvis, modifier: Modifier) {
    val forma = RoundedCornerShape(10.dp)
    val p = modelo.atualizando.value
    Row(modifier.clip(forma).background(Superficie2).border(1.dp, TracoForte, forma)
        .clickable(enabled = p < 0f) { modelo.avisoAtualizacao.value = true }
        .padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        when {
            p < 0f -> {
                Box(Modifier.size(7.dp).clip(CircleShape).background(Azul))
                Spacer(Modifier.width(8.dp))
                Text("Atualização disponível", color = TextoMedio, fontSize = 12.sp)
            }
            p > 1f -> Text("Instalando…", color = TextoMedio, fontSize = 12.sp)
            else -> {
                Text("Baixando atualização", color = TextoMedio, fontSize = 12.sp)
                Spacer(Modifier.width(10.dp))
                Box(Modifier.width(90.dp).height(5.dp).clip(RoundedCornerShape(3.dp)).background(Lateral)) {
                    Box(Modifier.fillMaxWidth(p.coerceIn(0.02f, 1f)).height(5.dp).clip(RoundedCornerShape(3.dp))
                        .background(Azul))
                }
                Spacer(Modifier.width(8.dp))
                Text("${(p * 100).toInt()}%", color = Texto, fontSize = 12.sp)
            }
        }
    }
}

/** O pedido de alguém do grupo da família que precisa do Sim (beta 0.13.0). */
@Composable
private fun AvisoPedido(modelo: Jarvis, quem: String, pedido: String) {
    BackHandler { modelo.responderPedido(false) }
    Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.45f))
        .clickable(indication = null, interactionSource = remember { MutableInteractionSource() }) {},
        contentAlignment = Alignment.Center) {
        val forma = RoundedCornerShape(20.dp)
        Column(Modifier.padding(horizontal = 32.dp).fillMaxWidth().clip(forma).background(Superficie2)
            .border(1.dp, TracoForte, forma).padding(22.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                AtomoFixo(Azul, 26.dp)
                Spacer(Modifier.width(10.dp))
                Text("Pedido de $quem pro Jarvis", color = Texto, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
            }
            Spacer(Modifier.height(10.dp))
            Text("\"$pedido\"", color = Texto, fontSize = 15.sp, lineHeight = 21.sp)
            Spacer(Modifier.height(6.dp))
            Text("Veio do grupo da família. Se você liberar, o Jarvis do PC faz.",
                color = TextoMedio, fontSize = 13.sp, lineHeight = 19.sp)
            Spacer(Modifier.height(20.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = { modelo.responderPedido(false) }, modifier = Modifier.weight(1f),
                    border = BorderStroke(1.dp, TracoForte)) { Text("Não", color = TextoMedio) }
                Button(onClick = { modelo.responderPedido(true) }, modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Azul, contentColor = Fundo)) { Text("Sim") }
            }
        }
    }
}

/** "Desbloquear o PC?": a segunda trava do desbloqueio (a primeira é a voz do Léo). */
@Composable
private fun AvisoDesbloqueio(modelo: Jarvis) {
    BackHandler { modelo.responderDesbloqueio(false) }
    Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.45f))
        .clickable(indication = null, interactionSource = remember { MutableInteractionSource() }) {},
        contentAlignment = Alignment.Center) {
        val forma = RoundedCornerShape(20.dp)
        Column(Modifier.padding(horizontal = 32.dp).fillMaxWidth().clip(forma).background(Superficie2)
            .border(1.dp, TracoForte, forma).padding(22.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                AtomoFixo(Azul, 26.dp)
                Spacer(Modifier.width(10.dp))
                Text("Desbloquear o PC?", color = Texto, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
            }
            Spacer(Modifier.height(10.dp))
            Text("Pediram pro Jarvis desbloquear o seu PC. Se não foi você, toque em Não.",
                color = TextoMedio, fontSize = 14.sp, lineHeight = 20.sp)
            Spacer(Modifier.height(20.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = { modelo.responderDesbloqueio(false) }, modifier = Modifier.weight(1f),
                    border = BorderStroke(1.dp, TracoForte)) { Text("Não", color = TextoMedio) }
                Button(onClick = { modelo.responderDesbloqueio(true) }, modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Azul, contentColor = Fundo)) { Text("Sim") }
            }
        }
    }
}

/** O aviso grande: o fundo escurece um pouco (o app continua visível atrás). */
@Composable
private fun AvisoAtualizacao(modelo: Jarvis) {
    BackHandler { modelo.fecharAvisoAtualizacao(false) }
    Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.45f))
        .clickable(indication = null, interactionSource = remember { MutableInteractionSource() }) {},
        contentAlignment = Alignment.Center) {
        val forma = RoundedCornerShape(20.dp)
        Column(Modifier.padding(horizontal = 32.dp).fillMaxWidth().clip(forma).background(Superficie2)
            .border(1.dp, TracoForte, forma).padding(22.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                AtomoFixo(Azul, 26.dp)
                Spacer(Modifier.width(10.dp))
                Text("Atualização pendente", color = Texto, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
            }
            Spacer(Modifier.height(10.dp))
            Text("Tem uma versão nova do app. Deseja atualizar agora?", color = TextoMedio,
                fontSize = 14.sp, lineHeight = 20.sp)
            Spacer(Modifier.height(20.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = { modelo.fecharAvisoAtualizacao(false) }, modifier = Modifier.weight(1f),
                    border = BorderStroke(1.dp, TracoForte)) { Text("Não", color = TextoMedio) }
                Button(onClick = { modelo.fecharAvisoAtualizacao(true) }, modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = Azul, contentColor = Fundo)) { Text("Sim") }
            }
        }
    }
}

@Composable
private fun Aviso(modelo: Jarvis, modifier: Modifier) {
    val texto = modelo.aviso.value
    LaunchedEffect(texto) {
        if (texto.isNotEmpty()) { delay(3200); modelo.aviso.value = "" }
    }
    AnimatedVisibility(texto.isNotEmpty(), modifier, enter = fadeIn(), exit = fadeOut()) {
        Text(texto, color = TextoMedio, fontSize = 13.sp, textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = 24.dp).clip(RoundedCornerShape(18.dp))
                .background(Superficie2).border(1.dp, TracoForte, RoundedCornerShape(18.dp))
                .padding(horizontal = 16.dp, vertical = 9.dp))
    }
}

/** Liga e desliga o "sempre ouvindo" (o topo e os Ajustes): ligar pede o microfone e (Android 13+) a notificação. */
@Composable
private fun lembrarAlternarOuvido(modelo: Jarvis): () -> Unit {
    val contexto = LocalContext.current
    val pedirParaOuvir = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()) { r ->
        if (r[Manifest.permission.RECORD_AUDIO] == true) modelo.alternarSempreOuvindo(true)
    }
    return {
        if (modelo.sempreOuvindo.value) modelo.alternarSempreOuvindo(false)
        else {
            val faltam = buildList {
                add(Manifest.permission.RECORD_AUDIO)
                if (android.os.Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
            }.filter { ContextCompat.checkSelfPermission(contexto, it) != PackageManager.PERMISSION_GRANTED }
            if (faltam.isEmpty()) modelo.alternarSempreOuvindo(true) else pedirParaOuvir.launch(faltam.toTypedArray())
        }
    }
}

@Composable
private fun Topo(modelo: Jarvis, abrirGaveta: () -> Unit, abrirSeletores: () -> Unit) {
    val alternarOuvido = lembrarAlternarOuvido(modelo)
    val pagina = modelo.pagina.value
    val antiga = modelo.vendo.value.isNotEmpty()
    val vazio = !antiga && modelo.mensagens.isEmpty()
    val titulo = when {
        pagina == "memoria" -> "Memórias"
        pagina == "ajustes" -> categoriasDosAjustes.flatMap { it.second }.firstOrNull { it.id == modelo.abaAjustes.value }?.nome ?: "Ajustes"
        else -> modelo.conversas.firstOrNull { it.id == (modelo.vendo.value.ifEmpty { modelo.conversaAtual.value }) }
            ?.titulo ?: "Chat novo"
    }
    Row(Modifier.fillMaxWidth().height(56.dp).padding(start = 4.dp, end = 4.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(44.dp).clip(CircleShape).clickable { abrirGaveta() }, contentAlignment = Alignment.Center) {
            Ic(Icones.menu, TextoMedio, 22.dp)
        }
        Column(
            Modifier.weight(1f).clip(RoundedCornerShape(10.dp))
                .clickable(enabled = pagina == "chat") { abrirSeletores() }
                .padding(horizontal = 6.dp, vertical = 4.dp),
        ) {
            Text(titulo, color = if (vazio && pagina == "chat") Fraco else Texto, fontSize = 15.sp,
                fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (pagina == "chat") {
                when {
                    !modelo.conectado.value -> Text(modelo.motivo.value, color = Fraco, fontSize = 11.sp, maxLines = 1)
                    antiga -> Text("Conversa antiga", color = Pergunta, fontSize = 11.sp)
                    else -> Text("${nomesModelo[modelo.modelo.value] ?: modelo.modelo.value} · esforço " +
                        (nomesEsforco[modelo.esforco.value] ?: modelo.esforco.value).lowercase(),
                        color = Fraco, fontSize = 11.sp, maxLines = 1)
                }
            }
        }
        // "Sempre ouvindo": aceso = o "hey Jarvis" funciona com a tela desligada.
        Box(Modifier.size(42.dp).clip(CircleShape).clickable { alternarOuvido() }, contentAlignment = Alignment.Center) {
            Ic(Icones.voz, if (modelo.sempreOuvindo.value) Azul else Fraco, 21.dp)
        }
        // O mudo: resposta só em texto.
        Box(Modifier.size(42.dp).clip(CircleShape).clickable { modelo.alternarMudo() }, contentAlignment = Alignment.Center) {
            Ic(if (modelo.mudo.value) Icones.mudo else Icones.som, if (modelo.mudo.value) Perigo else TextoMedio, 21.dp)
        }
    }
}

// -- o chat ------------------------------------------------------------------------

/**
 * Segurar = gravar a fala; soltar = mandar (o átomo é o botão de falar).
 *
 * **O dedo é do átomo do começo ao fim.** Com o `detectTapGestures` da 1ª
 * versão (beta 0.6), o átomo ficava dentro de coisas que também querem o dedo
 * (a rolagem do chat novo, o arrastar da gaveta): o dedo mexia um pouco, uma
 * delas pegava o toque, o toque era "cancelado" e a fala ia embora com o Léo
 * ainda falando (22/10/2026). Aqui o átomo consome cada movimento antes de
 * todo mundo (passe Initial) e só manda quando TODOS os dedos saem da tela.
 */
@Composable
private fun Modifier.segurarPraFalar(modelo: Jarvis): Modifier {
    val contexto = LocalContext.current
    val vibrar = LocalHapticFeedback.current
    val pedirMicrofone = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
    val vivo = modelo.conectado.value
    return this.pointerInput(vivo) {
        awaitEachGesture {
            awaitFirstDown(requireUnconsumed = false, pass = PointerEventPass.Initial).consume()
            val temPermissao = ContextCompat.checkSelfPermission(
                contexto, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
            val gravar = vivo && temPermissao
            if (vivo && !temPermissao) pedirMicrofone.launch(Manifest.permission.RECORD_AUDIO)
            if (gravar) {
                vibrar.performHapticFeedback(HapticFeedbackType.LongPress)
                modelo.comecarFala()
            }
            try {
                do {
                    val evento = awaitPointerEvent(PointerEventPass.Initial)
                    evento.changes.forEach { it.consume() }
                } while (evento.changes.any { it.pressed })
            } finally {
                if (gravar) modelo.terminarFala()
            }
        }
    }
}

@Composable
private fun AtomoVivo(modelo: Jarvis, tamanho: androidx.compose.ui.unit.Dp, modifier: Modifier = Modifier) {
    val estado = modelo.estadoVisivel
    Atomo(
        cor = corDoEstado(estado),
        escala = when (estado) {
            "sem_conexao" -> 0.80f; "escutando" -> 1.14f; "falando" -> 1.06f
            "pensando" -> 1.02f; else -> 0.92f
        },
        velocidade = when (estado) {
            "sem_conexao" -> 0f; "pensando" -> 2.2f; "falando" -> 1.25f
            "escutando" -> 1.15f; else -> 0.6f
        },
        brilho = when (estado) { "sem_conexao" -> 0.28f; "pensando" -> 1.2f; "pronto" -> 0.8f; else -> 1f },
        turbulencia = when (estado) { "pensando" -> 1f; "escutando" -> 0.35f; "falando" -> 0.25f; else -> 0f },
        nivel = modelo.nivel.floatValue,
        parado = !modelo.conectado.value,
        pulsando = estado == "pronto",
        fundo = Fundo,
        modifier = modifier.size(tamanho),
    )
}

@Composable
private fun Chat(modelo: Jarvis, abrirSeletores: () -> Unit) {
    var texto by remember { mutableStateOf("") }
    // Link ou texto que chegou por "Compartilhar → Jarvis": entra na barra.
    LaunchedEffect(modelo.textoCompartilhado.value) {
        val veio = modelo.textoCompartilhado.value
        if (veio.isNotEmpty()) {
            texto = listOf(texto, veio).filter { it.isNotBlank() }.joinToString(" ")
            modelo.textoCompartilhado.value = ""
        }
    }
    val lista = rememberLazyListState()
    val antiga = modelo.vendo.value.isNotEmpty()
    val falas = if (antiga) modelo.mensagensVendo else modelo.mensagens
    val boasVindas = !antiga && modelo.mensagens.isEmpty()
    val escrevendo = falas.any { it.escrevendo }
    val pensando = modelo.trabalhando && !escrevendo

    // Acompanha o fim da conversa: fala nova e o texto crescendo.
    val ultimo = falas.lastOrNull()
    LaunchedEffect(falas.size, ultimo?.texto?.length, pensando, modelo.vendo.value) {
        val n = falas.size + (if (pensando) 1 else 0)
        if (n > 0) lista.scrollToItem(n - 1, Int.MAX_VALUE / 2)
    }

    fun enviar(t: String = texto) {
        if (t.isBlank() && modelo.anexos.isEmpty()) return
        if (!modelo.anexosProntos) return
        modelo.enviarTexto(t)
        texto = ""
    }

    Column(Modifier.fillMaxSize()) {
        if (boasVindas) {
            // O chat novo: o átomo grande (segura pra falar) e a saudação.
            Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()),
                horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                Spacer(Modifier.height(24.dp))
                AtomoVivo(modelo, 190.dp, Modifier.segurarPraFalar(modelo))
                Text(rotuloDoEstado(modelo.estadoVisivel), color = corDoEstado(modelo.estadoVisivel),
                    fontSize = 11.sp, letterSpacing = 2.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(14.dp))
                Text(saudacao(modelo.nomeUsuario.value), color = Texto, fontSize = 28.sp, fontWeight = FontWeight.Medium)
                Spacer(Modifier.height(6.dp))
                Text("Segura o átomo pra falar, ou escreve aqui embaixo.", color = Fraco, fontSize = 14.sp,
                    textAlign = TextAlign.Center, modifier = Modifier.padding(horizontal = 30.dp))
                Spacer(Modifier.height(24.dp))
                Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (ideia in listOf("Como tá o tempo amanhã?", "O que eu tenho essa semana?",
                        "Toca alguma coisa pra focar")) {
                        Text(ideia, color = TextoMedio, fontSize = 14.sp,
                            modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp))
                                .background(Lateral).border(1.dp, Traco, RoundedCornerShape(14.dp))
                                .clickable(enabled = modelo.conectado.value) { enviar(ideia) }
                                .padding(horizontal = 14.dp, vertical = 12.dp))
                    }
                }
                Spacer(Modifier.height(16.dp))
            }
        } else {
            LazyColumn(
                state = lista,
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 12.dp),
                verticalArrangement = Arrangement.spacedBy(18.dp),
            ) {
                items(falas) { m -> Item(m) { r -> enviar(r) } }
                if (pensando) item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        AtomoFixo(Roxo, 26.dp)
                        Spacer(Modifier.width(10.dp))
                        Text(if (falas.lastOrNull()?.texto == "Pensando com calma") "Pensando com calma…" else "Pensando…",
                            color = Fraco, fontSize = 14.sp)
                    }
                }
            }
        }

        if (antiga) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                Text("O que tu escrever continua esta conversa · ", color = Fraco, fontSize = 12.sp)
                Text("Voltar", color = Azul, fontSize = 12.sp, fontWeight = FontWeight.Medium,
                    modifier = Modifier.clickable { modelo.abrir("") })
            }
        }

        // Os anexos esperando a mensagem: miniatura, nome e o ✕.
        if (modelo.anexos.isNotEmpty()) {
            Row(
                Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                modelo.anexos.forEach { a -> Chip(a) { modelo.tirarAnexo(a) } }
            }
            Spacer(Modifier.height(8.dp))
        }

        // No chat novo, os seletores à mão (na conversa, tocar no título abre).
        if (boasVindas) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp).padding(bottom = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Pilula(null, if (personaAtiva.value == "friday") "Friday" else "Jarvis", Azul, abrirSeletores)
                Pilula(Icones.raio, nomesModelo[modelo.modelo.value] ?: modelo.modelo.value, null, abrirSeletores)
                Pilula(Icones.barras, nomesEsforco[modelo.esforco.value] ?: modelo.esforco.value, null, abrirSeletores)
            }
        }

        BarraDeEscrever(modelo, texto, { texto = it }, mostrarAtomo = !boasVindas, enviar = { enviar() })
    }
}

private fun saudacao(nome: String): String {
    val h = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
    return (if (h < 5) "Boa noite" else if (h < 12) "Bom dia" else if (h < 18) "Boa tarde" else "Boa noite") +
        (if (nome.isNotBlank()) ", $nome." else ".")
}

@Composable
private fun Pilula(icone: androidx.compose.ui.graphics.vector.ImageVector?, nome: String, bola: Color?, aoClicar: () -> Unit) {
    Row(Modifier.height(32.dp).clip(RoundedCornerShape(9.dp)).background(Lateral)
        .border(1.dp, Traco, RoundedCornerShape(9.dp)).clickable { aoClicar() }.padding(horizontal = 10.dp),
        verticalAlignment = Alignment.CenterVertically) {
        if (bola != null) Box(Modifier.size(7.dp).clip(CircleShape).background(bola))
        if (icone != null) Ic(icone, TextoMedio, 13.dp)
        Spacer(Modifier.width(6.dp))
        Text(nome, color = TextoMedio, fontSize = 13.sp)
        Spacer(Modifier.width(4.dp))
        Ic(Icones.seta, MuitoFraco, 12.dp)
    }
}

@Composable
private fun BarraDeEscrever(modelo: Jarvis, texto: String, mudar: (String) -> Unit, mostrarAtomo: Boolean, enviar: () -> Unit) {
    val escolherArquivos = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        uris.take(10).forEach { modelo.anexar(it) }
    }
    val temTexto = texto.isNotBlank() || modelo.anexos.isNotEmpty()
    // Trabalhando e sem nada escrito: o enviar vira o Parar.
    val modoParar = modelo.trabalhando && !temTexto
    // [átomo] [barra: texto + clipe] [enviar]. O átomo e o enviar ocupam o
    // mesmo espaço dos dois lados, e a barra fica no centro da tela (pedido
    // do Léo, 22/10/2026: o enviar dentro da barra ficava feio e torto).
    val lado = 54.dp
    Row(Modifier.fillMaxWidth().padding(start = 8.dp, end = 8.dp, bottom = 10.dp, top = 2.dp),
        verticalAlignment = Alignment.CenterVertically) {
        if (mostrarAtomo) {
            // O átomo pequeno: segura pra falar, como o grande.
            AtomoVivo(modelo, lado, Modifier.segurarPraFalar(modelo))
            Spacer(Modifier.width(6.dp))
        }
        Row(
            Modifier.weight(1f).clip(RoundedCornerShape(24.dp)).background(Superficie)
                .border(1.dp, Color(0xFF263042), RoundedCornerShape(24.dp))
                .padding(start = 16.dp, end = 6.dp, top = 5.dp, bottom = 5.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(Modifier.weight(1f).padding(vertical = 8.dp)) {
                if (texto.isEmpty()) Text(
                    when {
                        // Curto: na barra estreita do celular a frase longa cortava.
                        !modelo.conectado.value -> "Esperando…"
                        modelo.anexos.isNotEmpty() -> "Sobre o anexo…"
                        else -> "Digite aqui…"
                    }, color = MuitoFraco, fontSize = 15.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                BasicTextField(
                    value = texto, onValueChange = mudar,
                    textStyle = TextStyle(color = Texto, fontSize = 15.sp, fontFamily = Inter),
                    cursorBrush = SolidColor(Azul), maxLines = 6,
                    keyboardOptions = KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Send),
                    keyboardActions = KeyboardActions(onSend = { enviar() }),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            Box(Modifier.size(36.dp).clip(CircleShape).clickable { escolherArquivos.launch("*/*") },
                contentAlignment = Alignment.Center) { Ic(Icones.clipe, Fraco, 20.dp) }
        }
        Spacer(Modifier.width(6.dp))
        // O enviar, fora da barra (vira Parar com ele trabalhando e o campo vazio).
        val ativo = modelo.conectado.value && (modoParar || (temTexto && modelo.anexosProntos))
        // Apagado = a cor misturada com o fundo, sem .alpha(): a camada do
        // alpha não redesenhava com o teclado aberto, e o botão sumia até ser
        // tocado (Léo, 22/10/2026).
        val cor = if (modoParar) Texto else Azul
        val fundoDoBotao = if (ativo) cor else lerp(Fundo, cor, 0.35f)
        Box(Modifier.size(lado), contentAlignment = Alignment.Center) {
            Box(
                Modifier.size(48.dp).clip(CircleShape).background(fundoDoBotao)
                    .clickable(enabled = ativo) { if (modoParar) modelo.parar() else enviar() },
                contentAlignment = Alignment.Center,
            ) {
                if (modoParar) Box(Modifier.size(13.dp).clip(RoundedCornerShape(3.dp)).background(Fundo))
                else Ic(Icones.enviar, if (ativo) Color(0xFF06101D) else lerp(fundoDoBotao, Color(0xFF06101D), 0.5f), 20.dp)
            }
        }
    }
}

// -- uma fala ---------------------------------------------------------------------

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun Item(m: Mensagem, responder: (String) -> Unit) {
    val area = LocalClipboardManager.current
    when (m.quem) {
        Quem.AVISO -> Text(m.texto, color = Perigo, fontSize = 12.sp, textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth())
        Quem.ATIVIDADE -> {
            var aberta by remember { mutableStateOf(false) }
            Column(Modifier.padding(start = 36.dp)) {
                Row(Modifier.clip(RoundedCornerShape(16.dp)).background(Lateral)
                    .border(1.dp, Traco, RoundedCornerShape(16.dp)).clickable { aberta = !aberta }
                    .padding(horizontal = 11.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(7.dp).clip(CircleShape).background(Color(0xFF38D39F)))
                    Spacer(Modifier.width(7.dp))
                    Text((if (m.passos.size > 1) "${m.passos.size} passos · " else "") + m.texto,
                        color = Fraco, fontSize = 12.5.sp, maxLines = 1, overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.widthIn(max = 250.dp))
                    Spacer(Modifier.width(4.dp))
                    Ic(if (aberta) Icones.seta else Icones.direita, MuitoFraco, 13.dp)
                }
                if (aberta) Column(Modifier.padding(start = 12.dp, top = 6.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    for (p in m.passos) Text("·  $p", color = Fraco, fontSize = 12.sp, maxLines = 2,
                        overflow = TextOverflow.Ellipsis)
                }
            }
        }
        Quem.VOCE -> Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.End) {
            Column(
                Modifier.widthIn(max = 300.dp)
                    .clip(RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp, bottomStart = 18.dp, bottomEnd = 6.dp))
                    .background(Superficie2)
                    .border(1.dp, Traco, RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp, bottomStart = 18.dp, bottomEnd = 6.dp))
                    .padding(horizontal = 14.dp, vertical = 10.dp),
            ) {
                for (n in m.anexos) Row(verticalAlignment = Alignment.CenterVertically) {
                    Ic(Icones.clipe, Fraco, 12.dp); Spacer(Modifier.width(4.dp))
                    Text(n, color = Fraco, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Text(m.texto, color = Texto, fontSize = 15.sp, lineHeight = 21.sp)
            }
            Row(Modifier.padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Ic(Icones.daOrigem(m.origem), MuitoFraco, 11.dp)
                Spacer(Modifier.width(4.dp))
                val origem = when (m.origem) { "voz" -> "voz"; "celular" -> "celular"; "relogio" -> "relógio"; else -> "digitado" }
                Text("$origem · ${hora(m.quando)}", color = MuitoFraco, fontSize = 11.sp)
            }
        }
        Quem.JARVIS, Quem.PAINEL -> Row {
            AtomoFixo(Azul, 26.dp, Modifier.padding(top = 2.dp))
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (m.perguntando) Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(7.dp).clip(CircleShape).background(Pergunta))
                    Spacer(Modifier.width(6.dp))
                    Text("Esperando tua resposta", color = Pergunta, fontSize = 11.5.sp)
                }
                val cartao = m.quem == Quem.PAINEL && m.titulo.isNotEmpty()
                Column(
                    if (cartao) Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Superficie)
                        .border(1.dp, Traco, RoundedCornerShape(12.dp)).padding(14.dp) else Modifier
                ) {
                    if (cartao) {
                        Text(m.titulo, color = Texto, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Spacer(Modifier.height(8.dp))
                    }
                    Markdown(if (m.escrevendo) m.texto + " ▍" else m.texto, Color(0xFFD7DDE7),
                        Modifier.combinedClickableCopiar { area.setText(AnnotatedString(m.texto)) })
                }
                if (m.perguntando && m.opcoes.isNotEmpty()) {
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        for (o in m.opcoes) Text(o, color = Color(0xFFFFCF8A), fontSize = 14.sp, fontWeight = FontWeight.Medium,
                            modifier = Modifier.clip(RoundedCornerShape(10.dp)).background(Color(0xFF2A2114))
                                .border(1.dp, Color(0xFF5C4422), RoundedCornerShape(10.dp))
                                .clickable { responder(o) }.padding(horizontal = 13.dp, vertical = 8.dp))
                    }
                }
            }
        }
    }
}

/** Segurar a resposta copia o texto inteiro. */
@OptIn(ExperimentalFoundationApi::class)
private fun Modifier.combinedClickableCopiar(copiar: () -> Unit): Modifier =
    this.combinedClickable(onClick = {}, onLongClick = copiar,
        indication = null, interactionSource = null)

@Composable
private fun Chip(a: Anexo, tirar: () -> Unit) {
    Row(
        Modifier.clip(RoundedCornerShape(12.dp)).background(Superficie)
            .border(1.dp, if (a.erro.isNotEmpty()) Perigo else Traco, RoundedCornerShape(12.dp))
            .padding(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(44.dp).clip(RoundedCornerShape(8.dp)).background(Traco),
            contentAlignment = Alignment.Center) {
            if (a.miniatura != null) {
                Image(a.miniatura.asImageBitmap(), a.nome, contentScale = ContentScale.Crop,
                    modifier = Modifier.size(44.dp))
            } else {
                Ic(Icones.clipe, Fraco, 18.dp)
            }
            if (a.idServidor == null && a.erro.isEmpty()) {
                CircularProgressIndicator(Modifier.size(22.dp), color = Texto, strokeWidth = 2.dp)
            }
        }
        Column(Modifier.widthIn(max = 120.dp).padding(horizontal = 8.dp)) {
            Text(a.nome, color = Texto, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (a.erro.isNotEmpty()) Text(a.erro, color = Perigo, fontSize = 11.sp, maxLines = 1)
        }
        Box(Modifier.size(28.dp).clip(CircleShape).clickable { tirar() }, contentAlignment = Alignment.Center) {
            Ic(Icones.fechar, Fraco, 15.dp)
        }
    }
}

// -- a gaveta: as conversas --------------------------------------------------------

@Composable
private fun Gaveta(modelo: Jarvis, fechar: () -> Unit) {
    var busca by remember { mutableStateOf("") }
    val selecionada = modelo.vendo.value.ifEmpty { modelo.conversaAtual.value }
    Column(Modifier.fillMaxHeight().safeDrawingPadding()) {
        Row(Modifier.height(56.dp).padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
            AtomoFixo(Azul, 22.dp)
            Spacer(Modifier.width(10.dp))
            Text("JARVIS", color = Fraco, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 3.sp)
        }
        Row(
            Modifier.padding(horizontal = 14.dp).fillMaxWidth().height(44.dp).clip(RoundedCornerShape(11.dp))
                .background(Superficie).border(1.dp, Traco, RoundedCornerShape(11.dp))
                .clickable { modelo.novaConversa(); fechar() }.padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(Modifier.size(22.dp).clip(RoundedCornerShape(7.dp)).background(Azul), contentAlignment = Alignment.Center) {
                Ic(Icones.mais, Color(0xFF06101D), 15.dp)
            }
            Spacer(Modifier.width(10.dp))
            Text("Novo chat", color = Texto, fontSize = 15.sp, fontWeight = FontWeight.Medium)
        }
        Row(Modifier.padding(horizontal = 26.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Ic(Icones.lupa, if (busca.isEmpty()) MuitoFraco else TextoMedio, 16.dp)
            Spacer(Modifier.width(10.dp))
            Box {
                if (busca.isEmpty()) Text("Procurar conversa", color = MuitoFraco, fontSize = 14.sp)
                BasicTextField(busca, { busca = it }, singleLine = true,
                    textStyle = TextStyle(color = Texto, fontSize = 14.sp, fontFamily = Inter),
                    cursorBrush = SolidColor(Azul), modifier = Modifier.fillMaxWidth())
            }
        }
        val visiveis = modelo.conversas.filter { busca.isBlank() || it.titulo.contains(busca.trim(), ignoreCase = true) }
        // A conversa de agora ainda sem nada salvo (a NOVA acabou de ligar) entra depois das fixadas.
        val comAtual = if (modelo.conversaAtual.value.isNotEmpty() && modelo.conversas.none { it.id == modelo.conversaAtual.value } && busca.isBlank())
            visiveis.filter { it.fixada } +
                Conversa(modelo.conversaAtual.value, "Chat novo", System.currentTimeMillis() / 1000.0, "nova") +
                visiveis.filter { !it.fixada }
        else visiveis
        LazyColumn(Modifier.weight(1f)) {
            var grupoAnterior = ""
            for (c in comAtual) {
                val grupo = if (c.fixada) "Fixadas" else grupoDe(c.quando)
                if (grupo != grupoAnterior) {
                    grupoAnterior = grupo
                    // A chave vem da primeira conversa do grupo: um grupo repetido não derruba o app.
                    item(key = "g-${c.id}") {
                        Text(grupo.uppercase(), color = MuitoFraco, fontSize = 11.sp, fontWeight = FontWeight.SemiBold,
                            letterSpacing = 0.8.sp, modifier = Modifier.padding(start = 22.dp, top = 14.dp, bottom = 6.dp))
                    }
                }
                item(key = c.id) {
                    ItemDaGaveta(modelo, c, c.id == selecionada && modelo.pagina.value == "chat") {
                        modelo.abrir(c.id); fechar()
                    }
                }
            }
        }
        // Embaixo: o estado, a memória e os ajustes.
        Box(Modifier.fillMaxWidth().height(1.dp).background(Traco))
        Row(Modifier.padding(horizontal = 18.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            val e = if (!modelo.conectado.value) "" else modelo.estado.value
            val cor = Color(when (e) {
                "dormindo" -> 0xFF7387A8; "ouvindo" -> 0xFF4DA3FF; "escutando" -> 0xFF38D39F
                "pensando" -> 0xFF9B7BFF; "falando" -> 0xFFFFB454; else -> 0xFF39435A
            })
            AtomoFixo(cor, 36.dp)
            Spacer(Modifier.width(12.dp))
            Column {
                Text(when (e) {
                    "dormindo" -> "DORMINDO"; "ouvindo" -> "OUVINDO"; "escutando" -> "ESCUTANDO VOCÊ"
                    "pensando" -> "PENSANDO"; "falando" -> "FALANDO"; else -> "SEM CONEXÃO"
                }, color = cor, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 1.6.sp)
                Text(if (!modelo.conectado.value) modelo.motivo.value
                    else if (modelo.nomePc.value.isNotEmpty()) "No PC ${modelo.nomePc.value}" else "No PC",
                    color = Fraco, fontSize = 12.sp)
            }
        }
        for ((pagina, nome, icone) in listOf(Triple("memoria", "Memórias", Icones.memoria), Triple("ajustes", "Ajustes", Icones.ajustes))) {
            val aqui = modelo.pagina.value == pagina
            Row(
                Modifier.padding(horizontal = 8.dp).fillMaxWidth().height(42.dp).clip(RoundedCornerShape(9.dp))
                    .background(if (aqui) Superficie2 else Color.Transparent)
                    .clickable {
                        modelo.pagina.value = if (aqui) "chat" else pagina
                        if (pagina == "memoria") modelo.pedirMemoria()
                        if (pagina == "ajustes") { modelo.fecharPasso(); modelo.abaAjustes.value = ""; modelo.pedirAjustes() }
                        fechar()
                    }.padding(horizontal = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Ic(icone, if (aqui) Texto else Fraco, 19.dp)
                Spacer(Modifier.width(12.dp))
                Text(nome, color = if (aqui) Texto else TextoMedio, fontSize = 14.sp)
            }
        }
        Spacer(Modifier.height(10.dp))
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ItemDaGaveta(modelo: Jarvis, c: Conversa, escolhida: Boolean, abrir: () -> Unit) {
    var menu by remember { mutableStateOf(false) }
    var confirmando by remember { mutableStateOf(false) }
    var renomeando by remember { mutableStateOf(false) }
    var novoTitulo by remember { mutableStateOf(c.titulo) }
    val eAtual = c.id == modelo.conversaAtual.value
    Box {
        Row(
            Modifier.padding(horizontal = 8.dp).fillMaxWidth().height(42.dp).clip(RoundedCornerShape(9.dp))
                .background(if (escolhida) Superficie2 else Color.Transparent)
                .combinedClickable(onClick = { if (!renomeando) abrir() },
                    onLongClick = { confirmando = false; menu = true })
                .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Ic(Icones.daOrigem(c.origem), if (escolhida) Azul else MuitoFraco, 15.dp)
            Spacer(Modifier.width(10.dp))
            if (renomeando) {
                BasicTextField(novoTitulo, { novoTitulo = it }, singleLine = true,
                    textStyle = TextStyle(color = Texto, fontSize = 14.sp, fontFamily = Inter),
                    cursorBrush = SolidColor(Azul),
                    keyboardOptions = KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = {
                        if (novoTitulo.isNotBlank() && novoTitulo != c.titulo) modelo.renomear(c.id, novoTitulo)
                        renomeando = false
                    }),
                    modifier = Modifier.weight(1f))
                Box(Modifier.size(30.dp).clip(CircleShape).clickable {
                    if (novoTitulo.isNotBlank() && novoTitulo != c.titulo) modelo.renomear(c.id, novoTitulo)
                    renomeando = false
                }, contentAlignment = Alignment.Center) { Ic(Icones.certo, Azul, 17.dp) }
            } else {
                Text(c.titulo, color = if (escolhida) Texto else TextoMedio, fontSize = 14.sp, maxLines = 1,
                    overflow = TextOverflow.Ellipsis)
            }
        }
        // Segurar abre o menu. Apagar pede confirmação NO PRÓPRIO menu.
        DropdownMenu(menu, { menu = false }, containerColor = Superficie2) {
            DropdownMenuItem(text = { Text(if (c.fixada) "Desafixar" else "Fixar no topo", color = Texto) },
                onClick = { menu = false; modelo.fixar(c.id, !c.fixada) })
            DropdownMenuItem(text = { Text("Renomear", color = Texto) }, onClick = {
                menu = false; novoTitulo = c.titulo; renomeando = true
            })
            DropdownMenuItem(
                text = {
                    Text(when {
                        eAtual -> "Apagar (é a conversa de agora)"
                        confirmando -> "Confirmar: mandar pra lixeira"
                        else -> "Apagar"
                    }, color = Color(0xFFFF8A8A), fontWeight = if (confirmando) FontWeight.SemiBold else FontWeight.Normal)
                },
                enabled = !eAtual,
                onClick = { if (!confirmando) confirmando = true else { menu = false; modelo.apagar(c.id) } },
            )
        }
    }
}

// -- cérebro, esforço e persona ------------------------------------------------------

@Composable
private fun Seletores(modelo: Jarvis) {
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(bottom = 28.dp)) {
        Grupo("Persona")
        Opcao("Jarvis", "O mordomo de humor seco", personaAtiva.value == "jarvis") { modelo.escolherPersona("jarvis") }
        Opcao("Friday", "Carinhosa e animada", personaAtiva.value == "friday") { modelo.escolherPersona("friday") }
        Grupo("Cérebro")
        for ((v, n, d) in listOf(
            Triple("auto", "Automático", "O Sonnet atende e chama o Opus no pedido pesado"),
            Triple("haiku", "Haiku", "O mais rápido"),
            Triple("sonnet", "Sonnet", "Equilibrado"),
            Triple("opus", "Opus", "O mais inteligente, mais lento"),
        )) Opcao(n, d, modelo.modelo.value == v) { modelo.escolherModelo(v) }
        Grupo("Esforço")
        for ((v, n, d) in listOf(
            Triple("low", "Baixo", "Responde rápido, pensa pouco"),
            Triple("medium", "Médio", "O padrão"),
            Triple("high", "Alto", "Pensa mais antes de responder"),
            Triple("xhigh", "Muito alto", "Para coisa difícil"),
            Triple("max", "Máximo", "Tudo o que ele tem (mais lento)"),
        )) Opcao(n, d, modelo.esforco.value == v) { modelo.escolherEsforco(v) }
    }
}

@Composable
private fun Grupo(nome: String) {
    Text(nome.uppercase(), color = MuitoFraco, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 0.8.sp,
        modifier = Modifier.padding(start = 12.dp, top = 14.dp, bottom = 6.dp))
}

@Composable
private fun Opcao(nome: String, descricao: String, escolhida: Boolean, habilitada: Boolean = true, aoEscolher: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(if (escolhida) Realce else Color.Transparent)
            .clickable(enabled = habilitada) { aoEscolher() }.alpha(if (habilitada) 1f else 0.45f)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(nome, color = Texto, fontSize = 15.sp, fontWeight = FontWeight.Medium)
            Text(descricao, color = Fraco, fontSize = 12.5.sp)
        }
        if (escolhida) Ic(Icones.certo, Azul, 18.dp)
    }
}

// -- memória e ajustes ----------------------------------------------------------------

@Composable
private fun PaginaMemoria(modelo: Jarvis) {
    // As Memórias (beta 0.14.5): a lista (Jarvis/Friday, grupos, pessoas) e,
    // ao tocar, a memória aberta para editar e salvar. Salvar não passa por
    // cima do que o Jarvis escreveu enquanto o Léo editava: vem o aviso.
    LaunchedEffect(Unit) { modelo.pedirMemorias() }
    val aberta = modelo.memoriaAberta.value
    if (aberta == null) ListaDeMemorias(modelo) else MemoriaEditando(modelo, aberta)
}

private fun quandoCurto(iso: String) =
    if (iso.length >= 16) "${iso.substring(8, 10)}/${iso.substring(5, 7)} às ${iso.substring(11, 16)}" else ""

@Composable
private fun ListaDeMemorias(modelo: Jarvis) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text("Memórias", color = Texto, fontSize = 26.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(4.dp))
        Text("Tudo o que a NOVA guarda. Toca numa pra ler, corrigir e salvar.", color = Fraco, fontSize = 14.sp)
        Spacer(Modifier.height(18.dp))
        if (modelo.memorias.isEmpty())
            Text(if (modelo.memoriasCarregando.value) "Carregando…" else "Nenhuma memória ainda.", color = Fraco, fontSize = 15.sp)
        for (m in modelo.memorias) {
            Row(
                Modifier.fillMaxWidth().padding(bottom = 8.dp).clip(RoundedCornerShape(14.dp)).background(Lateral)
                    .border(1.dp, Traco, RoundedCornerShape(14.dp)).clickable { modelo.abrirMemoria(m) }
                    .padding(horizontal = 14.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(Modifier.size(38.dp).clip(RoundedCornerShape(10.dp)).background(Realce), contentAlignment = Alignment.Center) {
                    Text(when (m.tipo) { "personas" -> "★"; "recados" -> "⏰"; "grupo" -> "👥"; "pessoa" -> "👤"; else -> "•" },
                        color = Azul, fontSize = 17.sp)
                }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(m.titulo, color = Texto, fontSize = 15.5.sp, fontWeight = FontWeight.Medium, maxLines = 1,
                        overflow = TextOverflow.Ellipsis)
                    Text(when (m.tipo) {
                        "personas" -> "O que o Jarvis e a Friday sabem de ti"
                        "recados" -> "Recados marcados da NOVA"
                        "grupo" -> "Grupo de WhatsApp"
                        "pessoa" -> "Pessoa"
                        else -> ""
                    } + quandoCurto(m.atualizado).let { if (it.isEmpty()) "" else " · $it" },
                        color = Fraco, fontSize = 12.5.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
        }
    }
}

@Composable
private fun MemoriaEditando(modelo: Jarvis, aberta: MemoriaAberta) {
    var texto by remember(aberta.id, aberta.versao) { mutableStateOf(aberta.texto) }
    val mudou = texto != aberta.texto && aberta.versao.isNotEmpty()
    val conflito = modelo.memoriaConflito.value
    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp, vertical = 12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(40.dp).clip(CircleShape).clickable { modelo.pedirMemorias() }, contentAlignment = Alignment.Center) {
                Text("‹", color = TextoMedio, fontSize = 26.sp)
            }
            Text(aberta.titulo, color = Texto, fontSize = 19.sp, fontWeight = FontWeight.SemiBold, maxLines = 1,
                overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            Box(
                Modifier.clip(RoundedCornerShape(10.dp)).background(Azul)
                    .alpha(if (mudou && conflito == null && !modelo.memoriaSalvando.value) 1f else 0.4f)
                    .clickable(enabled = mudou && conflito == null && !modelo.memoriaSalvando.value) { modelo.salvarMemoria(texto) }
                    .padding(horizontal = 16.dp, vertical = 8.dp),
            ) {
                Text(if (modelo.memoriaSalvando.value) "Salvando…" else "Salvar", color = Color(0xFF06101D),
                    fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
            }
        }
        if (conflito != null) {
            Spacer(Modifier.height(10.dp))
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Superficie)
                .border(1.dp, Pergunta, RoundedCornerShape(12.dp)).padding(14.dp)) {
                Text("A NOVA mudou esta memória enquanto tu editava. Nada foi salvo ainda: escolhe o que fica.",
                    color = Texto, fontSize = 14.sp)
                Spacer(Modifier.height(10.dp))
                Row {
                    Box(Modifier.clip(RoundedCornerShape(9.dp)).border(1.dp, Traco, RoundedCornerShape(9.dp))
                        .clickable { modelo.usarMemoriaDoJarvis() }.padding(horizontal = 12.dp, vertical = 7.dp)) {
                        Text("Usar a da NOVA", color = TextoMedio, fontSize = 13.sp)
                    }
                    Spacer(Modifier.width(8.dp))
                    Box(Modifier.clip(RoundedCornerShape(9.dp)).background(Azul)
                        .clickable { modelo.salvarMemoria(texto, conflito.second) }.padding(horizontal = 12.dp, vertical = 7.dp)) {
                        Text("Salvar a minha por cima", color = Color(0xFF06101D), fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            }
        }
        Spacer(Modifier.height(12.dp))
        Box(Modifier.fillMaxWidth().weight(1f).clip(RoundedCornerShape(14.dp)).background(Lateral)
            .border(1.dp, Traco, RoundedCornerShape(14.dp))) {
            if (aberta.versao.isEmpty()) {
                Text("Carregando…", color = Fraco, fontSize = 15.sp, modifier = Modifier.padding(16.dp))
            } else {
                BasicTextField(
                    texto, { texto = it },
                    modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
                    textStyle = androidx.compose.ui.text.TextStyle(color = Texto, fontSize = 15.sp, lineHeight = 22.sp),
                    cursorBrush = androidx.compose.ui.graphics.SolidColor(Azul),
                )
            }
        }
    }
}

// -- os Ajustes (beta 0.17.0: categorias, como os da janela) --------------------------

private data class Categoria(val id: String, val nome: String, val sub: String, val icone: ImageVector)

private val categoriasDosAjustes = listOf(
    "Preferências" to listOf(
        Categoria("geral", "Geral", "Teu nome e este celular", Icones.geral),
        Categoria("voz", "Voz e som", "Sempre ouvindo, volume da voz", Icones.voz),
        Categoria("avisos", "Avisos", "O que ele avisa aqui", Icones.sino),
        Categoria("uso", "Uso", "A assinatura do Claude", Icones.uso)),
    "Personalização" to listOf(
        Categoria("personas", "Personas", "Jarvis e Friday", Icones.personas),
        Categoria("conexoes", "Conexões", "WhatsApp, celular, relógio…", Icones.conexoes)),
    "" to listOf(Categoria("sobre", "Sobre a NOVA", "Versão e o que é a NOVA", Icones.sobre)),
)

@Composable
private fun PaginaAjustes(modelo: Jarvis) {
    val aba = modelo.abaAjustes.value
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp)) {
        when (aba) {
            "" -> ListaDeCategorias(modelo)
            "geral" -> AjustesGeral(modelo)
            "voz" -> AjustesVoz(modelo)
            "avisos" -> AjustesAvisos(modelo)
            "uso" -> AjustesUso(modelo)
            "personas" -> AjustesPersonas(modelo)
            "conexoes" -> if (modelo.passoConexao.value.isEmpty()) AjustesConexoes(modelo) else PassoDaConexao(modelo)
            else -> AjustesSobre(modelo)
        }
        Spacer(Modifier.height(24.dp))
    }
}

/** A lista das categorias: o toque entra em cada uma. */
@Composable
private fun ListaDeCategorias(modelo: Jarvis) {
    for ((grupo, itens) in categoriasDosAjustes) {
        if (grupo.isNotEmpty()) Text(grupo, color = MuitoFraco, fontSize = 12.5.sp,
            modifier = Modifier.padding(start = 6.dp, top = 14.dp, bottom = 8.dp))
        else Spacer(Modifier.height(14.dp))
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Lateral)
            .border(1.dp, Traco, RoundedCornerShape(16.dp))) {
            itens.forEachIndexed { i, c ->
                if (i > 0) Box(Modifier.fillMaxWidth().height(1.dp).background(Traco))
                Row(Modifier.fillMaxWidth().clickable { modelo.abaAjustes.value = c.id }
                    .padding(horizontal = 14.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(34.dp).clip(RoundedCornerShape(10.dp)).background(Superficie2),
                        contentAlignment = Alignment.Center) { Ic(c.icone, Azul, 18.dp) }
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text(c.nome, color = Texto, fontSize = 15.sp)
                        Text(c.sub, color = Fraco, fontSize = 12.5.sp)
                    }
                    Ic(Icones.direita, MuitoFraco, 18.dp)
                }
            }
        }
    }
}

/** Um bloco com título (e uma linha explicando, se tiver). */
@Composable
private fun SecaoDosAjustes(titulo: String, dica: String = "", conteudo: @Composable () -> Unit) {
    Text(titulo, color = Texto, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
        modifier = Modifier.padding(top = 14.dp, bottom = if (dica.isEmpty()) 4.dp else 2.dp))
    if (dica.isNotEmpty()) Text(dica, color = Fraco, fontSize = 13.sp, modifier = Modifier.padding(bottom = 8.dp))
    conteudo()
    Spacer(Modifier.height(12.dp))
}

/** Uma linha de ajuste: o nome (e a explicação) e o controle. `embaixo`: o controle vai na linha de baixo. */
@Composable
private fun LinhaDeAjuste(titulo: String, descricao: String = "", ultima: Boolean = false, embaixo: Boolean = false,
                          controle: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth()) {
        if (embaixo) {
            Column(Modifier.padding(vertical = 12.dp)) {
                Text(titulo, color = Texto, fontSize = 14.sp)
                if (descricao.isNotEmpty()) Text(descricao, color = Fraco, fontSize = 12.5.sp, modifier = Modifier.padding(top = 2.dp))
                Spacer(Modifier.height(10.dp))
                controle()
            }
        } else Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(titulo, color = Texto, fontSize = 14.sp)
                if (descricao.isNotEmpty()) Text(descricao, color = Fraco, fontSize = 12.5.sp, modifier = Modifier.padding(top = 2.dp))
            }
            Spacer(Modifier.width(14.dp))
            controle()
        }
        if (!ultima) Box(Modifier.fillMaxWidth().height(1.dp).background(Traco))
    }
}

@Composable
private fun Chave(ligado: Boolean, aoTrocar: () -> Unit) {
    Switch(checked = ligado, onCheckedChange = { aoTrocar() },
        colors = SwitchDefaults.colors(checkedTrackColor = Azul, checkedThumbColor = Color.White,
            uncheckedTrackColor = Superficie2, uncheckedThumbColor = Fraco, uncheckedBorderColor = TracoForte))
}

@Composable
private fun AjustesGeral(modelo: Jarvis) {
    SecaoDosAjustes("Você") {
        var nome by remember(modelo.nomeUsuario.value) { mutableStateOf(modelo.nomeUsuario.value) }
        LinhaDeAjuste("Seu nome", "Como o Jarvis e a Friday te chamam. É o mesmo da janela.", ultima = true, embaixo = true) {
            Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(9.dp)).background(Superficie)
                .border(1.dp, Traco, RoundedCornerShape(9.dp)).padding(horizontal = 12.dp, vertical = 11.dp)) {
                if (nome.isEmpty()) Text("Como ele te chama", color = MuitoFraco, fontSize = 14.sp, maxLines = 1)
                BasicTextField(nome, { nome = it.take(30) }, singleLine = true,
                    textStyle = TextStyle(color = Texto, fontSize = 14.sp, fontFamily = Inter),
                    cursorBrush = SolidColor(Azul),
                    keyboardOptions = KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = {
                        if (nome.trim() != modelo.nomeUsuario.value) modelo.mudarNome(nome)
                    }),
                    modifier = Modifier.fillMaxWidth())
            }
        }
    }
    SecaoDosAjustes("Este celular") {
        LinhaDeAjuste("Ligado ao PC", ultima = false) {
            Text(modelo.nomePc.value.ifEmpty { "—" }, color = TextoMedio, fontSize = 14.sp)
        }
        LinhaDeAjuste("Trocar o link do PC", "Para ligar este celular a outro PC (ou colar o link de novo).", ultima = true) {
            Text("Trocar", color = Perigo, fontSize = 14.sp,
                modifier = Modifier.clip(RoundedCornerShape(9.dp)).border(1.dp, Color(0xFF5C2A2C), RoundedCornerShape(9.dp))
                    .clickable { modelo.esquecer() }.padding(horizontal = 14.dp, vertical = 8.dp))
        }
    }
}

@Composable
private fun AjustesVoz(modelo: Jarvis) {
    val alternarOuvido = lembrarAlternarOuvido(modelo)
    SecaoDosAjustes("Neste celular") {
        LinhaDeAjuste("Sempre ouvindo", "O \"hey Jarvis\" funciona com o app fechado e a tela desligada (o mesmo botão do topo).",
            ultima = true) { Chave(modelo.sempreOuvindo.value) { alternarOuvido() } }
    }
    SecaoDosAjustes("No PC") {
        // 100% é o de sempre e é o teto: daqui só se abaixa (o volume já machucou o ouvido do Léo).
        var volume by remember(modelo.volumeVoz.intValue) { mutableFloatStateOf(modelo.volumeVoz.intValue.toFloat()) }
        LinhaDeAjuste("Volume da voz", "O volume do Jarvis e da Friday na caixa de som do PC.", ultima = true, embaixo = true) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Slider(volume, { volume = it }, valueRange = 0f..100f, steps = 19,
                    onValueChangeFinished = { modelo.mudarVolumeVoz(volume.roundToInt()) },
                    enabled = modelo.conectado.value, modifier = Modifier.weight(1f),
                    colors = SliderDefaults.colors(thumbColor = Color.White, activeTrackColor = Azul,
                        inactiveTrackColor = TracoForte, activeTickColor = Color.Transparent, inactiveTickColor = Color.Transparent))
                Spacer(Modifier.width(12.dp))
                Text("${volume.roundToInt()}%", color = TextoMedio, fontSize = 14.sp, modifier = Modifier.width(44.dp),
                    textAlign = TextAlign.End)
            }
        }
    }
    modelo.reconheceVoz.value?.let { reconhece ->
        SecaoDosAjustes("Quem fala") {
            LinhaDeAjuste("Reconhecer a tua voz",
                if (reconhece) "Só a tua voz pode apagar memória, mexer nos teus arquivos e outras coisas importantes."
                else "Sem o perfil da tua voz: qualquer pessoa que falar perto do PC vale como você.", ultima = true) {
                Text(if (reconhece) "Ligado" else "Desligado", color = TextoMedio, fontSize = 14.sp)
            }
        }
    }
}

@Composable
private fun AjustesAvisos(modelo: Jarvis) {
    SecaoDosAjustes("Avisos neste celular",
        "Nenhum aviso para ajustar ainda: eles aparecem aqui quando a conexão de cada um estiver ligada.") {}
}

@Composable
private fun AjustesUso(modelo: Jarvis) {
    val semDados = modelo.usoCinco.value < 0 && modelo.usoSemana.value < 0
    SecaoDosAjustes("Uso da assinatura",
        if (semDados) "Aparece depois do primeiro pedido ao Claude." else "Quanto do limite do Claude já foi usado.") {
        Column(Modifier.padding(top = 6.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
            BarraDeUso("Últimas 5 horas", modelo.usoCinco.value, modelo.voltaCinco.value, false)
            BarraDeUso("Esta semana", modelo.usoSemana.value, modelo.voltaSemana.value, true)
        }
    }
}

@Composable
private fun AjustesPersonas(modelo: Jarvis) {
    SecaoDosAjustes("Personas", "Quem responde. As duas dividem a conversa, a memória e as ferramentas; muda o jeito de falar, a voz e a cor.") {
        val lista = listOf(
            Triple("jarvis", "Jarvis", "O mordomo de humor seco. Chamado com \"Hey Jarvis\"."),
            Triple("friday", "Friday", "Carinhosa e animada. Chamada com \"Hey Friday\"."))
        lista.forEachIndexed { i, (id, nome, descricao) ->
            val ativa = personaAtiva.value == id
            LinhaDeAjuste(nome, descricao, ultima = i == lista.lastIndex) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(20.dp).clip(CircleShape).background(if (id == "friday") corDaFriday.value else CorDoJarvis))
                    Spacer(Modifier.width(12.dp))
                    Text(if (ativa) "Ativa" else "Usar", color = if (ativa) Color(0xFF38D39F) else TextoMedio, fontSize = 13.sp,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.width(72.dp).clip(RoundedCornerShape(9.dp))
                            .background(if (ativa) Color(0x2138D39F) else Color.Transparent)
                            .then(if (ativa) Modifier else Modifier.border(1.dp, TracoForte, RoundedCornerShape(9.dp)))
                            .clickable(enabled = !ativa && modelo.conectado.value) { modelo.escolherPersona(id) }
                            .padding(vertical = 8.dp))
                }
            }
        }
    }
}

/** O estado de uma conexão: Conectado (verde), Pronto (a cor da persona), Desligado. */
@Composable
private fun EtiquetaDeEstado(estado: String) {
    val (texto, cor) = when (estado) {
        "conectado" -> "Conectado" to Color(0xFF38D39F)
        "pronto" -> "Pronto" to Azul
        "desligado" -> "Desligado" to Fraco
        else -> "…" to Fraco
    }
    Text(texto, color = cor, fontSize = 12.sp, fontWeight = FontWeight.Medium,
        modifier = Modifier.clip(RoundedCornerShape(10.dp))
            .background(if (estado == "conectado" || estado == "pronto") cor.copy(alpha = 0.13f) else Superficie2)
            .padding(horizontal = 9.dp, vertical = 3.dp))
}

private data class InfoConexao(val id: String, val nome: String, val descricao: String, val icone: ImageVector,
                               val precisa: String = "")

// O nome e a descrição de cada conexão (os mesmos da janela); o estado vem do PC.
// `precisa`: a que tem que estar conectada antes (o cartão mostra "Precisa do…").
private val infoConexoes = listOf(
    InfoConexao("whatsapp", "WhatsApp", "Ler e mandar mensagens, e avisar quem te escreveu.", Icones.whats),
    InfoConexao("grupo", "Grupo do WhatsApp", "Responde no grupo da família quando chamam o Jarvis.", Icones.grupo, "whatsapp"),
    InfoConexao("fora", "Fora de casa", "O celular falar com o PC, em casa ou na rua (Tailscale).", Icones.globo),
    InfoConexao("celular", "Celular", "Este celular.", Icones.celular),
    InfoConexao("relogio", "Relógio", "Falar pelo relógio (Wear OS).", Icones.relogio, "celular"),
    InfoConexao("musica", "Música", "Tocar música e vídeo do YouTube pelo PC.", Icones.musica),
    InfoConexao("atalhos", "Atalhos", "Programas e pastas que ele abre pelo nome.", Icones.raioTraco),
)

private val Verde = Color(0xFF38D39F)
private const val TAILSCALE = "com.tailscale.ipn"

private fun estadoDe(modelo: Jarvis, id: String) = modelo.conexoes.value.firstOrNull { it.id == id }?.estado ?: ""

/** "Precisa do WhatsApp" se a de antes não está conectada; "" se pode. */
private fun faltaPara(modelo: Jarvis, c: InfoConexao): String {
    if (c.precisa.isEmpty()) return ""
    val e = estadoDe(modelo, c.precisa)
    return if (e == "conectado" || e == "pronto") "" else "Precisa do " + infoConexoes.first { it.id == c.precisa }.nome
}

/** O texto com **negrito** (os passos têm os nomes dos botões do WhatsApp em negrito). */
private fun negrito(texto: String) = buildAnnotatedString {
    texto.split("**").forEachIndexed { i, pedaco ->
        if (i % 2 == 1) withStyle(SpanStyle(color = Texto, fontWeight = FontWeight.SemiBold)) { append(pedaco) }
        else append(pedaco)
    }
}

@Composable
private fun BotaoDeConexao(texto: String, forte: Boolean = false, ativo: Boolean = true, aoTocar: () -> Unit) {
    Text(texto, color = if (forte) Color(0xFF06101D) else TextoMedio, fontSize = 13.5.sp,
        fontWeight = if (forte) FontWeight.SemiBold else FontWeight.Normal,
        modifier = Modifier.alpha(if (ativo) 1f else 0.4f).clip(RoundedCornerShape(9.dp))
            .then(if (forte) Modifier.background(Azul) else Modifier.border(1.dp, TracoForte, RoundedCornerShape(9.dp)))
            .clickable(enabled = ativo) { aoTocar() }.padding(horizontal = 14.dp, vertical = 8.dp))
}

/** Desconectar sem pop-up: o primeiro toque arma, o segundo (em até 4 s) faz. */
@Composable
private fun BotaoDesconectar(aoConfirmar: () -> Unit) {
    var armado by remember { mutableStateOf(false) }
    LaunchedEffect(armado) { if (armado) { delay(4000); armado = false } }
    Text(if (armado) "Toca de novo pra confirmar" else "Desconectar", color = Perigo, fontSize = 13.5.sp,
        modifier = Modifier.clip(RoundedCornerShape(9.dp))
            .background(if (armado) Perigo.copy(alpha = 0.12f) else Color.Transparent)
            .border(1.dp, Color(0xFF5C2A2C), RoundedCornerShape(9.dp))
            .clickable { if (armado) { armado = false; aoConfirmar() } else armado = true }
            .padding(horizontal = 14.dp, vertical = 8.dp))
}

/** Um passo do passo a passo: a bolinha (número, ✓ ou a de agora), o texto e o que mais precisar. */
@Composable
private fun PassoDaLista(numero: Int, titulo: String, dica: String = "", feito: Boolean = false, agora: Boolean = false,
                         extra: @Composable () -> Unit = {}) {
    Row(Modifier.fillMaxWidth().padding(vertical = 9.dp)) {
        Box(Modifier.size(26.dp).clip(CircleShape)
            .background(when { feito -> Verde.copy(alpha = 0.16f); agora -> Azul; else -> Superficie2 }),
            contentAlignment = Alignment.Center) {
            if (feito) Ic(Icones.certo, Verde, 14.dp)
            else Text("$numero", color = if (agora) Color(0xFF06101D) else Fraco, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f).padding(top = 3.dp)) {
            Text(negrito(titulo), color = if (feito) TextoMedio else Texto, fontSize = 14.sp, lineHeight = 20.sp)
            if (dica.isNotEmpty()) Text(dica, color = Fraco, fontSize = 12.5.sp, lineHeight = 18.sp, modifier = Modifier.padding(top = 2.dp))
            extra()
        }
    }
}

@Composable
private fun Espera(texto: String) {
    Row(Modifier.padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        CircularProgressIndicator(Modifier.size(13.dp), color = Azul, strokeWidth = 2.dp)
        Spacer(Modifier.width(8.dp))
        Text(texto, color = Fraco, fontSize = 13.sp)
    }
}

@Composable
private fun NotaDaConexao(texto: String) {
    Row(Modifier.fillMaxWidth().padding(top = 14.dp).clip(RoundedCornerShape(12.dp)).background(Superficie)
        .border(1.dp, Traco, RoundedCornerShape(12.dp)).padding(12.dp)) {
        Ic(Icones.sobre, Fraco, 17.dp)
        Spacer(Modifier.width(10.dp))
        Text(texto, color = Fraco, fontSize = 13.sp, lineHeight = 19.sp)
    }
}

@Composable
private fun CaixaDaConexao(conteudo: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(vertical = 10.dp).clip(RoundedCornerShape(14.dp)).background(Superficie)
        .border(1.dp, Traco, RoundedCornerShape(14.dp)).padding(18.dp),
        horizontalAlignment = Alignment.CenterHorizontally) { conteudo() }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun AjustesConexoes(modelo: Jarvis) {
    val estados = modelo.conexoes.value
    SecaoDosAjustes("Conexões da NOVA", if (estados.isEmpty()) "Aparece quando o PC responder."
        else "O que o Jarvis e a Friday conseguem usar no PC. Tudo começa desligado: liga só o que quiser.") {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            for (c in infoConexoes) {
                val estado = estadoDe(modelo, c.id)
                val falta = faltaPara(modelo, c)
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Superficie)
                    .border(1.dp, Traco, RoundedCornerShape(14.dp)).padding(14.dp)) {
                    Box(Modifier.size(38.dp).clip(RoundedCornerShape(11.dp)).background(Superficie2),
                        contentAlignment = Alignment.Center) { Ic(c.icone, TextoMedio, 18.dp) }
                    Spacer(Modifier.width(13.dp))
                    Column(Modifier.weight(1f)) {
                        Text(c.nome, color = Texto, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                        Text(c.descricao, color = Fraco, fontSize = 13.sp, modifier = Modifier.padding(top = 3.dp))
                        Row(Modifier.fillMaxWidth().padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                            EtiquetaDeEstado(estado)
                            Spacer(Modifier.weight(1f))
                            when {
                                // O cartão do Celular é este próprio celular: não tem o que conectar.
                                c.id == "celular" || estados.isEmpty() -> {}
                                falta.isNotEmpty() -> Text(falta, color = MuitoFraco, fontSize = 12.5.sp)
                                c.id == "atalhos" || (estado == "conectado" && c.id in listOf("relogio", "musica")) ->
                                    BotaoDeConexao("Como usar") { modelo.abrirPasso(c.id) }
                                estado == "conectado" || estado == "pronto" -> BotaoDeConexao("Gerenciar") { modelo.abrirPasso(c.id) }
                                else -> BotaoDeConexao("Conectar", forte = true) { modelo.abrirPasso(c.id) }
                            }
                        }
                    }
                }
            }
        }
    }
    val abrir = androidx.compose.ui.platform.LocalUriHandler.current
    SecaoDosAjustes("Da tua conta do Claude",
        "Gmail, Agenda, Drive e outros: liga no site do Claude e o Jarvis e a Friday já usam, aqui e no PC.") {
        val lista = modelo.conectores.value
        if (lista.isEmpty()) Text("Nenhum ligado ainda.", color = MuitoFraco, fontSize = 13.sp)
        else FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            for (nome in lista) Row(Modifier.clip(RoundedCornerShape(16.dp)).background(Superficie)
                .border(1.dp, Traco, RoundedCornerShape(16.dp)).padding(horizontal = 11.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(7.dp).clip(CircleShape).background(Verde))
                Spacer(Modifier.width(7.dp))
                Text(nome, color = TextoMedio, fontSize = 13.sp)
            }
        }
        Spacer(Modifier.height(12.dp))
        BotaoDeConexao("Adicionar no claude.ai") { abrir.openUri("https://claude.ai/settings/connectors") }
    }
}

/** O passo a passo de uma conexão (o Conectar ou o Gerenciar de um cartão). */
@Composable
private fun PassoDaConexao(modelo: Jarvis) {
    val id = modelo.passoConexao.value
    val info = infoConexoes.first { it.id == id }
    // O estado de agora, de 2 em 2 s; o Fora de casa repete o "conectar" para ligar o
    // acesso sozinho quando o celular aparecer na conta (o mesmo da janela).
    if (id != "relogio" && id != "atalhos") LaunchedEffect(id) {
        while (true) { delay(2000); modelo.pedirConexao(id, if (id == "fora") "conectar" else "estado") }
    }
    val e = modelo.estadoPasso.value
    val estado = e.optString("estado").ifEmpty { estadoDe(modelo, id) }
    Row(Modifier.padding(top = 10.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(38.dp).clip(RoundedCornerShape(11.dp)).background(Superficie2),
            contentAlignment = Alignment.Center) { Ic(info.icone, Azul, 18.dp) }
        Spacer(Modifier.width(12.dp))
        Text(info.nome, color = Texto, fontSize = 18.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
        EtiquetaDeEstado(if (id == "atalhos") "conectado" else if (estado in listOf("conectado", "pronto")) estado else "desligado")
    }
    val detalhe = e.optString("detalhe")
    if (estado == "falta" || estado == "erro") {
        Text(detalhe, color = Pergunta, fontSize = 14.sp, modifier = Modifier.padding(top = 10.dp))
        return
    }
    when (id) {
        "whatsapp" -> PassoWhatsapp(modelo, e, estado)
        "grupo" -> PassoGrupo(modelo, e)
        "fora" -> PassoFora(e, estado)
        "relogio" -> {
            val celular = estadoDe(modelo, "celular") == "conectado"
            PassoDaLista(1, "Celular conectado", feito = celular)
            PassoDaLista(2, "Instalar o NOVA no relógio", agora = celular,
                dica = "Por enquanto é pela depuração sem fio do relógio: o Léo te ajuda nesse passo.")
            PassoDaLista(3, "Abre o NOVA no relógio e toca no átomo", feito = estadoDe(modelo, "relogio") == "conectado",
                dica = "O cartão vira \"Conectado\" quando ele aparecer.")
            NotaDaConexao("Funciona com relógio Wear OS (Galaxy Watch e parecidos), sempre por este celular.")
        }
        "musica" -> {
            val feito = estado == "conectado"
            PassoDaLista(1, if (feito) "O programa que toca o som (o mpv) está instalado no PC"
                else "Falta o programa que toca o som (o mpv). Roda isto no terminal do PC:", feito = feito, agora = !feito,
                dica = if (feito) "" else "Pede a tua senha do PC. A NOVA não roda nada como administrador sozinha.") {
                if (!feito) Text(e.optString("comando", "sudo apt install mpv mpv-mpris"), color = Texto, fontSize = 13.sp,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.padding(top = 8.dp).fillMaxWidth().clip(RoundedCornerShape(9.dp)).background(Superficie)
                        .border(1.dp, Traco, RoundedCornerShape(9.dp)).padding(horizontal = 12.dp, vertical = 10.dp))
            }
            PassoDaLista(2, if (feito) "Pede: **\"Jarvis, toca uma música\"**" else "Volta aqui: o cartão vira \"Conectado\" sozinho",
                agora = feito)
        }
        else -> {
            PassoDaLista(1, "Pede: **\"Jarvis, cria um atalho pro Discord\"**", dica = "Vale programa, pasta ou site.")
            PassoDaLista(2, "Depois é só falar: **\"abre o Discord\"**")
            NotaDaConexao("Os atalhos ficam no PC.")
        }
    }
}

/** No app, o WhatsApp vai pelo código de 8 letras do "Conectar com número de telefone":
 *  o próprio celular não lê o QR da tela dele. */
@Composable
private fun PassoWhatsapp(modelo: Jarvis, e: org.json.JSONObject, estado: String) {
    var numero by remember { mutableStateOf("") }
    var pediu by remember { mutableStateOf(false) }
    var invalido by remember { mutableStateOf(false) }
    val codigo = e.optString("codigo")
    val erroCodigo = e.optString("erro_codigo")
    if (estado == "conectado" || estado == "pronto") {
        Text("Conectado. O Jarvis e a Friday leem as mensagens do PC e avisam quem te escreveu.",
            color = TextoMedio, fontSize = 14.sp, lineHeight = 20.sp, modifier = Modifier.padding(vertical = 10.dp))
        BotaoDesconectar { modelo.pedirConexao("whatsapp", "desconectar") }
        NotaDaConexao("As mensagens ficam só no PC. Mandar sempre pede o teu \"pode\" falado.")
        return
    }
    if (codigo.isNotEmpty() || (pediu && estado in listOf("esperando", "abrindo"))) {
        CaixaDaConexao {
            when {
                codigo.isNotEmpty() -> {
                    Text(codigo.chunked(4).joinToString("-"), color = Texto, fontSize = 30.sp, letterSpacing = 3.sp,
                        fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold)
                    Espera("esperando o WhatsApp…")
                }
                erroCodigo.isNotEmpty() -> {
                    Text("O WhatsApp não aceitou esse número. Confere o DDD e tenta de novo.", color = Pergunta,
                        fontSize = 14.sp, textAlign = TextAlign.Center)
                    Spacer(Modifier.height(10.dp))
                    BotaoDeConexao("Tentar de novo") { pediu = false }
                }
                else -> Espera("pedindo o código ao WhatsApp…")
            }
        }
        PassoDaLista(1, "Abre o WhatsApp → **Aparelhos conectados** → **Conectar um aparelho**", agora = true,
            dica = "Android: os três pontinhos. iPhone: Configurações.")
        PassoDaLista(2, "Toca em **Conectar com número de telefone**")
        PassoDaLista(3, "Digita o código acima", dica = "Pronto: o cartão vira \"Conectado\" sozinho.")
        NotaDaConexao("As mensagens ficam só no PC. Mandar sempre pede o teu \"pode\" falado.")
        return
    }
    if (estado == "expirou") Text("O código expirou. Pede outro.", color = Pergunta, fontSize = 14.sp,
        modifier = Modifier.padding(top = 10.dp))
    Text("O teu número do WhatsApp", color = Texto, fontSize = 14.sp, modifier = Modifier.padding(top = 12.dp))
    Text("Com o DDD. O WhatsApp manda um código de 8 letras para ligar o PC à tua conta.", color = Fraco,
        fontSize = 12.5.sp, modifier = Modifier.padding(top = 2.dp, bottom = 10.dp))
    Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(9.dp)).background(Superficie)
        .border(1.dp, if (invalido) Perigo else Traco, RoundedCornerShape(9.dp)).padding(horizontal = 12.dp, vertical = 11.dp)) {
        if (numero.isEmpty()) Text("48 99999-9999", color = MuitoFraco, fontSize = 15.sp)
        BasicTextField(numero, { numero = it.take(20); invalido = false }, singleLine = true,
            textStyle = TextStyle(color = Texto, fontSize = 15.sp, fontFamily = Inter), cursorBrush = SolidColor(Azul),
            keyboardOptions = KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Phone),
            modifier = Modifier.fillMaxWidth())
    }
    if (invalido) Text("Esse número está curto. Põe o DDD junto.", color = Perigo, fontSize = 12.5.sp,
        modifier = Modifier.padding(top = 4.dp))
    Spacer(Modifier.height(12.dp))
    BotaoDeConexao("Pedir o código", forte = true, ativo = modelo.conectado.value) {
        // Com DDD e sem o país, é do Brasil: o WhatsApp quer o 55 na frente.
        val digitos = numero.filter { it.isDigit() }.let { if (it.length in 10..11) "55$it" else it }
        if (digitos.length < 12) invalido = true
        else { pediu = true; modelo.pedirConexao("whatsapp", "conectar", digitos) }
    }
    NotaDaConexao("As mensagens ficam só no PC. Mandar sempre pede o teu \"pode\" falado.")
}

@Composable
private fun PassoGrupo(modelo: Jarvis, e: org.json.JSONObject) {
    val escolhido = e.optString("escolhido")
    val ligado = e.optBoolean("ligado")
    val grupos = e.optJSONArray("grupos")
    LinhaDeAjuste("Responder no grupo", if (escolhido.isEmpty()) "Escolhe um grupo primeiro." else "Liga e desliga quando quiser.",
        ultima = true) {
        Switch(checked = ligado, enabled = escolhido.isNotEmpty(), onCheckedChange = { modelo.ligarGrupo(it) },
            colors = SwitchDefaults.colors(checkedTrackColor = Azul, checkedThumbColor = Color.White,
                uncheckedTrackColor = Superficie2, uncheckedThumbColor = Fraco, uncheckedBorderColor = TracoForte))
    }
    Text("Escolhe o grupo onde o Jarvis responde quando alguém escreve \"Jarvis, …\".", color = Fraco, fontSize = 13.sp,
        modifier = Modifier.padding(top = 8.dp, bottom = 8.dp))
    if (grupos == null) { Espera("procurando os teus grupos…"); return }
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Superficie)
        .border(1.dp, Traco, RoundedCornerShape(14.dp))) {
        for (i in 0 until grupos.length()) {
            val g = grupos.optJSONObject(i) ?: continue
            val jid = g.optString("jid")
            val sim = jid == escolhido
            if (i > 0) Box(Modifier.fillMaxWidth().height(1.dp).background(Traco))
            Row(Modifier.fillMaxWidth().clickable(enabled = !sim) { modelo.pedirConexao("grupo", "escolher", jid) }
                .padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(18.dp).clip(CircleShape).border(2.dp, if (sim) Azul else TracoForte, CircleShape),
                    contentAlignment = Alignment.Center) {
                    if (sim) Box(Modifier.size(8.dp).clip(CircleShape).background(Azul))
                }
                Spacer(Modifier.width(12.dp))
                Text(g.optString("nome"), color = if (sim) Texto else TextoMedio, fontSize = 14.sp, maxLines = 1,
                    overflow = TextOverflow.Ellipsis)
            }
        }
    }
    if (escolhido.isNotEmpty()) {
        Spacer(Modifier.height(12.dp))
        BotaoDesconectar { modelo.pedirConexao("grupo", "desconectar") }
    }
    NotaDaConexao("No grupo ele conversa, pesquisa e anota recados. O que mexe nas tuas coisas (arquivos, mensagens, " +
        "o PC) só acontece com o teu Sim neste celular.")
}

@Composable
private fun PassoFora(e: org.json.JSONObject, estado: String) {
    val contexto = LocalContext.current
    val noPc = e.optBoolean("instalado") && e.optString("conta").isNotEmpty()
    val aqui = remember(e) { contexto.packageManager.getLaunchIntentForPackage(TAILSCALE) != null }
    val celular = e.optString("celular")
    val servindo = e.optBoolean("servindo")
    if (estado == "conectado") Text("Conectado: este celular alcança o PC em casa ou na rua.", color = TextoMedio,
        fontSize = 14.sp, modifier = Modifier.padding(vertical = 10.dp))
    else Text("O Tailscale é um app grátis que liga este celular ao PC, em casa ou na rua, sem abrir nada para a internet.",
        color = Fraco, fontSize = 13.sp, lineHeight = 19.sp, modifier = Modifier.padding(vertical = 10.dp))
    PassoDaLista(1, "Tailscale no PC", feito = noPc, agora = !noPc,
        dica = if (noPc) "Ligado na conta ${e.optString("conta")}." else "Esse passo é na janela do PC: Ajustes → Conexões → Fora de casa.")
    PassoDaLista(2, "Instala o Tailscale neste celular", feito = aqui, agora = noPc && !aqui) {
        if (!aqui) Box(Modifier.padding(top = 8.dp)) {
            BotaoDeConexao("Abrir a Play Store", forte = noPc) {
                val loja = Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$TAILSCALE"))
                runCatching { contexto.startActivity(loja) }.onFailure {
                    contexto.startActivity(Intent(Intent.ACTION_VIEW,
                        Uri.parse("https://play.google.com/store/apps/details?id=$TAILSCALE")))
                }
            }
        }
    }
    PassoDaLista(3, "Entra com a **mesma conta** do PC", feito = celular.isNotEmpty(), agora = aqui && celular.isEmpty(),
        dica = if (celular.isNotEmpty()) "Achei: $celular." else "") {
        if (aqui && celular.isEmpty()) Box(Modifier.padding(top = 8.dp)) {
            BotaoDeConexao("Abrir o Tailscale") {
                contexto.packageManager.getLaunchIntentForPackage(TAILSCALE)?.let { contexto.startActivity(it) }
            }
        }
    }
    PassoDaLista(4, "Volta aqui: a NOVA confere e liga sozinha", feito = servindo, agora = celular.isNotEmpty() && !servindo,
        dica = e.optString("detalhe"))
}

@Composable
private fun AjustesSobre(modelo: Jarvis) {
    val contexto = LocalContext.current
    val versaoDoApp = remember {
        runCatching { contexto.packageManager.getPackageInfo(contexto.packageName, 0).versionName }.getOrNull() ?: "—"
    }
    SecaoDosAjustes("Sobre a NOVA") {
        val linhas = listOf(
            "Versão" to versaoDoApp,
            "Conexão" to (if (modelo.conectado.value) "Ligado" else modelo.motivo.value),
        )
        linhas.forEachIndexed { i, (rotulo, valor) ->
            LinhaDeAjuste(rotulo, ultima = i == linhas.lastIndex) { Text(valor, color = TextoMedio, fontSize = 14.sp) }
        }
        Text(buildAnnotatedString {
            append("A NOVA é uma assistente que mora no teu PC e conversa contigo por voz, pela janela, " +
                "pelo celular e pelo relógio. Ela tem duas personas: o ")
            withStyle(SpanStyle(color = Texto, fontWeight = FontWeight.SemiBold)) { append("Jarvis") }
            append(", mais sério e direto, e a ")
            withStyle(SpanStyle(color = Texto, fontWeight = FontWeight.SemiBold)) { append("Friday") }
            append(", mais carinhosa e animada. Você escolhe com quem quer falar, e os dois conhecem a tua " +
                "rotina, lembram das tuas coisas e cuidam do que você pedir.")
        }, color = TextoMedio, fontSize = 14.sp, lineHeight = 21.sp, modifier = Modifier.padding(top = 14.dp))
    }
}

@Composable
private fun BarraDeUso(nome: String, uso: Double, volta: Double, comDia: Boolean) {
    if (uso < 0) return
    val cor = if (uso >= 0.9) Perigo else if (uso >= 0.7) Pergunta else Azul
    val renova = if (volta <= 0) "" else {
        val c = Calendar.getInstance().apply { timeInMillis = (volta * 1000).toLong() }
        val h = "%02d:%02d".format(c.get(Calendar.HOUR_OF_DAY), c.get(Calendar.MINUTE))
        if (!comDia) "renova às $h" else {
            val dias = listOf("dom", "seg", "ter", "qua", "qui", "sex", "sáb")
            "renova ${dias[c.get(Calendar.DAY_OF_WEEK) - 1]} ${c.get(Calendar.DAY_OF_MONTH)}/${c.get(Calendar.MONTH) + 1}, $h"
        }
    }
    Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
        Row {
            Text(nome, color = TextoMedio, fontSize = 14.sp)
            Spacer(Modifier.weight(1f))
            Text("${(uso * 100).toInt()}%", color = Texto, fontSize = 14.sp)
        }
        Box(Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(4.dp)).background(Superficie2)) {
            Box(Modifier.fillMaxWidth(uso.toFloat().coerceIn(0.03f, 1f)).height(8.dp).clip(RoundedCornerShape(4.dp)).background(cor))
        }
        Text(renova, color = Fraco, fontSize = 12.sp)
    }
}
