package com.lelokz.jarvis

import android.Manifest
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
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

private val Cinza = Color(0xFF39435A)
private val Dormindo = Color(0xFF6B7488)
private val CorDoJarvis = Color(0xFF4DA3FF)
private val CorDaFriday = Color(0xFFFF6FB5)

private fun corDoEstado(estado: String) = when (estado) {
    "dormindo" -> Dormindo
    "escutando" -> Color(0xFF38D39F)
    "pensando" -> Color(0xFF9B7BFF)
    "falando" -> Color(0xFFFFB454)
    else -> Cinza
}

/** A cor de quem responde: o azul do Jarvis, ou a cor da Friday que veio do PC. */
private fun corDaPersona(r: Relogio): Color {
    if (r.persona.value != "friday") return CorDoJarvis
    return runCatching { Color(android.graphics.Color.parseColor(r.corPersona.value)) }.getOrDefault(CorDaFriday)
}

/**
 * A tela do relógio: em cima, quem responde (JARVIS ou FRIDAY, toque troca);
 * o átomo no meio (toque: ouve, manda, para); embaixo, o que ele está fazendo
 * e a conversa. O app abre dormindo: não ouve sem o toque.
 */
class MainActivity : ComponentActivity() {
    private val relogio get() = (application as App).relogio

    private val pedirMicrofone = registerForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) relogio.tocou()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { Tela(relogio, ::tocou, ::telaAcesa) }
    }

    override fun onStart() {
        super.onStart()
        relogio.aparecer()
    }

    override fun onStop() {
        relogio.sumir()
        super.onStop()
    }

    /** O toque no átomo. Na 1ª vez, pede o microfone antes. */
    private fun tocou() {
        val temPermissao = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        if (temPermissao) relogio.tocou() else pedirMicrofone.launch(Manifest.permission.RECORD_AUDIO)
    }

    /** Ouvindo, pensando ou falando: a tela não apaga no meio. */
    private fun telaAcesa(acesa: Boolean) {
        if (acesa) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }
}

@Composable
private fun Tela(r: Relogio, tocar: () -> Unit, telaAcesa: (Boolean) -> Unit) {
    val estado = r.estadoVisivel
    val vivo = r.ligado.value
    val ocupado = r.ocupado
    LaunchedEffect(ocupado) { telaAcesa(ocupado) }
    val cor = corDaPersona(r)

    // O que ele está fazendo, embaixo do átomo.
    val linha = when {
        !vivo -> r.motivo.value.ifBlank { "procurando o celular…" }
        r.ouvindo.value -> "ouvindo…"
        r.tocando.value -> "falando…"
        r.atividade.value.isNotBlank() -> r.atividade.value
        estado == "pensando" -> "pensando…"
        else -> "toca pra falar"
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(Fundo)
            .verticalScroll(rememberScrollState())
            .padding(start = 24.dp, end = 24.dp, top = 16.dp, bottom = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Top,
    ) {
        NomeDaPersona(r, cor, vivo)
        Spacer(Modifier.height(2.dp))
        AtomoDoRelogio(r, estado, vivo, tocar)
        BasicText(
            linha,
            style = TextStyle(color = Fraco, fontSize = 12.sp, textAlign = TextAlign.Center),
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
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

/** JARVIS ou FRIDAY, na cor dela. É um botão: o toque troca (aqui, no PC e no app). */
@Composable
private fun NomeDaPersona(r: Relogio, cor: Color, vivo: Boolean) {
    val nome = if (r.persona.value == "friday") "FRIDAY" else "JARVIS"
    BasicText(
        nome,
        style = TextStyle(color = if (vivo) cor else Fraco, fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
            letterSpacing = 3.sp, textAlign = TextAlign.Center),
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background((if (vivo) cor else Fraco).copy(alpha = 0.14f))
            .clickable(enabled = vivo) { r.trocarPersona() }
            .padding(horizontal = 14.dp, vertical = 5.dp),
    )
}

/**
 * O átomo: sem conexão, cinza e parado; ligado e dormindo, cinza girando
 * devagar; ouvindo, pensando e falando, nas cores de sempre.
 */
@Composable
private fun AtomoDoRelogio(r: Relogio, estado: String, vivo: Boolean, tocar: () -> Unit) {
    Atomo(
        cor = corDoEstado(estado),
        escala = when (estado) {
            "sem_conexao" -> 0.80f; "escutando" -> 1.14f; "falando" -> 1.06f
            "pensando" -> 1.02f; else -> 0.88f
        },
        velocidade = when (estado) {
            "sem_conexao" -> 0f; "pensando" -> 2.2f; "falando" -> 1.25f
            "escutando" -> 1.15f; else -> 0.3f
        },
        brilho = when (estado) { "sem_conexao" -> 0.28f; "dormindo" -> 0.5f; "pensando" -> 1.2f; else -> 1f },
        turbulencia = 0f,
        nivel = r.nivel.floatValue,
        parado = !vivo,
        pulsando = estado == "dormindo",
        fundo = Fundo,
        modifier = Modifier
            .size(112.dp)
            .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) { tocar() },
    )
}
