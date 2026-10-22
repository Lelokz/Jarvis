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
     "perguntando":false, "opcoes":["Apagar", "Deixar"]}
        `opcoes` (v3, só numa pergunta que tem opções): a janela mostra como
        botões; clicar manda o texto da opção como um "falar".
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
     "tema":"...", "resumo":"..."}], "texto": "<o CLAUDE.md inteiro>"}
        Só para quem pediu "memoria". O que o Jarvis sabe do Léo e o diário
        de conversas, mais novo primeiro. `texto` (v3): o arquivo inteiro,
        em markdown, para a página de memória da janela.

    (v3, a janela grande; o celular ignora todos estes)
    {"ev":"cerebro", "modelo":"auto|haiku|sonnet|opus",
     "esforco":"low|medium|high|xhigh|max", "persona":"jarvis"}
        O que está escolhido. Reenviado a quem diz "ola" e a cada mudança.
    {"ev":"conversa_atual", "id":"<uuid>", "falas":[...]}
        A conversa do Jarvis mudou (ligou, "nova", "continuar"): o id da
        sessão do Claude Code e as falas dela (vazio na nova). O histórico
        da ponte passa a ser este. Reenviado a quem diz "ola", só o id.
    {"ev":"uso", "cinco_horas":{"uso":0.56, "volta_em":1792643400},
     "semana":{"uso":0.76, "volta_em":1792807200}}
        O uso da assinatura (0 a 1) e quando cada janela renova. Só quando
        muda (chega com as respostas do Claude); reenviado a quem diz "ola".
    {"ev":"escrevendo", "bloco": 3, "delta": "um pedaço"}
    {"ev":"escrevendo", "fim": true, "descartar": false}
        (beta 0.5) O texto da resposta enquanto ele escreve, em pedaços; o
        texto inteiro chega depois, como sempre (jarvis_disse / mostrar), e
        substitui. `fim`: acabou o turno (o que sobrou vira texto normal; com
        `descartar`, some: o rápido passou o pedido para o Opus). Fora do
        histórico; só para quem não é corpo (a janela).
    {"ev":"conversas", "lista":[{"id", "titulo", "quando", "criada", "origem"}]}
        Só para quem pediu "conversas". Mais nova primeiro.
    {"ev":"conversa", "id":"<uuid>", "falas":[...]}
        Só para quem pediu "abrir": uma conversa qualquer, só para ler.

CLIENTES -> ASSISTENTE
    {"pedir":"ola", "quem":"interface", "historico": 80, "voz": false}
        `historico` é opcional e vale 0 quando ausente: quantas falas anteriores
        o cliente quer receber ao conectar. `voz` (v2, opcional): true = este
        cliente é um "corpo" (o celular): o que ele pedir é respondido NELE,
        com os eventos "voz", sem acordar nem falar no PC. O "sessao" de
        resposta traz o `id` do cliente. `janela` (v3, opcional): um corpo
        que TAMBÉM mostra a janela nova (o app do celular, beta 0.6) e quer
        os eventos dela (`conversa_atual`, `escrevendo`, `uso`); o relógio
        não manda e não recebe.

    {"pedir":"memoria"}
        Pede a memória (fatos e diário). Resposta: o evento "memoria".

    (v3) {"pedir":"conversas"}            -> "conversas"
         {"pedir":"abrir", "id":"<uuid>"} -> "conversa" (só para ler)
         {"pedir":"nova"}                 -> chat novo ("conversa_atual" para todos)
         {"pedir":"continuar", "id":"..."} -> o Jarvis volta para essa conversa
         {"pedir":"cerebro", "modelo":"...", "esforco":"..."}  (um ou os dois)
         {"pedir":"parar"}                -> interrompe a tarefa (o botão Parar)
         {"pedir":"renomear", "id":"...", "titulo":"..."} -> "conversas"
         {"pedir":"apagar", "id":"..."}   -> manda para a lixeira; "conversas"
        A conversa de AGORA não pode ser apagada (erro): o Jarvis está nela.
        "nova" e "continuar" com o Jarvis no meio de uma tarefa voltam
        {"ev":"erro"} para quem pediu.

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

    "mudo": true
        (v2, opcional no "falar" e no "ouvir") O celular está no mudo: a
        resposta vai só em texto, e a voz nem é gerada (mais rápido).

