"""O cérebro de nuvem: o Claude Opus 5.5, pelo Claude Code com o login do Léo.

Substitui o qwen local (decisão do Léo, out/2026): o qwen ocupava 1,6 GB de
RAM e 5,6 GB da placa, e o Opus entende e conversa muito melhor. O preço é a
latência (~1 a 3 s em vez de ~0,5 s) e precisar de internet — por isso o que
é comando fixo continua nas listas fechadas do núcleo, sem modelo nenhum.

**Como fala com o Claude.** `claude -p` em modo stream-json, com o processo
ABERTO: a primeira pergunta paga ~1 s de subida do programa, as seguintes não
(medido: 1,0 a 1,2 s por resposta curta com o processo quente). O login é o da
assinatura (sem `--bare`, que exigiria chave de API). Só para uso pessoal: a
Anthropic não permite oferecer o login do claude.ai num produto para outras
pessoas.

Duas sessões:
- **conversa**: escolhe a ferramenta ou responde, e lembra do que foi dito
  enquanto o Jarvis está acordado. Recomeça quando ele dorme.
- **avulsa**: perguntas soltas (sim/não de confirmação, correção de nome,
  detalhe de música). Uma pergunta por processo, para um assunto não vazar
  no outro; o próximo já sobe em segundo plano e fica esperando.

**Limite e internet.** Toda resposta traz o estado do limite da assinatura
(`rate_limit_event`: quanto foi usado e quando volta). Limite batido vira
`LimiteAtingido(volta_em)`; sem conexão vira `SemInternet`. O núcleo
transforma os dois em fala e em aviso na janela.
"""

from __future__ import annotations

import json
import queue
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .cerebro import FERRAMENTAS, Confirmacao, ErroDoCerebro, Interpretacao

# Pasta vazia de onde o Claude Code roda: sem ela ele carregaria o CLAUDE.md
# e as configurações do projeto em que estivesse.
_PASTA = Path("~/.cache/jarvis-claude").expanduser()


class LimiteAtingido(ErroDoCerebro):
    def __init__(self, volta_em: float | None) -> None:
        super().__init__("limite da assinatura atingido")
        self.volta_em = volta_em  # época, em segundos; None se não veio


class SemInternet(ErroDoCerebro):
    pass


def internet_ok(timeout: float = 1.5) -> bool:
    """Consegue abrir conexão com a API? Rápido, e só roda quando algo falha."""
    try:
        with socket.create_connection(("api.anthropic.com", 443), timeout=timeout):
            return True
    except OSError:
        return False


@dataclass
class Limite:
    """O último estado do limite que o Claude informou."""
    status: str = "desconhecido"       # "allowed", "allowed_warning", "rejected"…
    volta_em: float | None = None
    uso_5h: float | None = None        # 0 a 1
    uso_semana: float | None = None


