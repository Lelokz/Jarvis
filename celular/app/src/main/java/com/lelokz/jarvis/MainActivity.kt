package com.lelokz.jarvis

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel

// As cores da janela do PC (jarvis/interface/qml/Tema.qml).
private val Fundo = Color(0xFF0A0C10)
private val Superficie = Color(0xFF11151C)
private val Traco = Color(0xFF1C2431)
private val Texto = Color(0xFFE6EBF2)
private val Fraco = Color(0xFF7E879B)
private val Perigo = Color(0xFFFF6B6B)
private val Pergunta = Color(0xFFFFB454)

/** Uma cor por estado, as mesmas do PC: dá para saber o que ele faz sem ler. */
private fun corDoEstado(e: String) = when (e) {
    "pronto" -> Color(0xFF4DA3FF)
    "escutando" -> Color(0xFF38D39F)
    "pensando" -> Color(0xFF9B7BFF)
    "falando" -> Color(0xFFFFB454)
    else -> Color(0xFF39435A)
}

private fun rotuloDoEstado(e: String) = when (e) {
    "pronto" -> "SEGURA PRA FALAR"
    "escutando" -> "ESCUTANDO VOCÊ"
    "pensando" -> "PENSANDO"
    "falando" -> "FALANDO"
    else -> "SEM CONEXÃO"
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(background = Fundo, surface = Fundo)) {
                val modelo: JarvisModelo = viewModel()
                Box(Modifier.fillMaxSize().background(Fundo).safeDrawingPadding()) {
                    if (modelo.configurado.value) Conversa(modelo) else Entrada(modelo)
                }
            }
        }
    }
}

/** A primeira vez: colar o link da página, que já traz a chave. */
@Composable
fun Entrada(modelo: JarvisModelo) {
    var link by remember { mutableStateOf("") }
    var erro by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text("JARVIS", color = Texto, fontSize = 22.sp, fontWeight = FontWeight.Bold, letterSpacing = 4.sp)
        Spacer(Modifier.height(8.dp))
        Text("Cola o link do Jarvis (o mesmo da página, com a chave).", color = Fraco, fontSize = 14.sp)
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(
            value = link, onValueChange = { link = it; erro = false },
            modifier = Modifier.fillMaxWidth(), singleLine = true,
            placeholder = { Text("https://jarvis…ts.net/#chave=…") }, isError = erro,
            colors = OutlinedTextFieldDefaults.colors(
                focusedTextColor = Texto, unfocusedTextColor = Texto,
                focusedBorderColor = Color(0xFF4DA3FF), unfocusedBorderColor = Traco,
                cursorColor = Color(0xFF4DA3FF)),
        )
        if (erro) Text("Esse link não tem a chave.", color = Perigo, fontSize = 13.sp)
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = { erro = !modelo.configurar(link) },
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4DA3FF), contentColor = Fundo),
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Entrar") }
    }
}

