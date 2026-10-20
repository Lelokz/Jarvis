package com.lelokz.jarvis

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel

private val Fundo = Color(0xFF0B1016)
private val Painel = Color(0xFF121A23)
private val Borda = Color(0xFF1F2B38)
private val Texto = Color(0xFFE6EDF3)
private val Fraco = Color(0xFF8B98A5)
private val BalaoJarvis = Color(0xFF16324A)
private val BalaoVoce = Color(0xFF1D2A36)
private val Destaque = Color(0xFF4FB3FF)
private val Erro = Color(0xFFFF7B72)

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
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Jarvis", color = Texto, fontSize = 28.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(8.dp))
        Text("Cola o link do Jarvis (o mesmo da página, com a chave). No PC: porta_remota.py --endereco",
            color = Fraco, fontSize = 14.sp)
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(
            value = link, onValueChange = { link = it; erro = false },
            modifier = Modifier.fillMaxWidth(), singleLine = true,
            placeholder = { Text("https://jarvis…ts.net/#chave=…") },
            isError = erro, colors = camposEscuros(),
        )
        if (erro) Text("Esse link não tem a chave.", color = Erro, fontSize = 13.sp)
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = { erro = !modelo.configurar(link) },
            colors = ButtonDefaults.buttonColors(containerColor = Destaque, contentColor = Fundo),
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Entrar") }
    }
}

@Composable
fun Conversa(modelo: JarvisModelo) {
    val contexto = androidx.compose.ui.platform.LocalContext.current
    var texto by remember { mutableStateOf("") }
    val lista = rememberLazyListState()
    val pedirMicrofone = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}

    LaunchedEffect(modelo.mensagens.size) {
        if (modelo.mensagens.isNotEmpty()) lista.animateScrollToItem(modelo.mensagens.lastIndex)
    }

    Column(Modifier.fillMaxSize().imePadding()) {
        // Topo: nome e o que ele está fazendo. Segurar o nome = trocar o link.
        Row(
            Modifier.fillMaxWidth().background(Painel).padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Jarvis", color = Texto, fontSize = 20.sp, fontWeight = FontWeight.SemiBold,
                modifier = Modifier.pointerInput(Unit) {
                    detectTapGestures(onLongPress = { modelo.esquecer() })
                })
            Spacer(Modifier.weight(1f))
            val cor = when {
                !modelo.conectado.value -> Erro
                modelo.estado.value == "pronto" -> Color(0xFF3FB950)
                else -> Destaque
            }
            Box(Modifier.size(9.dp).clip(CircleShape).background(cor))
            Spacer(Modifier.size(6.dp))
            Text(modelo.estado.value, color = Fraco, fontSize = 13.sp)
        }

        LazyColumn(
            state = lista,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            itemsIndexed(modelo.mensagens) { _, m -> Balao(m) }
        }

        Row(
            Modifier.fillMaxWidth().background(Painel).padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = texto, onValueChange = { texto = it },
                modifier = Modifier.weight(1f), singleLine = true,
                placeholder = { Text("Escreve pro Jarvis…") },
                shape = RoundedCornerShape(22.dp), colors = camposEscuros(),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(onSend = { modelo.enviarTexto(texto); texto = "" }),
            )
            Spacer(Modifier.size(8.dp))
            if (texto.isNotBlank()) {
                Button(
                    onClick = { modelo.enviarTexto(texto); texto = "" },
                    colors = ButtonDefaults.buttonColors(containerColor = BalaoJarvis, contentColor = Texto),
                    shape = CircleShape,
                ) { Text("➤") }
            } else {
                // Segurar para falar: grava enquanto o dedo está em cima.
                val gravando = modelo.gravando.value
                Box(
                    Modifier
                        .size(56.dp)
                        .clip(CircleShape)
                        .background(if (gravando) Erro else Destaque)
                        .pointerInput(Unit) {
                            detectTapGestures(onPress = {
                                val temPermissao = ContextCompat.checkSelfPermission(
                                    contexto, Manifest.permission.RECORD_AUDIO) ==
                                    PackageManager.PERMISSION_GRANTED
                                if (!temPermissao) {
                                    pedirMicrofone.launch(Manifest.permission.RECORD_AUDIO)
                                    return@detectTapGestures
                                }
                                modelo.comecarFala()
                                tryAwaitRelease()
                                modelo.terminarFala()
                            })
                        },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(if (gravando) "Solta" else "Falar", color = Fundo,
                        fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                }
            }
        }
    }
}

@Composable
fun Balao(m: Mensagem) {
    when (m.quem) {
        Quem.ATIVIDADE, Quem.AVISO -> Text(
            m.texto, color = if (m.quem == Quem.AVISO) Erro else Fraco, fontSize = 12.sp,
            textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth(),
        )
        Quem.PAINEL -> Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(Painel)
                .border(1.dp, Borda, RoundedCornerShape(10.dp)).padding(12.dp),
        ) {
            if (m.titulo.isNotEmpty()) {
                Text(m.titulo, color = Texto, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                Spacer(Modifier.height(4.dp))
            }
            Text(m.texto, color = Texto, fontSize = 13.sp, fontFamily = FontFamily.Monospace)
        }
        Quem.VOCE, Quem.JARVIS -> {
            val voce = m.quem == Quem.VOCE
            Box(Modifier.fillMaxWidth(), contentAlignment = if (voce) Alignment.CenterEnd else Alignment.CenterStart) {
                Text(
                    m.texto, color = Texto, fontSize = 16.sp,
                    modifier = Modifier
                        .widthIn(max = 300.dp)
                        .clip(RoundedCornerShape(14.dp))
                        .background(if (voce) BalaoVoce else BalaoJarvis)
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                )
            }
        }
    }
}

@Composable
private fun camposEscuros() = OutlinedTextFieldDefaults.colors(
    focusedTextColor = Texto, unfocusedTextColor = Texto,
    focusedBorderColor = Destaque, unfocusedBorderColor = Borda,
    focusedContainerColor = Fundo, unfocusedContainerColor = Fundo,
    focusedPlaceholderColor = Fraco, unfocusedPlaceholderColor = Fraco,
    cursorColor = Destaque,
)