class _Sessao:
    """Um `claude -p` aberto, falando JSON por linha."""

    def __init__(self, binario: str, modelo: str, effort: str, sistema: str,
                 ao_limite) -> None:
        _PASTA.mkdir(parents=True, exist_ok=True)
        self._ao_limite = ao_limite
        self._fila: queue.Queue = queue.Queue()
        self.proc = subprocess.Popen(
            [binario, "-p", "--input-format", "stream-json",
             "--output-format", "stream-json", "--verbose",
             "--model", modelo, "--effort", effort,
             "--system-prompt", sistema, "--tools", "",
             "--strict-mcp-config", "--no-session-persistence"],
            cwd=_PASTA, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
            start_new_session=True,
        )
        threading.Thread(target=self._ler, daemon=True).start()

    def _ler(self) -> None:
        for linha in self.proc.stdout:
            try:
                ev = json.loads(linha)
            except ValueError:
                continue
            if ev.get("type") == "rate_limit_event":
                self._ao_limite(ev.get("rate_limit_info") or {})
            self._fila.put(ev)
        self._fila.put({"type": "_morreu"})

    def viva(self) -> bool:
        return self.proc.poll() is None

    def perguntar(self, texto: str, timeout: float) -> str:
        if not self.viva():
            raise ErroDoCerebro("o Claude Code fechou")
        msg = {"type": "user", "message": {"role": "user", "content": texto}}
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        fim = time.monotonic() + timeout
        sem_resposta = 0
        while True:
            try:
                ev = self._fila.get(timeout=max(0.1, fim - time.monotonic()))
            except queue.Empty:
                raise SemInternet("sem resposta") if not internet_ok() \
                    else ErroDoCerebro("o Claude demorou demais")
            tipo = ev.get("type")
            if tipo == "_morreu":
                raise ErroDoCerebro("o Claude Code fechou no meio da resposta")
            if tipo == "rate_limit_event":
                info = ev.get("rate_limit_info") or {}
                if info.get("status") == "rejected":
                    raise LimiteAtingido(info.get("resetsAt"))
            if tipo == "system" and ev.get("subtype") == "api_retry":
                if ev.get("error") == "rate_limit":
                    raise LimiteAtingido(None)
                # Tentativa sem resposta nenhuma da API: confere a rede já,
                # em vez de esperar as novas tentativas esgotarem.
                if ev.get("error_status") is None or ev.get("no_response"):
                    sem_resposta += 1
                    if sem_resposta >= 1 and not internet_ok():
                        raise SemInternet("sem conexão")
            if tipo == "result":
                if ev.get("is_error"):
                    texto_erro = str(ev.get("result") or "")
                    if "limit" in texto_erro.lower():
                        raise LimiteAtingido(None)
                    if not internet_ok():
                        raise SemInternet(texto_erro)
                    raise ErroDoCerebro(texto_erro or "erro do Claude")
                return str(ev.get("result") or "")

    def fechar(self) -> None:
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.terminate()
        except OSError:
            pass


# --- os prompts -------------------------------------------------------------

def _ferramentas_em_texto() -> str:
    linhas = []
    for f in FERRAMENTAS:
        fn = f["function"]
        linhas.append(json.dumps({"nome": fn["name"], "descricao": fn["description"],
                                  "parametros": fn["parameters"]}, ensure_ascii=False))
    return "\n".join(linhas)


def _sistema_conversa(nome: str) -> str:
    return (
        f"Você é {nome}, assistente de voz que roda no PC do usuário, com Linux. "
        "Ele fala com você em voz alta; o texto chega transcrito (pode ter erro "
        "de transcrição: interprete pela intenção).\n\n"
        "A cada mensagem, decida: ou uma das ferramentas abaixo resolve o pedido, "
        "ou você responde conversando. Responda SEMPRE e SÓ com um objeto JSON, "
        "sem nada antes ou depois:\n"
        '{"funcao": "<nome da ferramenta>" ou null, "argumentos": {...}, '
        '"fala": "<o que dizer>"}\n'
        "- Com ferramenta: preencha funcao e argumentos seguindo o schema dela; "
        "a fala pode ficar vazia (quem fala o resultado é o sistema).\n"
        "- Sem ferramenta: funcao null, argumentos {}, e a fala é a resposta.\n"
        "- O microfone fica aberto um tempo depois de cada resposta, e pega o "
        "que estiver tocando ou sendo dito na sala. Se a fala CLARAMENTE não é "
        "para você (narração de vídeo, TV, música, alguém conversando com outra "
        "pessoa), responda funcao null e fala vazia \"\": você fica calado. Na "
        "dúvida, responda normalmente.\n"
        "O sistema executa a ferramenta de verdade e responde ao usuário; você "
        "vê essa resposta na mensagem seguinte, em [O sistema respondeu]. Cada "
        "pedido é um pedido novo: se ele repetir um comando, chame a ferramenta "
        "de novo.\n\n"
        "Regras da fala: português do Brasil, falado e natural, curto (uma ou "
        "duas frases: é voz). Sem listas, sem markdown, sem emoji. Nem formal, "
        "nem cheio de gíria. Não dê conselho nem comente o estado do usuário "
        "(cansaço, sono, humor) sem ele pedir. Não invente fatos sobre ele: o "
        "que você sabe dele vem da memória que acompanha cada mensagem. Se ele "
        "pedir para FAZER algo que nenhuma ferramenta faz, diga em uma frase que "
        "isso você ainda não consegue fazer.\n\n"
        "Ferramentas (uma por linha):\n" + _ferramentas_em_texto()
    )


_SISTEMA_AVULSO = (
    "Você é um classificador e extrator de texto para um assistente de voz em "
    "português. Cada mensagem traz uma instrução e uma frase. Siga a instrução "
    "e responda SÓ o que ela pede, sem explicação."
)


