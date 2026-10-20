"""O protocolo da ponte — o vocabulário que atravessa o socket.

**Este arquivo é a especificação.** A interface é o primeiro cliente a falar
isto, e o celular vai herdar o mesmo vocabulário mesmo trocando o transporte.
Mudou um evento, muda aqui e sobe a VERSAO.

Transporte: JSON Lines sobre socket unix — um objeto por linha, UTF-8. O mesmo
formato dos logs, então as mesmas ferramentas leem os dois.

ASSISTENTE -> CLIENTES
    {"ev":"sessao", "v":2, "nome":"Jarvis", "log":"<caminho do .jsonl>", "id": 3}
        Só em resposta ao "ola". O log é de onde a interface lê o histórico.
        `id` (v2) é o número deste cliente nesta sessão (o "para" da "voz").
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
    {"ev":"mostrar", "titulo":"..."|"", "texto":"<markdown>"}
        O que o Claude mandou para a JANELA, sem voz: código, lista, passos,
        o pedido de permissão por extenso. Entra no histórico (quem "painel").
    {"ev":"atividade", "texto":"Bash — olhando a pasta lixo"}
        A ferramenta que o Claude está usando agora. Descartável e fora do
        histórico: é o "o que ele está fazendo", não o que ele disse.
    {"ev":"voz", "para": 3, "taxa": 40000, "pcm": "<base64 de PCM int16 mono>"}
    {"ev":"voz", "para": 3, "fim": true}
        A voz da resposta, pedaço por pedaço, **só para o cliente que pediu**
        (o `id` dele, no "sessao") e só se ele disse "voz": true no "ola". É
        como o celular fala: o pedido veio dele, a resposta sai nele, e a
        caixa de som do PC fica quieta. Fora do histórico.
    {"ev":"erro", "motivo":"..."}
        Só para o cliente que mandou o pedido inválido.
    {"ev":"historico", "falas":[
        {"quem":"voce",   "texto":"...", "origem":"voz|texto", "quando": 1758731040.2},
        {"quem":"jarvis", "texto":"...", "acao":"abrir:loft"|null,
         "perguntando": false, "quando": 1758731041.0},
        {"quem":"painel", "titulo":"...", "texto":"<markdown>", "quando": ...}]}
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
    {"pedir":"ola", "quem":"interface", "historico": 80, "voz": false}
        `historico` é opcional e vale 0 quando ausente: quantas falas anteriores
        o cliente quer receber ao conectar. `voz` (v2, opcional): true = este
        cliente é um "corpo" (o celular): o que ele pedir é respondido NELE,
        com os eventos "voz", sem acordar nem falar no PC. O "sessao" de
        resposta traz o `id` do cliente.

    {"pedir":"memoria"}
        Pede a memória (fatos e diário). Resposta: o evento "memoria".

    {"pedir":"falar", "texto":"abre o loft"}
        Atendido como se tivesse sido falado: acorda mesmo dormindo e a resposta
        sai na voz (decisão do Léo, Etapa 6). De um cliente com "voz": true, a
        voz sai nele.

    {"pedir":"ouvir", "arquivo":"<PASTA_AUDIO>/<nome>.pcm"}
        (v2) Uma fala gravada no celular: PCM int16 mono a 16 kHz, num arquivo
        dentro de `pasta_audio()` (quem escreve é a porta remota, no mesmo PC;
        áudio não cabe numa linha). O assistente transcreve, apaga o arquivo e
        atende como o "falar". Arquivo fora da pasta é recusado.

    "anexos": ["<pasta_recebidos()>/..."]
        (v2, opcional no "falar" e no "ouvir") Fotos, vídeos e arquivos que o
        Léo mandou do celular junto com o pedido; a porta remota já os gravou
        em `pasta_recebidos()`. O Claude recebe os caminhos e abre (imagem com
        o Read; vídeo tirando quadros). Até MAX_ANEXOS; fora da pasta, recusa.

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

VERSAO = 2

# O que sai do assistente para os clientes. O resto que o Ciclo emite
# (acordou, dormiu, janela, tempos...) é para o terminal e fica em casa.
PUBLICOS = frozenset({"sessao", "estado", "nivel", "voce_disse", "jarvis_disse", "aviso",
                      "mostrar", "atividade", "voz"})
ESTADOS = ("dormindo", "ouvindo", "escutando", "pensando", "falando")
PEDIDOS = frozenset({"ola", "falar", "memoria", "ouvir"})

# Uma linha maior que isto sem quebra é um cliente com defeito, não um pedido.
MAX_LINHA = 64 * 1024
# Comando digitado é uma frase. Quinhentos caracteres é folga, não limite de uso.
MAX_TEXTO = 500
# Teto do histórico que o assistente guarda e que um cliente pode pedir. É o
# alcance de UMA sessão, que foi a decisão do Léo na passada 2.
MAX_HISTORICO = 200
# Anexos num pedido só (fotos, vídeos, arquivos do celular).
MAX_ANEXOS = 10


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
        return tipo, {"texto": texto, "anexos": _anexos(objeto)}

    if tipo == "memoria":
        return tipo, {}

    if tipo == "ouvir":
        arquivo = objeto.get("arquivo")
        if not isinstance(arquivo, str) or not arquivo:
            raise ErroDeProtocolo("'ouvir' sem arquivo")
        caminho = Path(arquivo).resolve()
        if caminho.parent != pasta_audio().resolve() or caminho.suffix != ".pcm":
            raise ErroDeProtocolo("'ouvir' só aceita .pcm da pasta de áudio da ponte")
        return tipo, {"arquivo": str(caminho), "anexos": _anexos(objeto)}

    if tipo == "ola":
        quantas = objeto.get("historico", 0)
        if isinstance(quantas, bool) or not isinstance(quantas, int) or quantas < 0:
            raise ErroDeProtocolo("'historico' tem que ser um inteiro não negativo")
        voz = objeto.get("voz", False)
        if not isinstance(voz, bool):
            raise ErroDeProtocolo("'voz' tem que ser true ou false")
        quem = objeto.get("quem", "")
        return tipo, {"historico": min(quantas, MAX_HISTORICO), "voz": voz,
                      "quem": quem if isinstance(quem, str) else ""}
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


def pasta_audio() -> Path:
    """Onde a porta remota deixa as falas gravadas no celular para o "ouvir".
    Dentro do `$XDG_RUNTIME_DIR` (só o usuário entra, some no logout)."""
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "jarvis-remoto"


def pasta_recebidos() -> Path:
    """Onde ficam as fotos, vídeos e arquivos que o Léo manda do celular.
    Fora do git e fora do $XDG_RUNTIME_DIR: o Claude pode precisar deles
    depois (a porta remota apaga os de mais de 14 dias)."""
    return Path.home() / ".local" / "share" / "jarvis" / "recebidos"


def _anexos(objeto: dict[str, Any]) -> list[str]:
    anexos = objeto.get("anexos", [])
    if not isinstance(anexos, list) or len(anexos) > MAX_ANEXOS:
        raise ErroDeProtocolo(f"'anexos' tem que ser uma lista de até {MAX_ANEXOS}")
    pasta = pasta_recebidos().resolve()
    caminhos = []
    for a in anexos:
        if not isinstance(a, str):
            raise ErroDeProtocolo("anexo tem que ser um caminho")
        c = Path(a).resolve()
        if pasta not in c.parents or not c.is_file():
            raise ErroDeProtocolo("anexo fora da pasta de recebidos")
        caminhos.append(str(c))
    return caminhos
