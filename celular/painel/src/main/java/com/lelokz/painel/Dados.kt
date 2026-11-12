package com.lelokz.painel

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZonedDateTime

/** O pacote do Painel (o mesmo da janela do PC: jarvis/youtube/dados.py → para_janela). */
data class Canal(val titulo: String, val inscritos: Long, val views: Long, val videos: Int, val meta: Long)
data class Numeros(val views28: Long, val horas28: Long, val inscritos28: Long, val viewsVar: Int?, val horasVar: Int?, val inscritosAntes: Long?)
data class Dia(val dia: LocalDate, val views: Long)
data class Video(
    val id: String, val titulo: String, val descricao: String, val publicado: ZonedDateTime?, val duracao: Int,
    val views: Long, val likes: Long, val comentarios: Long, val visibilidade: String, val agendado: ZonedDateTime?,
    val tags: List<String>, val thumb: String, val comparacao: String,
)
data class Card(val id: Int, val titulo: String, val jogo: String, val coluna: String, val data: String,
                val notas: String, val arquivos: List<String>, val video: String)
data class Comentario(val id: String, val video: String, val autor: String, val texto: String, val quando: ZonedDateTime?,
                      val likes: Long, val lido: Boolean, val pergunta: Boolean, val respondido: Boolean, val videoTitulo: String)
data class Fatia(val nome: String, val valor: Double)
data class Top(val video: String, val views: Long, val inscritos: Long)
data class Analises(val top: List<Top>, val origens: List<Fatia>, val paises: List<Fatia>, val idades: List<Fatia>, val aparelhos: List<Fatia>)

data class Pacote(
    val conectado: Boolean, val temDados: Boolean, val atualizado: Double,
    val canal: Canal, val numeros: Numeros, val dias: List<Dia>, val videos: List<Video>,
    val cards: List<Card>, val comentarios: List<Comentario>, val naoLidos: Int, val analises: Analises,
)

val COLUNAS = listOf("ideia" to "Ideia", "gravando" to "Gravando", "editando" to "Editando",
                     "pronto" to "Pronto", "agendado" to "Agendado", "postado" to "Postado")

private val ZONA: ZoneId = ZoneId.systemDefault()

fun quando(iso: String?): ZonedDateTime? =
    if (iso.isNullOrEmpty()) null else try { Instant.parse(iso).atZone(ZONA) } catch (e: Exception) {
        try { ZonedDateTime.parse(iso).withZoneSameInstant(ZONA) } catch (e: Exception) { null }
    }

private fun JSONArray?.objetos(): List<JSONObject> =
    if (this == null) emptyList() else (0 until length()).mapNotNull { optJSONObject(it) }

private fun JSONArray?.textos(): List<String> =
    if (this == null) emptyList() else (0 until length()).map { optString(it) }

private fun JSONObject.intOuNada(k: String): Int? = if (has(k) && !isNull(k)) optInt(k) else null
private fun JSONObject.longOuNada(k: String): Long? = if (has(k) && !isNull(k)) optLong(k) else null

private fun fatias(a: JSONArray?) = a.objetos().map { Fatia(it.optString("nome"), it.optDouble("valor", 0.0)) }

fun lerPacote(j: JSONObject): Pacote {
    val c = j.optJSONObject("canal") ?: JSONObject()
    val n = j.optJSONObject("numeros") ?: JSONObject()
    val a = j.optJSONObject("analises") ?: JSONObject()
    return Pacote(
        conectado = j.optBoolean("conectado"),
        temDados = j.optBoolean("temDados"),
        atualizado = j.optDouble("atualizado", 0.0),
        canal = Canal(c.optString("titulo"), c.optLong("inscritos"), c.optLong("views"), c.optInt("videos"), c.optLong("meta", 100)),
        numeros = Numeros(n.optLong("views28"), n.optLong("horas28"), n.optLong("inscritos28"),
            n.intOuNada("views28_var"), n.intOuNada("horas28_var"), n.longOuNada("inscritos28_antes")),
        dias = j.optJSONArray("dias").objetos().mapNotNull { d ->
            try { Dia(LocalDate.parse(d.optString("dia")), d.optLong("views")) } catch (e: Exception) { null }
        },
        videos = j.optJSONArray("videos").objetos().map { v ->
            Video(v.optString("id"), v.optString("titulo"), v.optString("descricao"), quando(v.optString("publicado")),
                v.optInt("duracao"), v.optLong("views"), v.optLong("likes"), v.optLong("comentarios"),
                v.optString("visibilidade"), quando(v.optString("agendado")), v.optJSONArray("tags").textos(),
                v.optString("thumb"), v.optString("comparacao"))
        },
        cards = j.optJSONArray("cards").objetos().map { k ->
            Card(k.optInt("id"), k.optString("titulo"), k.optString("jogo"), k.optString("coluna"), k.optString("data"),
                k.optString("notas"), k.optJSONArray("arquivos").textos(), k.optString("video"))
        },
        comentarios = j.optJSONArray("comentarios").objetos().map { k ->
            Comentario(k.optString("id"), k.optString("video"), k.optString("autor"), k.optString("texto"),
                quando(k.optString("quando")), k.optLong("likes"), k.optInt("lido") != 0, k.optInt("pergunta") != 0,
                k.optInt("respondido") != 0, k.optString("video_titulo"))
        },
        naoLidos = j.optInt("naoLidos"),
        analises = Analises(
            top = a.optJSONArray("top").objetos().map { Top(it.optString("video"), it.optLong("views"), it.optLong("inscritos")) },
            origens = fatias(a.optJSONArray("origens")), paises = fatias(a.optJSONArray("paises")),
            idades = fatias(a.optJSONArray("idades")), aparelhos = fatias(a.optJSONArray("aparelhos")),
        ),
    )
}

/** 58321 → "58.321" (o jeito brasileiro). */
fun mil(n: Long): String = String.format(java.util.Locale.US, "%,d", n).replace(',', '.')
fun mil(n: Int): String = mil(n.toLong())
