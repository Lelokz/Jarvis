package com.lelokz.jarvis

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Markdown do jeito que o Jarvis escreve: parágrafos, títulos (#), listas
 * (-, *, 1.), **negrito**, `código` e blocos de código. Cada bloco de código
 * vira uma caixa com a linguagem e o "Copiar", como no PC. Sem biblioteca:
 * é o pouco que ele usa, e o resto aparece como texto.
 */
private sealed interface Parte {
    data class Texto(val linhas: List<String>) : Parte
    data class Codigo(val lingua: String, val conteudo: String) : Parte
}

private fun partes(t: String): List<Parte> {
    val saida = mutableListOf<Parte>()
    val texto = mutableListOf<String>()
    var codigo: StringBuilder? = null
    var lingua = ""
    for (linha in t.lines()) {
        if (linha.trimStart().startsWith("```")) {
            if (codigo == null) {
                if (texto.isNotEmpty()) { saida += Parte.Texto(texto.toList()); texto.clear() }
                codigo = StringBuilder(); lingua = linha.trim().removePrefix("```").trim()
            } else {
                saida += Parte.Codigo(lingua, codigo.toString().trimEnd()); codigo = null
            }
        } else if (codigo != null) {
            codigo.append(linha).append('\n')
        } else {
            texto += linha
        }
    }
    if (codigo != null) saida += Parte.Codigo(lingua, codigo.toString().trimEnd())  // ainda chegando
    if (texto.isNotEmpty()) saida += Parte.Texto(texto.toList())
    return saida
}

/** **negrito** e `código` dentro de uma linha. */
private fun enfeitar(linha: String, mono: Color): AnnotatedString = buildAnnotatedString {
    var i = 0
    while (i < linha.length) {
        when {
            linha.startsWith("**", i) && linha.indexOf("**", i + 2) > i -> {
                val fim = linha.indexOf("**", i + 2)
                withStyle(SpanStyle(fontWeight = FontWeight.SemiBold, color = Color(0xFFE6EBF2))) {
                    append(linha.substring(i + 2, fim))
                }
                i = fim + 2
            }
            linha[i] == '`' && linha.indexOf('`', i + 1) > i -> {
                val fim = linha.indexOf('`', i + 1)
                withStyle(SpanStyle(fontFamily = FontFamily.Monospace, color = mono,
                    background = Color(0xFF181E29))) { append(linha.substring(i + 1, fim)) }
                i = fim + 1
            }
            else -> { append(linha[i]); i++ }
        }
    }
}

@Composable
fun Markdown(texto: String, cor: Color, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        for (p in partes(texto)) when (p) {
            is Parte.Codigo -> CaixaDeCodigo(p.lingua, p.conteudo)
            is Parte.Texto -> Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                for (bruta in p.linhas) {
                    val linha = bruta.trimEnd()
                    if (linha.isBlank()) continue
                    val item = Regex("^\\s*([-*•]|\\d+[.)])\\s+(.*)").find(linha)
                    val titulo = Regex("^#{1,6}\\s+(.*)").find(linha)
                    when {
                        titulo != null -> Text(enfeitar(titulo.groupValues[1], cor), color = Color(0xFFE6EBF2),
                            fontSize = 16.sp, fontWeight = FontWeight.SemiBold, lineHeight = 22.sp)
                        item != null -> Row {
                            val marca = item.groupValues[1]
                            Text(if (marca[0].isDigit()) marca else "•", color = cor, fontSize = 15.sp,
                                modifier = Modifier.width(if (marca[0].isDigit()) 22.dp else 14.dp))
                            Text(enfeitar(item.groupValues[2], Color(0xFFC9D1DD)), color = cor,
                                fontSize = 15.sp, lineHeight = 22.sp)
                        }
                        else -> Text(enfeitar(linha, Color(0xFFC9D1DD)), color = cor, fontSize = 15.sp,
                            lineHeight = 22.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun CaixaDeCodigo(lingua: String, conteudo: String) {
    val area = LocalClipboardManager.current
    var copiado by remember { mutableStateOf(false) }
    val forma = RoundedCornerShape(11.dp)
    Column(Modifier.fillMaxWidth().clip(forma).border(1.dp, Color(0xFF1F2734), forma)
        .background(Color(0xFF0C0F15))) {
        Row(Modifier.fillMaxWidth().background(Color(0xFF131821)).padding(horizontal = 12.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Text(lingua.ifEmpty { "código" }, color = Color(0xFF7E879B), fontSize = 11.sp)
            Spacer(Modifier.weight(1f))
            Row(Modifier.clip(RoundedCornerShape(6.dp)).clickable {
                area.setText(AnnotatedString(conteudo)); copiado = true
            }.padding(horizontal = 4.dp, vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
                Ic(if (copiado) Icones.certo else Icones.copiar, Color(0xFF7E879B), 13.dp)
                Spacer(Modifier.width(5.dp))
                Text(if (copiado) "Copiado" else "Copiar", color = Color(0xFF7E879B), fontSize = 11.sp)
            }
        }
        Text(conteudo, color = Color(0xFFC9D1DD), fontSize = 12.sp, fontFamily = FontFamily.Monospace,
            lineHeight = 17.sp, modifier = Modifier.horizontalScroll(rememberScrollState()).padding(12.dp))
    }
}
