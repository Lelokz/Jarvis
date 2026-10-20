package com.lelokz.jarvis

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat

private val Fundo = Color(0xFF0A0C10)
private val Texto = Color(0xFFE6EBF2)
private val Fraco = Color(0xFF7E879B)

private fun corDoEstado(estado: String) = when (estado) {
    "pronto" -> Color(0xFF4DA3FF)
    "escutando" -> Color(0xFF38D39F)
    "pensando" -> Color(0xFF9B7BFF)
    "falando" -> Color(0xFFFFB454)
    else -> Color(0xFF39435A)
}

/**
 * A tela do relógio: o átomo no meio, uma linha curta em cima (o que ele está
 * fazendo) e, embaixo, o que você disse e a resposta (rola com o dedo).
 * Abrir o app (o botão duplo) já começa a ouvir.
 */
class MainActivity : ComponentActivity() {
    private val relogio get() = (application as App).relogio

    private val pedirMicrofone = registerForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) relogio.ouvir()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { Tela(relogio, ::falar, ::telaAcesa) }
        if (savedInstanceState == null) falar()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        falar() // o botão apertado de novo com o app já aberto
    }

    override fun onStart() {
        super.onStart()
        relogio.aparecer()
    }

    override fun onStop() {
        relogio.sumir()
        super.onStop()
    }

    private fun falar() {
        val temPermissao = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        if (temPermissao) relogio.ouvir() else pedirMicrofone.launch(Manifest.permission.RECORD_AUDIO)
    }

    /** Ouvindo, pensando ou falando: a tela não apaga no meio. */
    private fun telaAcesa(acesa: Boolean) {
        if (acesa) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }
}

@Composable
private fun Tela(r: Relogio, falar: () -> Unit, telaAcesa: (Boolean) -> Unit) {
    val estado = r.estadoVisivel
    val vivo = r.ligado.value
    val ocupado = r.ocupado
    LaunchedEffect(ocupado) { telaAcesa(ocupado) }

    val linha = when {
        !vivo -> r.motivo.value
        r.ouvindo.value -> "ouvindo…"
        r.atividade.value.isNotBlank() -> r.atividade.value
        estado == "pensando" -> "pensando…"
        else -> "JARVIS"
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(Fundo)
            .verticalScroll(rememberScrollState())
            .padding(start = 24.dp, end = 24.dp, top = 22.dp, bottom = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Top,
    ) {
        BasicText(
            linha,
            style = TextStyle(color = Fraco, fontSize = 12.sp, textAlign = TextAlign.Center,
                letterSpacing = if (linha == "JARVIS") 3.sp else 0.sp),
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(4.dp))
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
            turbulencia = when (estado) {
                "pensando" -> 1f; "escutando" -> 0.35f; "falando" -> 0.25f; else -> 0f
            },
            nivel = r.nivel.floatValue,
            parado = !vivo,
            pulsando = estado == "pronto",
            fundo = Fundo,
            modifier = Modifier
                .size(112.dp)
                .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) {
                    if (!r.ouvindo.value && !r.tocando.value && vivo) falar() else r.tocou()
                },
        )
        if (r.voceDisse.value.isNotBlank()) {
            Spacer(Modifier.height(6.dp))
            BasicText(r.voceDisse.value,
                style = TextStyle(color = Fraco, fontSize = 12.sp, textAlign = TextAlign.Center))
        }
        if (r.resposta.value.isNotBlank()) {
            Spacer(Modifier.height(6.dp))
            BasicText(r.resposta.value,
                style = TextStyle(color = Texto, fontSize = 14.sp, textAlign = TextAlign.Center))
        }
    }
}
