package com.lelokz.jarvis

import java.io.DataInputStream
import java.io.DataOutputStream

/**
 * O tubo entre o relógio e o celular (um canal do Wear OS, por Bluetooth):
 * mensagens em fila, cada uma com o tipo (1 byte), o tamanho (4 bytes) e os
 * dados.
 *
 * - TEXTO: um evento ou pedido da porta remota, o mesmo JSON do WebSocket.
 * - AUDIO: o WAV da fala gravada no relógio (relógio → celular).
 * - VOZ: a voz do Jarvis já fora do base64: a taxa (4 bytes) e o PCM
 *   (celular → relógio). Um quarto a menos de bytes no Bluetooth.
 *
 * Este arquivo mora em `comum/`: o app do celular e o do relógio usam o mesmo.
 */
object Tubo {
    const val TEXTO = 1
    const val AUDIO = 2
    const val VOZ = 3
    const val CAMINHO = "/jarvis"

    fun escrever(saida: DataOutputStream, tipo: Int, dados: ByteArray) {
        synchronized(saida) {
            saida.writeByte(tipo)
            saida.writeInt(dados.size)
            saida.write(dados)
            saida.flush()
        }
    }

    /** A próxima mensagem, ou null quando o outro lado fechou. */
    fun ler(entrada: DataInputStream): Pair<Int, ByteArray>? {
        val tipo = entrada.read()
        if (tipo < 0) return null
        val n = entrada.readInt()
        if (n < 0 || n > 64 * 1024 * 1024) return null
        val dados = ByteArray(n)
        entrada.readFully(dados)
        return tipo to dados
    }
}