def _json_da_resposta(texto: str) -> dict:
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        texto = texto[texto.find("{"):]
    ini, fim = texto.find("{"), texto.rfind("}")
    if ini < 0 or fim < 0:
        return {"funcao": None, "argumentos": {}, "fala": texto}
    try:
        return json.loads(texto[ini:fim + 1])
    except ValueError:
        return {"funcao": None, "argumentos": {}, "fala": texto}


class CerebroClaude:
    """Mesma cara do `Cerebro` (qwen): o núcleo não precisa saber qual é."""

    def __init__(self, binario: str, modelo: str, effort: str, timeout_s: float,
                 nome: str) -> None:
        self.binario = str(Path(binario).expanduser())
        self.modelo, self.effort, self.timeout_s = modelo, effort, timeout_s
        self.nome = nome
        self.limite = Limite()
        self._offline = False
        self._trava = threading.Lock()
        self._conversa: _Sessao | None = None
        self._avulsa: _Sessao | None = None
        # Dados que acompanham cada mensagem da conversa (o núcleo preenche).
        self.contexto = lambda: ""

    # -- ciclo de vida -------------------------------------------------------

    def _ao_limite(self, info: dict) -> None:
        janelas = info.get("unifiedWindows") or {}
        self.limite = Limite(
            status=str(info.get("status") or "desconhecido"),
            volta_em=info.get("resetsAt"),
            uso_5h=(janelas.get("five_hour") or {}).get("utilization"),
            uso_semana=(janelas.get("seven_day") or {}).get("utilization"),
        )

    def _nova(self, sistema: str) -> _Sessao:
        return _Sessao(self.binario, self.modelo, self.effort, sistema, self._ao_limite)

    def conferir(self) -> None:
        if not (shutil.which(self.binario) or Path(self.binario).is_file()):
            raise ErroDoCerebro(
                f"Claude Code não encontrado em {self.binario}.\n"
                "  Instale: curl -fsSL https://claude.ai/install.sh | bash")

    def usar_atalhos(self, nomes: list[str]) -> None:
        pass  # o Opus não precisa da lista no prompt: o casamento é em Python

    def carregar(self) -> float:
        """Sobe as duas sessões e faz uma pergunta de aquecimento, esperando."""
        inicio = time.monotonic()
        with self._trava:
            self._conversa = self._nova(_sistema_conversa(self.nome))
            self._avulsa = self._nova(_SISTEMA_AVULSO)
        try:
            self._avulsa.perguntar("Instrução: responda só OK. Frase: teste", 60)
            self._trocar_avulsa()
        except ErroDoCerebro:
            pass  # sem internet na subida: o Jarvis sobe assim mesmo
        return time.monotonic() - inicio

    def aquecer(self) -> None:
        """Ao acordar: garante as sessões vivas, sem esperar."""
        with self._trava:
            if self._conversa is None or not self._conversa.viva():
                self._conversa = self._nova(_sistema_conversa(self.nome))
            if self._avulsa is None or not self._avulsa.viva():
                self._avulsa = self._nova(_SISTEMA_AVULSO)

    def recomecar_conversa(self) -> None:
        """Ele dormiu: a próxima conversa começa do zero (em segundo plano)."""
        velha = self._conversa
        self._conversa = self._nova(_sistema_conversa(self.nome))
        if velha is not None:
            velha.fechar()

    def _trocar_avulsa(self) -> None:
        velha = self._avulsa
        self._avulsa = self._nova(_SISTEMA_AVULSO)
        if velha is not None:
            velha.fechar()

    # -- situação (para o aviso na janela) -----------------------------------

    def situacao(self) -> dict:
        """{"tipo": "ok"|"limite"|"offline", "volta_em": época|None, "uso_5h": 0-1}"""
        agora = time.time()
        # Sem internet ganha: sem ela nada chega ao Claude, com limite ou não.
        if self._offline:
            tipo = "offline"
        elif self.limite.status == "rejected" and (self.limite.volta_em or agora + 1) > agora:
            tipo = "limite"
        else:
            tipo = "ok"
        return {"tipo": tipo, "volta_em": self.limite.volta_em,
                "uso_5h": self.limite.uso_5h, "uso_semana": self.limite.uso_semana}

    def conferir_internet(self) -> bool:
        """Para sair do aviso de offline sem esperar o próximo pedido."""
        if self._offline and internet_ok():
            self._offline = False
        return not self._offline

    def _registrar(self, chamada, *args):
        try:
            r = chamada(*args)
        except SemInternet:
            self._offline = True
            raise
        except LimiteAtingido as e:
            self._offline = False
            self.limite.status = "rejected"
            if e.volta_em:
                self.limite.volta_em = e.volta_em
            raise
        self._offline = False
        return r

    # -- perguntas -----------------------------------------------------------

    def _avulso(self, instrucao: str, frase: str) -> str:
        if self._avulsa is None or not self._avulsa.viva():
            self._avulsa = self._nova(_SISTEMA_AVULSO)
        try:
            return self._registrar(self._avulsa.perguntar,
                                   f"Instrução: {instrucao}\nFrase: {frase}",
                                   self.timeout_s).strip()
        finally:
            self._trocar_avulsa()

    def interpretar(self, frase: str) -> Interpretacao:
        if self._conversa is None or not self._conversa.viva():
            self._conversa = self._nova(_sistema_conversa(self.nome))
        inicio = time.monotonic()
        extra = self.contexto()
        texto = f"{extra}\nFala do usuário: {frase}" if extra else frase
        d = _json_da_resposta(self._registrar(self._conversa.perguntar, texto, self.timeout_s))
        funcao = d.get("funcao") or None
        nomes = {f["function"]["name"] for f in FERRAMENTAS}
        if funcao not in nomes:
            funcao = None
        return Interpretacao(funcao, d.get("argumentos") or {} if funcao else {},
                             time.monotonic() - inicio, fala=str(d.get("fala") or "").strip())

    def detalhar_musica(self, frase: str) -> Interpretacao:
        inicio = time.monotonic()
        texto = self._avulso(
            "Você perguntou qual música o usuário quer, e a frase é a resposta. "
            'Responda só um JSON: {"o_que": "<nome da música>", "onde": '
            '"navegador" se ele falar de YouTube/navegador/ver, senão "audio"}. '
            'Se não for nome de música, responda {"o_que": ""}.', frase)
        d = _json_da_resposta(texto)
        o_que = str(d.get("o_que") or "").strip()
        if not o_que:
            return Interpretacao(None, {}, time.monotonic() - inicio)
        onde = "navegador" if d.get("onde") == "navegador" else "audio"
        return Interpretacao("tocar", {"o_que": o_que, "onde": onde},
                             time.monotonic() - inicio)

    def corrigir(self, frase: str) -> str | None:
        texto = self._avulso(
            "O usuário está corrigindo um pedido que você entendeu errado. Se ele "
            "disse qual é a coisa certa, responda APENAS o nome dela, sem verbo e "
            "sem artigo. Se só negou sem dizer o que queria, responda NADA.", frase)
        if not texto or texto.upper().startswith("NADA"):
            return None
        return texto.strip(" .\"'")

    def confirmar(self, frase: str, pergunta: str) -> Confirmacao:
        texto = self._avulso(
            f'Você perguntou ao usuário: "{pergunta}". Classifique a frase dele '
            "com uma palavra só: SIM (concordou: 'pode', 'manda', 'isso', 'beleza', "
            "'claro', 'aham'...), NAO (recusou ou corrigiu essa pergunta), ou OUTRO "
            "(pedido novo, outra pergunta, ou sem relação; na dúvida entre NAO e "
            "OUTRO, OUTRO). Pontuação e maiúsculas não mudam nada.", frase).upper()
        if texto.startswith("SIM"):
            return Confirmacao.SIM
        if texto.startswith("NAO") or texto.startswith("NÃO"):
            return Confirmacao.NAO
        return Confirmacao.OUTRO

    def resposta_solta(self, frase: str) -> bool:
        texto = self._avulso(
            "A frase foi dita sem nenhuma pergunta pendente. Responda SOLTA se ela "
            "é só uma concordância ou recusa sem pedido próprio ('sim', 'pode', "
            "'não', 'deixa pra lá'), ou OUTRO para qualquer outra coisa.", frase)
        return texto.upper().startswith("SOLTA")
