package com.lelokz.jarvis

import android.app.Activity
import android.content.Intent
import android.os.Bundle

/**
 * O app "Painel do Canal" pega daqui o link e a chave do PC (12/11/2026): o
 * Léo não precisa colar nada. Só abre pra app com a MESMA assinatura (a
 * permissão LIGACAO é "signature", no AndroidManifest): outro app qualquer
 * não consegue pedir a chave.
 */
class DarLigacao : Activity() {
    override fun onCreate(estado: Bundle?) {
        super.onCreate(estado)
        val prefs = getSharedPreferences("jarvis", MODE_PRIVATE)
        val base = prefs.getString("base", null)
        val chave = prefs.getString("chave", null)
        if (base != null && chave != null) setResult(RESULT_OK, Intent().putExtra("base", base).putExtra("chave", chave))
        else setResult(RESULT_CANCELED)
        finish()
    }
}
