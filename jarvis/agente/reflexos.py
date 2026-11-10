"""Reflexos: o pouco que responde em 0 s, sem passar pelo Claude.

Decisão do Léo (out/2026): o Jarvis passa a ser o Claude Code inteiro, e as
listas fechadas saem. Ficam só pausa/volta/próxima e volume, porque pelo
agente "pausa a música" levou 14 s (medido: ele descobre o sistema do zero) e
é o comando que mais se repete. O "dorme aí" fica no próprio ciclo de voz.

A regra que segura isto: casa a fala INTEIRA, nunca um pedaço. "Para a música
e abre o Spotify" não é reflexo: vai para o Claude, que entende as duas coisas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from jarvis.nucleo import midia, obs, sistema
from jarvis.nucleo.atalhos import normalizar


@dataclass(frozen=True)
class Reflexo:
    fala: str
    acao: str | None


# Volume só com a frase inteira de volume. Mais que o limite (70) não é
# reflexo: vai para o Claude, que confirma antes (já machucou o ouvido do Léo).
# Contra o texto já normalizado: sem acento, sem pontuação e sem "o", "no",
# "um" ("Volume no 30." chega como "volume 30").
_VOLUME = re.compile(
    r"^(aumenta|aumente|sobe|abaixa|abaixe|baixa|diminui|diminua)( (um )?pouco)? "
    r"(volume|som)( (um )?pouco)?$"
    r"|^((coloca|poe|bota) )?(volume|som)( (em|pra|para|a))? \d+( por cento)?$"
)


# O OBS por voz (08/11/2026). Frase inteira, já normalizada ("Começa a gravar."
# chega "comeca gravar"). O "pausa" do OBS precisa de "gravação": sozinho é a música.
_V = "(?:muta|mutar|silencia|silenciar|desliga|desligar)"
_DESV = "(?:desmuta|desmutar|ativa|ativar|liga|ligar)"
_OBS = [
    ("gravar", re.compile(r"^(?:(?:comeca|comecar|inicia|iniciar|liga|bora|pode) )?(?:gravar|gravacao|grava)"
                          r"(?: (?:ai|agora|ja))?$")),
    ("parar", re.compile(r"^(?:para|parar|termina|terminar|encerra|encerrar|finaliza|finalizar|desliga|corta) "
                         r"(?:gravacao|gravar|de gravar)$")),
    ("pausar", re.compile(r"^(?:pausa|pausar|pause) (?:gravacao|gravar)$")),
    ("continuar", re.compile(r"^(?:continua|continuar|retoma|retomar|volta|voltar|despausa|despausar) "
                             r"(?:gravacao|gravar|gravando|a gravar)$")),
    ("mutar microfone", re.compile(rf"^{_V} (?:microfone|mic)(?: (?:do )?obs)?$")),
    ("desmutar microfone", re.compile(rf"^{_DESV} (?:microfone|mic)(?: (?:do )?obs)?$")),
    ("mutar desktop", re.compile(rf"^{_V} (?:som|audio)(?: do)? (?:pc|computador|desktop|jogo)$")),
    ("desmutar desktop", re.compile(rf"^{_DESV} (?:som|audio)(?: do)? (?:pc|computador|desktop|jogo)$")),
]
_CENA = re.compile(r"^(?:troca|trocar|muda|mudar|vai|coloca|bota|poe)(?: (?:pra|para|na|pro))? cena (.+)$")


def reflexo_obs(falado: str) -> Reflexo | None:
    t = normalizar(falado)
    m = _CENA.match(t)
    if m:
        if not obs.aberto():
            return None
        r = obs.cena(m.group(1))
        return Reflexo(r.mensagem, "obs:cena" if r.ok else None)
    for nome, padrao in _OBS:
        if not padrao.match(t):
            continue
        if nome == "gravar":
            r = obs.gravar()
        elif nome in ("parar", "pausar", "continuar"):
            r = getattr(obs, nome)()
        else:
            # "Muta o microfone" / "o som do PC" com o OBS fechado não é do OBS:
            # vai para o Claude (o som do PC, o mudo do sistema).
            if not obs.aberto():
                return None
            acao, qual = nome.split()
            r = obs.mutar(qual, acao == "mutar")
        return Reflexo(r.mensagem, f"obs:{nome.replace(' ', ':')}" if r.ok else None)
    return None


def reflexo(falado: str, limite_volume: int = 70, passo: int = 10) -> Reflexo | None:
    """A resposta pronta, ou None para mandar ao Claude."""
    r = reflexo_obs(falado)
    if r is not None:
        return r
    cru = midia.comando_cru(falado)
    if cru is not None:
        r = midia.controlar(cru.acao, cru.qual)
        return Reflexo(r.mensagem, f"midia:{cru.acao}" if r.ok else None)

    if _VOLUME.match(normalizar(falado)):
        plano = sistema.planejar_volume(falado, passo)
        if not plano.ok or plano.caminho == "mudo" or plano.novo > limite_volume:
            return None
        r = sistema.aplicar_volume(plano.novo)
        return Reflexo(r.mensagem, f"midia:volume:{plano.novo}" if r.ok else None)
    return None


# O modo code (10/11/2026): entrar, trocar de projeto e sair são do CORPO (a
# conversa do Claude troca por baixo), nunca do Claude. Frase inteira,
# normalizada ("Jarvis, modo code no Loft." chega "jarvis modo code loft").
# O Whisper às vezes escreve "code" como "código", "cold", "cod", "coude".
_CODE = r"(?:code|codigo|cod|cold|coud|coude|codi|kode|coud)"
_ENTRA = re.compile(rf"^(?:jarvis |friday )?(?:(?:entra|entrar|abre|abrir|liga|ligar|ativa|ativar|bora)(?: (?:pro|pra|para|em|n))? )?"
                    rf"modo {_CODE}(?: (?:em|pro|pra|para|n|d))?(?: projeto)? (?P<projeto>.+)$")
_SAI = re.compile(rf"^(?:jarvis |friday )?(?:sai|sair|fecha|fechar|desliga|desligar|desativa|desativar|termina|encerra)"
                  rf"(?: d)? modo {_CODE}$")
# Projeto novo (10/11/2026): "Jarvis, cria um projeto novo chamado Pressure",
# "modo code num projeto novo chamado X", "novo projeto X".
_NOVO = re.compile(rf"^(?:jarvis |friday )?(?:(?:cria|criar|crie|abre|abrir|faz|fazer|comeca|comecar|bora|quero)"
                   rf"(?: (?:um|uma))? )?(?:modo {_CODE} (?:n|num|em|pro|pra|para) )?(?:projeto novo|novo projeto)"
                   rf"(?: (?:chamado|que se chama|com nome|de nome|nome))?(?: (?P<nome>.+))?$")
_TROCA = re.compile(r"^(?:jarvis |friday )?(?:troca|trocar|muda|mudar|vai)(?: (?:pro|pra|para|o|de))?(?: projeto)? (?P<projeto>.+)$")


def comando_code(falado: str, em_code: bool) -> tuple[str, str] | None:
    """("entrar", projeto) | ("trocar", projeto) | ("sair", "") | None.
    "Troca pro X" só vale dentro do modo code, e só se X for um projeto: quem
    chama confere ("troca a música" não é projeto e segue pro Claude)."""
    t = normalizar(falado)
    if _SAI.match(t):
        return ("sair", "")
    m = _NOVO.match(t)
    if m:
        return ("novo", _nome_falado(falado) if m["nome"] else "")
    m = _ENTRA.match(t)
    if m:
        return ("entrar", m["projeto"])
    m = _TROCA.match(t) if em_code else None
    if m:
        return ("trocar", m["projeto"])
    return None


def _nome_falado(falado: str) -> str:
    """O nome do projeto como ele falou (com maiúscula e acento), depois de
    "chamado"/"nome"/"novo"/"projeto"."""
    texto = falado.strip().rstrip(".!?")
    for marca in (r"\bque se chama\b", r"\bchamad[oa]\b", r"\bde nome\b", r"\bcom (?:o )?nome\b", r"\bnome\b",
                  r"\bprojeto novo\b", r"\bnovo projeto\b"):
        achou = list(re.finditer(marca, texto, re.IGNORECASE))
        if achou:
            return texto[achou[-1].end():].strip(" ,:;\"'")
    return ""