**O "ola" é obrigatório antes de qualquer evento.** Quem não se apresentou não
recebe difusão. Não é cerimônia: é o que garante que tudo o que chega depois do
histórico seja novo, sem um evento ao vivo escapar pela brecha entre conectar e
pedir — e o cliente de celular vai depender disso do mesmo jeito.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

VERSAO = 3

# O que sai do assistente para os clientes. O resto que o Ciclo emite
# (acordou, dormiu, janela, tempos...) é para o terminal e fica em casa.
PUBLICOS = frozenset({"sessao", "estado", "nivel", "voce_disse", "jarvis_disse", "aviso",
                      "mostrar", "atividade", "voz", "cerebro", "conversa_atual", "uso",
                      "escrevendo", "notificacao"})
ESTADOS = ("dormindo", "ouvindo", "escutando", "pensando", "falando")
PEDIDOS = frozenset({"ola", "falar", "memoria", "ouvir",
                     "conversas", "abrir", "nova", "continuar", "cerebro", "parar",
                     "renomear", "apagar"})

# Uma linha maior que isto sem quebra é um cliente com defeito, não um pedido.
MAX_LINHA = 64 * 1024
# Comando digitado. Na janela grande (out/2026) dá para colar um texto inteiro.
MAX_TEXTO = 8000
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
        # Espaços repetidos saem; as quebras de linha ficam (texto colado).
        texto = "\n".join(" ".join(l.split()) for l in texto.strip().splitlines()).strip()
        if len(texto) > MAX_TEXTO:
            raise ErroDeProtocolo(f"texto com mais de {MAX_TEXTO} caracteres")
        return tipo, {"texto": texto, "anexos": _anexos(objeto), "mudo": _mudo(objeto)}

    if tipo in ("memoria", "conversas", "nova", "parar"):
        return tipo, {}

    if tipo in ("abrir", "continuar", "renomear", "apagar"):
        sessao = objeto.get("id")
        if not isinstance(sessao, str) or not re.fullmatch(r"[0-9a-fA-F-]{8,64}", sessao):
            raise ErroDeProtocolo(f"'{tipo}' sem um id de conversa válido")
        if tipo == "renomear":
            titulo = objeto.get("titulo")
            if not isinstance(titulo, str) or not titulo.strip() or len(titulo) > 200:
                raise ErroDeProtocolo("'renomear' sem um título válido")
            return tipo, {"id": sessao, "titulo": titulo.strip()}
        return tipo, {"id": sessao}

    if tipo == "cerebro":
        dados = {}
        for campo in ("modelo", "esforco"):
            valor = objeto.get(campo)
            if valor is not None:
                if not isinstance(valor, str) or len(valor) > 20:
                    raise ErroDeProtocolo(f"'{campo}' inválido")
                dados[campo] = valor
        if not dados:
            raise ErroDeProtocolo("'cerebro' sem modelo nem esforço")
        return tipo, dados

    if tipo == "ouvir":
        arquivo = objeto.get("arquivo")
        if not isinstance(arquivo, str) or not arquivo:
            raise ErroDeProtocolo("'ouvir' sem arquivo")
        caminho = Path(arquivo).resolve()
        if caminho.parent != pasta_audio().resolve() or caminho.suffix != ".pcm":
            raise ErroDeProtocolo("'ouvir' só aceita .pcm da pasta de áudio da ponte")
        return tipo, {"arquivo": str(caminho), "anexos": _anexos(objeto), "mudo": _mudo(objeto)}

    if tipo == "ola":
        quantas = objeto.get("historico", 0)
        if isinstance(quantas, bool) or not isinstance(quantas, int) or quantas < 0:
            raise ErroDeProtocolo("'historico' tem que ser um inteiro não negativo")
        voz = objeto.get("voz", False)
        if not isinstance(voz, bool):
            raise ErroDeProtocolo("'voz' tem que ser true ou false")
        quem = objeto.get("quem", "")
        janela = objeto.get("janela", False)
        if not isinstance(janela, bool):
            raise ErroDeProtocolo("'janela' tem que ser true ou false")
        return tipo, {"historico": min(quantas, MAX_HISTORICO), "voz": voz, "janela": janela,
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


def _mudo(objeto: dict[str, Any]) -> bool:
    mudo = objeto.get("mudo", False)
    if not isinstance(mudo, bool):
        raise ErroDeProtocolo("'mudo' tem que ser true ou false")
    return mudo


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