@Composable
fun Conversa(modelo: JarvisModelo) {
    val contexto = LocalContext.current
    val vibrar = LocalHapticFeedback.current
    var texto by remember { mutableStateOf("") }
    val lista = rememberLazyListState()
    val pedirMicrofone = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
    val escolherArquivos = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        uris.take(10).forEach { modelo.anexar(it) }
    }
    val estado = modelo.estadoVisivel
    val cor = corDoEstado(estado)
    val vivo = modelo.conectado.value

    LaunchedEffect(modelo.mensagens.size) {
        if (modelo.mensagens.isNotEmpty()) lista.animateScrollToItem(modelo.mensagens.lastIndex)
    }

    fun enviar() {
        if (texto.isBlank() && modelo.anexos.isEmpty()) return
        if (!modelo.anexosProntos) return
        modelo.enviarTexto(texto)
        texto = ""
    }

    Column(Modifier.fillMaxSize().imePadding()) {
        // Topo. Segurar o nome = trocar o link.
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("JARVIS", color = Texto, fontSize = 15.sp, fontWeight = FontWeight.Bold,
                letterSpacing = 4.sp,
                modifier = Modifier.pointerInput(Unit) { detectTapGestures(onLongPress = { modelo.esquecer() }) })
            Spacer(Modifier.weight(1f))
            if (!vivo) Text(modelo.motivo.value, color = Fraco, fontSize = 12.sp)
            Spacer(Modifier.width(8.dp))
            // O mudo: alto-falante, e com um risco no meio quando mudo.
            Box(
                Modifier.size(40.dp).clip(CircleShape).clickable { modelo.alternarMudo() },
                contentAlignment = Alignment.Center,
            ) { AltoFalante(mudo = modelo.mudo.value, cor = if (modelo.mudo.value) Perigo else Texto) }
        }

        LazyColumn(
            state = lista,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            itemsIndexed(modelo.mensagens) { _, m -> Balao(m) }
        }

        // O átomo: centralizado embaixo, e é o botão de falar (segura e fala).
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
            Atomo(
                cor = cor,
                escala = when (estado) {
                    "sem_conexao" -> 0.80f; "escutando" -> 1.14f; "falando" -> 1.06f
                    "pensando" -> 1.02f; else -> 0.92f
                },
                velocidade = when (estado) {
                    "sem_conexao" -> 0f; "pensando" -> 2.2f; "falando" -> 1.25f
                    "escutando" -> 1.15f; else -> 0.6f
                },
                brilho = when (estado) { "sem_conexao" -> 0.28f; "pensando" -> 1.2f; "pronto" -> 0.8f; else -> 1f },
                turbulencia = when (estado) {
                    "pensando" -> 1f; "escutando" -> 0.35f; "falando" -> 0.25f; else -> 0f
                },
                nivel = modelo.nivel.floatValue,
                parado = !vivo,
                pulsando = estado == "pronto",
                fundo = Fundo,
                modifier = Modifier
                    .size(150.dp)
                    .pointerInput(vivo) {
                        detectTapGestures(onPress = {
                            if (!vivo) return@detectTapGestures
                            val temPermissao = ContextCompat.checkSelfPermission(
                                contexto, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
                            if (!temPermissao) {
                                pedirMicrofone.launch(Manifest.permission.RECORD_AUDIO)
                                return@detectTapGestures
                            }
                            vibrar.performHapticFeedback(HapticFeedbackType.LongPress)
                            modelo.comecarFala()
                            tryAwaitRelease()
                            modelo.terminarFala()
                        })
                    },
            )
            Text(rotuloDoEstado(estado), color = cor, fontSize = 11.sp, letterSpacing = 2.sp,
                fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(10.dp))
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

        // O campo de escrever e, à direita, o clipe.
        Row(
            Modifier.fillMaxWidth().padding(start = 12.dp, end = 12.dp, bottom = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Row(
                Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape(22.dp))
                    .background(Superficie)
                    .border(1.dp, Traco, RoundedCornerShape(22.dp))
                    .padding(start = 16.dp, end = 6.dp, top = 4.dp, bottom = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(Modifier.weight(1f).padding(vertical = 8.dp)) {
                    if (texto.isEmpty()) Text("Escreve pro Jarvis…", color = Fraco, fontSize = 15.sp)
                    BasicTextField(
                        value = texto, onValueChange = { texto = it },
                        textStyle = TextStyle(color = Texto, fontSize = 15.sp),
                        cursorBrush = SolidColor(cor), maxLines = 5,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                        keyboardActions = KeyboardActions(onSend = { enviar() }),
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                if (texto.isNotBlank() || modelo.anexos.isNotEmpty()) {
                    val pronto = modelo.anexosProntos
                    Box(
                        Modifier.size(36.dp).clip(CircleShape)
                            .background(if (pronto) cor else Traco)
                            .clickable(enabled = pronto) { enviar() },
                        contentAlignment = Alignment.Center,
                    ) { Text("➤", color = Fundo, fontSize = 15.sp) }
                }
            }
            Spacer(Modifier.width(8.dp))
            Box(
                Modifier.size(44.dp).clip(CircleShape).background(Superficie)
                    .border(1.dp, Traco, CircleShape)
                    .clickable { escolherArquivos.launch("*/*") },
                contentAlignment = Alignment.Center,
            ) { Text("📎", fontSize = 18.sp) }
        }
    }
}

@Composable
private fun AltoFalante(mudo: Boolean, cor: Color) {
    Canvas(Modifier.size(22.dp)) {
        val w = size.width
        val h = size.height
        // A caixa e o cone do alto-falante.
        val corpo = Path().apply {
            moveTo(w * 0.10f, h * 0.38f); lineTo(w * 0.28f, h * 0.38f)
            lineTo(w * 0.52f, h * 0.16f); lineTo(w * 0.52f, h * 0.84f)
            lineTo(w * 0.28f, h * 0.62f); lineTo(w * 0.10f, h * 0.62f); close()
        }
        drawPath(corpo, cor)
        val traco = Stroke(width = w * 0.08f, cap = StrokeCap.Round)
        if (mudo) {
            // O risco no meio.
            drawLine(cor, Offset(w * 0.06f, h * 0.10f), Offset(w * 0.94f, h * 0.90f),
                strokeWidth = w * 0.09f, cap = StrokeCap.Round)
        } else {
            // As ondas do som.
            drawArc(cor, -45f, 90f, false, Offset(w * 0.40f, h * 0.30f), Size(w * 0.30f, h * 0.40f), style = traco)
            drawArc(cor, -50f, 100f, false, Offset(w * 0.40f, h * 0.14f), Size(w * 0.52f, h * 0.72f), style = traco)
        }
    }
}

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
                Text("📄", fontSize = 18.sp)
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
            Text("✕", color = Fraco, fontSize = 14.sp)
        }
    }
}

@Composable
fun Balao(m: Mensagem) {
    when (m.quem) {
        Quem.ATIVIDADE -> Text(
            "▸ " + m.texto, color = Fraco, fontSize = 11.sp, letterSpacing = 0.5.sp,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp),
        )
        Quem.AVISO -> Text(
            m.texto, color = Perigo, fontSize = 12.sp, textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
        )
        Quem.PAINEL -> Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(Superficie)
                .border(1.dp, Traco, RoundedCornerShape(10.dp)).padding(14.dp),
        ) {
            if (m.titulo.isNotEmpty()) {
                Text(m.titulo.uppercase(), color = Fraco, fontSize = 10.sp, letterSpacing = 1.2.sp,
                    fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
            }
            Text(m.texto, color = Texto, fontSize = 13.sp, fontFamily = FontFamily.Monospace)
        }
        Quem.VOCE, Quem.JARVIS -> {
            val voce = m.quem == Quem.VOCE
            Box(Modifier.fillMaxWidth(), contentAlignment = if (voce) Alignment.CenterEnd else Alignment.CenterStart) {
                val forma = RoundedCornerShape(14.dp)
                Column(
                    Modifier
                        .widthIn(max = 300.dp)
                        .clip(forma)
                        .then(if (voce) Modifier.background(Superficie)
                              else Modifier.border(1.dp, if (m.perguntando) Pergunta else Traco, forma))
                        .padding(horizontal = 14.dp, vertical = 9.dp),
                ) {
                    for (n in m.anexos) Text("📎 $n", color = Fraco, fontSize = 12.sp, maxLines = 1,
                        overflow = TextOverflow.Ellipsis)
                    Text(m.texto, color = Texto, fontSize = 15.sp)
                }
            }
        }
    }
}
