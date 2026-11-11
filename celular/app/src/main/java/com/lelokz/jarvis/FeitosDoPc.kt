package com.lelokz.jarvis

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.core.content.FileProvider
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * A galeria Feitos no celular (app beta 0.21.5): as miniaturas e os arquivos
 * vêm do PC pela porta remota (/feito, com a chave), e só o que está na
 * galeria. Imagem abre no próprio app; vídeo, documento e código baixam e
 * abrem no app certo do celular.
 */
object FeitosDoPc {
    private val cliente = OkHttpClient.Builder().callTimeout(3, TimeUnit.MINUTES).build()
    private val cache = object : LruCache<String, Bitmap>(24 * 1024 * 1024) {
        override fun sizeOf(key: String, value: Bitmap) = value.byteCount
    }

    private fun pedido(c: Context, id: String, mini: Boolean): Request? {
        val p = c.getSharedPreferences("jarvis", Context.MODE_PRIVATE)
        val base = p.getString("base", null)?.trimEnd('/') ?: return null
        val chave = p.getString("chave", null) ?: return null
        return Request.Builder().url("$base/feito?id=$id" + (if (mini) "&mini=1" else ""))
            .header("Authorization", "Bearer $chave").build()
    }

    /** A imagem (ou o 1º quadro do vídeo), reduzida pra caber em `lado` px. Fora da thread principal. */
    fun imagem(c: Context, id: String, mini: Boolean, lado: Int): Bitmap? {
        val chave = "$id-$mini-$lado"
        cache.get(chave)?.let { return it }
        val req = pedido(c, id, mini) ?: return null
        return try {
            val bytes = cliente.newCall(req).execute().use { r -> if (!r.isSuccessful) return null; r.body?.bytes() } ?: return null
            val limites = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, limites)
            var passo = 1
            while (limites.outWidth / (passo * 2) >= lado && limites.outHeight / (passo * 2) >= lado / 2) passo *= 2
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = passo })
                ?.also { cache.put(chave, it) }
        } catch (e: Exception) {
            null
        }
    }

    /** Baixa e abre no app do celular que sabe abrir. Devolve o erro, ou "". */
    fun abrir(c: Context, id: String, nome: String): String {
        val req = pedido(c, id, false) ?: return "Sem conexão com o PC."
        val pasta = File(c.cacheDir, "feitos").apply { mkdirs() }
        pasta.listFiles()?.filter { System.currentTimeMillis() - it.lastModified() > 86_400_000 }?.forEach { it.delete() }
        val arquivo = File(pasta, nome.replace(Regex("[/\\\\]"), "_"))
        try {
            cliente.newCall(req).execute().use { r ->
                if (!r.isSuccessful) return "O PC não achou o arquivo (${r.code})."
                arquivo.outputStream().use { saida -> r.body?.byteStream()?.copyTo(saida) ?: return "Veio vazio." }
            }
        } catch (e: Exception) {
            return "Sem conexão com o PC."
        }
        val uri = FileProvider.getUriForFile(c, "${c.packageName}.arquivos", arquivo)
        val tipo = c.contentResolver.getType(uri) ?: android.webkit.MimeTypeMap.getSingleton()
            .getMimeTypeFromExtension(arquivo.extension.lowercase()) ?: "*/*"
        return try {
            c.startActivity(Intent.createChooser(Intent(Intent.ACTION_VIEW).setDataAndType(uri, tipo)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), nome).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            ""
        } catch (e: Exception) {
            "Nenhum app do celular abre esse tipo de arquivo."
        }
    }
}
