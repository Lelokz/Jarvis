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
 * - VOZ: a voz do Jarvis já fora do base64 e pela metade da taxa (o
 *   alto-falante do relógio não precisa de mais): a taxa (4 bytes) e o PCM
 *   (celular → relógio).
 * - FALA_INICIO / FALA_PEDACO / FALA_FIM: o microfone do relógio indo para o
 *   celular ENQUANTO o Léo fala (PCM 16 kHz em pedaços de 160 ms). Quem decide
 *   o fim da frase é o celular, com o Silero (`EscutaRemota.kt`), e responde
 *   com o evento `_escuta`. FALA_INICIO leva `{"desiste_ms": N}`; FALA_FIM,
 *   "toque" (terminar agora) ou "cancelar" (jogar fora).
 *
 * Este arquivo mora em `comum/`: o app do celular e o do relógio usam o mesmo.
 */
object Tubo {
    const val TEXTO = 1
    const val AUDIO = 2
    const val VOZ = 3
    const val FALA_INICIO = 4
    const val FALA_PEDACO = 5
    const val FALA_FIM = 6
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
