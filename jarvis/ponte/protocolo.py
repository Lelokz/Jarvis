"""O protocolo da ponte — o vocabulário que atravessa o socket.

**Este arquivo é a especificação.** A interface é o primeiro cliente a falar
isto, e o celular vai herdar o mesmo vocabulário mesmo trocando o transporte.
Mudou um evento, muda aqui e sobe a VERSAO.

Transporte: JSON Lines sobre socket unix — um objeto por linha, UTF-8. O mesmo
formato dos logs, então as mesmas ferramentas leem os dois.

ASSISTENTE -> CLIENTES
    {"ev":"sessao", "v":1, "nome":"Jarvis", "log":"<caminho do .jsonl>"}
        Só em resposta ao "ola". O log é de onde a interface lê o histórico.
    {"ev":"estado", "estado":"dormindo|ouvindo|escutando|pensando|falando"}
        Só quando MUDA. O último é reenviado a quem acabou de dizer "ola".
    {"ev":"nivel", "v":0.42}
        Volume do microfone, 0 a 1 em escala de dB. ~15 por segundo (um a cada
        dois blocos de 32 ms do Silero), só acordado e só com cliente
        conectado. Descartável: é o primeiro a sair quando a fila enche.
    {"ev":"voce_disse", "texto":"abre o loft", "origem":"voz|texto"}
    {"ev":"jarvis_disse", "texto":"Abri o Loft.", "acao":"abrir:loft"|null,
     "perguntando":false}
    {"ev":"aviso", "situacao":"ok|limite|offline", "volta_em": 1791706200|null,
     "uso_5h": 0.21|null}
        O estado do cérebro de nuvem (Claude). Só quando muda; o último é
        reenviado a quem acabou de dizer "ola". `volta_em` é quando o limite
        da assinatura volta, no relógio do assistente.
    {"ev":"erro", "motivo":"..."}
        Só para o cliente que mandou o pedido inválido.
    {"ev":"historico", "falas":[
        {"quem":"voce",   "texto":"...", "origem":"voz|texto", "quando": 1758731040.2},
        {"quem":"jarvis", "texto":"...", "acao":"abrir:loft"|null,
         "perguntando": false, "quando": 1758731041.0}]}
        Resposta ao "ola" que pediu histórico, entregue logo depois de `sessao`
        e `estado`. Em ordem, do mais antigo para o mais novo.

        **O número pedido pode não ser o número entregue.** O assistente guarda
        as últimas MAX_HISTORICO falas da sessão; pediu mais do que ele tem,
        recebe o que ele tem. Nunca promete o que não pode cumprir.

        `quando` é o relógio do ASSISTENTE, em segundos desde a época — os
        eventos ao vivo não têm carimbo, porque para eles "agora" é a chegada.

    {"ev":"memoria", "fatos": ["..."], "conversas": [{"quando":"sáb 11/10 02:31",
     "tema":"...", "resumo":"..."}]}
        Só para quem pediu "memoria". O que o Jarvis sabe do Léo e o diário
        de conversas, mais novo primeiro.

CLIENTES -> ASSISTENTE
    {"pedir":"ola", "quem":"interface", "historico": 80}
        `historico` é opcional e vale 0 quando ausente: quantas falas anteriores
        o cliente quer receber ao conectar.

    {"pedir":"memoria"}
        Pede a memória (fatos e diário). Resposta: o evento "memoria".

    {"pedir":"falar", "texto":"abre o loft"}
        Atendido como se tivesse sido falado: acorda mesmo dormindo e a resposta
        sai na voz (decisão do Léo, Etapa 6).

**O "ola" é obrigatório antes de qualquer evento.** Quem não se apresentou não
recebe difusão. Não é cerimônia: é o que garante que tudo o que chega depois do
histórico seja novo, sem um evento ao vivo escapar pela brecha entre conectar e
pedir — e o cliente de celular vai depender disso do mesmo jeito.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

VERSAO = 1

# O que sai do assistente para os clientes. O resto que o Ciclo emite
# (acordou, dormiu, janela, tempos...) é para o terminal e fica em casa.
PUBLICOS = frozenset({"sessao", "estado", "nivel", "voce_disse", "jarvis_disse", "aviso"})
ESTADOS = ("dormindo", "ouvindo", "escutando", "pensando", "falando")
PEDIDOS = frozenset({"ola", "falar", "memoria"})

# Uma linha maior que isto sem quebra é um cliente com defeito, não um pedido.
MAX_LINHA = 64 * 1024
# Comando digitado é uma frase. Quinhentos caracteres é folga, não limite de uso.
MAX_TEXTO = 500
# Teto do histórico que o assistente guarda e que um cliente pode pedir. É o
# alcance de UMA sessão, que foi a decisão do Léo na passada 2.
MAX_HISTORICO = 200


class ErroDeProtocolo(ValueError):
    """Pedido que não segue o protocolo. A mensagem vai de volta ao cliente."""


def codificar(objeto: dict[str, Any]) -> bytes:
    return (
        json.dumps(objeto, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def ler_pedido(linha: bytes) -> tuple[str, dict[str, Any]]:
    try:
        objeto = json.loads(linha.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ErroDeProtocolo(f"não é JSON válido ({e.__class__.__name__})") from None
    if not isinstance(objeto, dict):
        raise ErroDeProtocolo("o pedido tem que ser um objeto JSON")

    tipo = objeto.get("pedir")
    if tipo not in PEDIDOS:
        raise ErroDeProtocolo(f"pedido desconhecido: {tipo!r}")

    if tipo == "falar":
        texto = objeto.get("texto")
        if not isinstance(texto, str) or not texto.strip():
            raise ErroDeProtocolo("'falar' sem texto")
        texto = " ".join(texto.split())
        if len(texto) > MAX_TEXTO:
            raise ErroDeProtocolo(f"texto com mais de {MAX_TEXTO} caracteres")
        return tipo, {"texto": texto}

    if tipo == "memoria":
        return tipo, {}

    if tipo == "ola":
        quantas = objeto.get("historico", 0)
        if isinstance(quantas, bool) or not isinstance(quantas, int) or quantas < 0:
            raise ErroDeProtocolo("'historico' tem que ser um inteiro não negativo")
        return tipo, {"historico": min(quantas, MAX_HISTORICO)}
    return tipo, {}


def caminho_socket(configurado: str = "") -> Path:
    """Onde o socket mora. Vazio no config = `$XDG_RUNTIME_DIR/jarvis.sock`.

    O `XDG_RUNTIME_DIR` é `/run/user/1000`: só o próprio usuário entra (0700), é
    apagado no logout, e é o lugar que o sistema reserva para isto.
    """
    if configurado:
        return Path(configurado).expanduser()
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "jarvis.sock"
