"""O cérebro: o Claude Code inteiro, pelo Agent SDK, com o login da assinatura.

Decisão do Léo (out/2026): "quero que o Jarvis SEJA o Claude Code". Sai o
roteador com 11 ferramentas fechadas; entra a mesma sessão de agente do VS
Code (Bash, arquivos, Playwright, Gmail, Agenda, Drive, imagens), que entende,
decide, faz e pergunta quando é sério.

**Como conversa com o ciclo de voz.** O agente roda numa thread própria, com
um laço asyncio. Uma tarefa pode levar minutos e fazer perguntas no meio, então
nada aqui bloqueia o microfone: o ciclo manda falas por `pedir()` e recolhe o
que sai pela fila `saidas`:

    falar      texto curto no meio da tarefa ("Beleza, vou procurar.")
    mostrar    texto para a janela, sem voz
    atividade  ferramenta que ele está usando (janela e log)
    perguntar  pergunta FALADA; o ciclo devolve a resposta em `Saida.resposta`
    fim        a resposta final (`texto` vira voz, `janela` vai para a janela)
    erro       limite, sem internet, Claude fora

**Permissão por voz.** O modo é "auto": o próprio Claude julga o que roda
direto (medido: leu a pasta antes de apagar, e apagou só o pedido). O que ele
achar sério vira `AskUserQuestion`, que passa por `_pode` e vira pergunta
falada. Testado: a pergunta chega aqui mesmo no modo auto.

Uso pessoal só: a Anthropic não permite oferecer o login do claude.ai num
produto para outras pessoas.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import datetime as dt
import json
import queue
import re
import shutil
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient,
                              PermissionResultAllow, PermissionResultDeny, RateLimitEvent,
                              ResultMessage, TextBlock, ToolUseBlock)

from jarvis.nucleo import relogio
from jarvis.nucleo.atalhos import normalizar

from . import ferramentas

PERSONA = Path(__file__).with_name("persona.md")
CALADO = "[calado]"

# Resposta falada a uma pergunta dele. "Não" vem primeiro: "não pode" tem "pode".
_NAO = {"nao", "para", "cancela", "deixa", "negativo", "esquece", "nem", "nunca"}
_SIM = {"pode", "sim", "manda", "vai", "beleza", "ok", "okay", "faz", "claro", "isso",
        "bora", "confirma", "confirmo", "positivo", "uhum", "aham", "fechou", "certo",
        "yes", "apaga", "pode ir", "vai la"}


def sim_ou_nao(falado: str) -> bool | None:
    palavras = normalizar(falado).split()
    if any(p in _NAO for p in palavras):
        return False
    if any(p in _SIM for p in palavras):
        return True
    return None


def internet_ok(timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection(("api.anthropic.com", 443), timeout=timeout):
            return True
    except OSError:
        return False


class ErroDoAgente(Exception):
    """O Claude Code não subiu (não instalado, sem login, sem rede na subida)."""


@dataclass
class Saida:
    tipo: str
    texto: str = ""
    titulo: str = ""
    janela: str | None = None
    opcoes: list[str] = field(default_factory=list)
    resposta: concurrent.futures.Future | None = None
    interrompido: bool = False


@dataclass
class Limite:
    status: str = "desconhecido"       # "allowed", "allowed_warning", "rejected"
    volta_em: float | None = None
    uso: float | None = None           # 0 a 1, da janela que vale agora


# -- a resposta final: o que vira voz e o que vai para a janela ---------------

_MARKDOWN = re.compile(r"[*_`#>]+")


def _limpar(texto: str) -> str:
    return " ".join(_MARKDOWN.sub("", texto).split())


def _tem_codigo(texto: str) -> bool:
    """Código e tabela não se falam: vão para a janela."""
    return "```" in texto or any(l.lstrip().startswith("|") for l in texto.splitlines())


def _formatado(texto: str) -> bool:
    return _tem_codigo(texto) or any(
        re.match(r"\s*([-*•]|#+|\d+[.)])\s", l) for l in texto.splitlines())


def _falavel(texto: str) -> str:
    """O texto como se fala: sem código nem tabela, e cada item de lista ou
    título vira uma frase."""
    sem_codigo = re.sub(r"```.*?```", "", texto, flags=re.S)
    frases = []
    for linha in sem_codigo.splitlines():
        s = linha.strip()
        if not s or s.startswith("|"):
            continue
        s = re.sub(r"^([-*•]|#+|\d+[.)])\s+", "", s)
        s = s[:1].upper() + s[1:]
        if s and not re.search(r"[.!?…:;]$", s):
            s += "."
        frases.append(s)
    return _limpar(" ".join(frases))


def dividir(texto: str, deixei: str = "Deixei na janela.") -> tuple[str, str | None]:
    """(fala, janela). Fala TUDO o que o Claude escreveu (pedido do Léo,
    20/10/2026: "se ele pode escrever tanto, por que não pode falar tanto?";
    o curto é o estilo dele, não um corte). A janela fica com o que não se
    fala (código, tabela) e com o texto formatado, quando há lista.

    A 1ª versão cortava a fala em duas frases e dizia "o resto tá na janela"."""
    t = texto.strip()
    if not t or t.endswith(CALADO):
        return "", None
    if not _formatado(t):
        return _limpar(t), None
    fala = _falavel(t)
    if _tem_codigo(t):
        fala = f"{fala} O código tá na janela." if fala else deixei
    return fala, t


def _resumo_de_ferramenta(b: ToolUseBlock) -> str:
    e = b.input or {}
    detalhe = e.get("description") or e.get("command") or e.get("file_path") \
        or e.get("url") or e.get("pattern") or e.get("query") or ""
    nome = b.name.removeprefix("mcp__").replace("__", ": ")
    return f"{nome} — {str(detalhe)[:160]}" if detalhe else nome


def _casar_opcao(falado: str, opcoes: list[str]) -> str:
    """A opção que ele disse, ou a fala inteira (resposta livre)."""
    alvo = normalizar(falado)
    for o in opcoes:
        n = normalizar(o)
        if n and (n in alvo or alvo in n):
            return o
    ordinais = {"primeiro": 0, "primeira": 0, "segundo": 1, "segunda": 1,
                "terceiro": 2, "terceira": 2, "quarto": 3, "quarta": 3}
    for palavra, i in ordinais.items():
        if palavra in alvo.split() and i < len(opcoes):
            return opcoes[i]
    sn = sim_ou_nao(falado)
    if sn is not None and len(opcoes) == 2:
        # Pergunta de sim ou não com rótulos próprios ("Apagar" / "Deixar").
        return opcoes[0] if sn else opcoes[1]
    return falado


class Agente:
    def __init__(self, cfg, nome: str, *, whatsapp=None, persona_cfg=None) -> None:
        self.cfg = cfg
        self.nome = nome
        self.persona_cfg = persona_cfg
        self.whatsapp = whatsapp
        self.casa = Path(cfg.casa).expanduser()
        self.binario = shutil.which(str(Path(cfg.binario).expanduser())) or cfg.binario
        self.saidas: queue.Queue[Saida] = queue.Queue()
        self.ocupado = False
        self.limite = Limite()
        self.offline = False
        # O que o Léo falou desde que a tarefa começou (pedido, correções e
        # respostas). É o que a trava de envio do WhatsApp olha.
        self._falas: list[str] = []
        # (pessoa, quando, texto) do que o Jarvis mandou no WhatsApp: os
        # avisos usam para separar o que veio do celular.
        self.enviados_whats: list[tuple[str, dt.datetime, str]] = []
        self._cliente: ClaudeSDKClient | None = None
        self._leitor: asyncio.Task | None = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True,
                                        name="agente")
        self._marca = self.casa / ".ultimo-uso"

    # -- ciclo de vida -----------------------------------------------------

    def iniciar(self) -> float:
        """Sobe o Claude Code e espera ele ficar pronto. Devolve os segundos."""
        inicio = time.monotonic()
        self.casa.mkdir(parents=True, exist_ok=True)
        self._thread.start()
        # Continua a conversa de antes se ela parou há pouco (desligar e ligar
        # o Jarvis não apaga o papo); senão, começa outra.
        continuar = self._marca.exists() and \
            time.time() - self._marca.stat().st_mtime < self.cfg.recomecar_apos_h * 3600
        if not Path(self.binario).is_file():
            raise ErroDoAgente(f"Claude Code não encontrado em {self.binario}.\n"
                               "  Instale: curl -fsSL https://claude.ai/install.sh | bash")
        try:
            self._rodar(self._conectar(continuar), espera=90)
        except Exception as e:
            # Sem rede na subida o Jarvis sobe assim mesmo: o primeiro pedido
            # tenta de novo e, sem rede, vira a fala de "sem internet".
            self._cliente = None
            self.offline = not internet_ok()
            if not self.offline:
                raise ErroDoAgente(f"o Claude Code não subiu: {e}") from e
        return time.monotonic() - inicio

    def encerrar(self) -> None:
        try:
            self._rodar(self._desconectar(), espera=10)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)

    def _rodar(self, corrotina, espera: float | None = None):
        fut = asyncio.run_coroutine_threadsafe(corrotina, self._loop)
        return fut.result(espera) if espera is not None else fut

    def _opcoes(self, continuar: bool) -> ClaudeAgentOptions:
        servidor = ferramentas.criar_servidor(
            mostrar=lambda titulo, texto: self.saidas.put(Saida("mostrar", texto, titulo)),
            whatsapp=self.whatsapp,
            falas_do_pedido=lambda: list(self._falas),
            ao_mandar=self._mandou_whats,
        )
        return ClaudeAgentOptions(
            cli_path=self.binario,
            cwd=str(self.casa),
            model=self.cfg.modelo,
            effort=self.cfg.effort,
            # "user": os MCPs, skills e preferências do Léo, iguais ao VS Code.
            # "project": o CLAUDE.md da casa, que é a memória dele.
            setting_sources=["user", "project"],
            permission_mode=self.cfg.modo_permissao,
            can_use_tool=self._pode,
            system_prompt={"type": "preset", "preset": "claude_code",
                           "append": PERSONA.read_text().replace("{nome}", self.nome)},
            mcp_servers={"jarvis": servidor},
            continue_conversation=continuar,
            stderr=lambda _linha: None,
            # Uma foto aberta pelo Read volta numa mensagem só, em base64. O
            # padrão (1 MB) quebrava a conexão com uma foto de 2 MB do
            # celular ("JSON message exceeded maximum buffer size", 20/10/2026).
            max_buffer_size=64 * 1024 * 1024,
        )

    async def _conectar(self, continuar: bool = False) -> None:
        self._cliente = ClaudeSDKClient(self._opcoes(continuar))
        try:
            await self._cliente.connect()
        except Exception:
            if not continuar:
                raise
            # A sessão de antes sumiu ou não abriu: começa uma nova.
            self._cliente = ClaudeSDKClient(self._opcoes(False))
            await self._cliente.connect()
        self._leitor = asyncio.create_task(self._ler(self._cliente))

    async def _desconectar(self) -> None:
        cliente, self._cliente = self._cliente, None
        if self._leitor is not None:
            self._leitor.cancel()
        if cliente is not None:
            await cliente.disconnect()

    # -- o que o ciclo chama ----------------------------------------------

    def pedir(self, texto: str, origem: str = "voz", contexto: str = "") -> None:
        """Manda uma fala. Com uma tarefa em andamento, ela entra NA tarefa
        (medido: o Claude incorpora a fala nova e responde as duas coisas)."""
        if not self.ocupado:
            self._falas = []
        self._falas.append(texto)
        self.ocupado = True
        agora = dt.datetime.now()
        cabecalho = f"[{origem}, {relogio.data_curta(agora.date())}, {agora:%H:%M}]"
        mensagem = "\n".join(p for p in (cabecalho, contexto, texto) if p)
        self._rodar(self._enviar(mensagem))

    def interromper(self) -> None:
        if self._cliente is not None and self.ocupado:
            self._rodar(self._cliente.interrupt())

    def responder(self, saida: Saida, falado: str | None) -> None:
        """A resposta dele a uma pergunta (None: não respondeu a tempo)."""
        if falado:
            self._falas.append(falado)
        if saida.resposta is not None and not saida.resposta.done():
            saida.resposta.set_result(falado)

    def situacao(self) -> dict:
        """{"tipo": "ok"|"limite"|"offline", "volta_em": época|None, "uso_5h": 0-1}"""
        agora = time.time()
        if self.offline:
            tipo = "offline"
        elif self.limite.status == "rejected" and (self.limite.volta_em or agora + 1) > agora:
            tipo = "limite"
        else:
            tipo = "ok"
        return {"tipo": tipo, "volta_em": self.limite.volta_em, "uso_5h": self.limite.uso}

    def conferir_internet(self) -> None:
        if self.offline and internet_ok():
            self.offline = False

    def memoria_para_janela(self) -> dict:
        """O painel "memória": os itens do CLAUDE.md da casa."""
        arquivo = self.casa / "CLAUDE.md"
        try:
            linhas = arquivo.read_text().splitlines()
        except OSError:
            linhas = []
        fatos = [l.lstrip("-* ").strip() for l in linhas if l.lstrip().startswith(("- ", "* "))]
        return {"fatos": fatos, "conversas": []}

    # -- por dentro ---------------------------------------------------------

    async def _enviar(self, mensagem: str) -> None:
        try:
            parada = time.time() - self._marca.stat().st_mtime if self._marca.exists() else 0
            if self._cliente is not None and parada > self.cfg.recomecar_apos_h * 3600:
                await self._desconectar()  # muito tempo parado: conversa nova
            if self._cliente is None:
                await self._conectar()
            self._marca.touch()
            await self._cliente.query(mensagem)
        except Exception as e:
            self._falhou(e)

    def _falhou(self, erro: Exception | str) -> None:
        self.ocupado = False
        self.offline = not internet_ok()
        self.saidas.put(Saida("erro", "offline" if self.offline else "falhou",
                              titulo=str(erro)[:300]))

    async def _ler(self, cliente: ClaudeSDKClient) -> None:
        pendente: str | None = None  # texto que pode ser o final ou um aviso no meio

        def no_meio(texto: str) -> None:
            t = texto.strip()
            if not t or t.endswith(CALADO):
                return
            fala, janela = dividir(t)
            if janela:
                self.saidas.put(Saida("mostrar", janela))
            if fala:
                self.saidas.put(Saida("falar", fala))

        try:
            async for m in cliente.receive_messages():
                if isinstance(m, AssistantMessage):
                    if m.parent_tool_use_id:  # dentro de um subagente: só ele vê
                        continue
                    if m.error == "rate_limit":
                        self.limite.status = "rejected"
                    for b in m.content:
                        if isinstance(b, TextBlock):
                            if pendente:
                                no_meio(pendente)
                            pendente = b.text
                        elif isinstance(b, ToolUseBlock):
                            if pendente:
                                no_meio(pendente)
                            pendente = None
                            if b.name != "AskUserQuestion":
                                self.saidas.put(Saida("atividade", _resumo_de_ferramenta(b)))
                elif isinstance(m, RateLimitEvent):
                    info = m.rate_limit_info
                    self.limite = Limite(info.status, info.resets_at, info.utilization)
                elif isinstance(m, ResultMessage):
                    final, pendente = (pendente if pendente is not None else m.result or ""), None
                    self.ocupado = False
                    self.offline = False
                    motivo = getattr(m, "terminal_reason", None) or ""
                    if motivo.startswith("aborted"):
                        self.saidas.put(Saida("fim", interrompido=True))
                    elif m.is_error and self.limite.status == "rejected":
                        self.saidas.put(Saida("erro", "limite"))
                    elif m.is_error and not final:
                        self._falhou(m.result or m.subtype)
                    else:
                        fala, janela = dividir(final)
                        self.saidas.put(Saida("fim", fala, janela=janela))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # O Claude Code caiu: o próximo pedido sobe outro.
            self._cliente = None
            self._falhou(e)

    async def _perguntar(self, texto: str, opcoes: list[str]) -> str | None:
        fut: concurrent.futures.Future = concurrent.futures.Future()
        self.saidas.put(Saida("perguntar", texto, opcoes=opcoes, resposta=fut))
        return await asyncio.wrap_future(fut)

    async def _pode(self, nome: str, entrada: dict, _ctx):
        """Toda pergunta e todo pedido de permissão viram VOZ."""
        sem_resposta = ("O usuário não respondeu a tempo (pode não ter ouvido, ou não "
                        "estar perto). Não faça; diga em uma frase que deixou sem fazer.")
        if nome == "AskUserQuestion":
            respostas = {}
            for q in entrada.get("questions") or []:
                opcoes = [str(o.get("label") or "") for o in q.get("options") or []]
                falado = await self._perguntar(str(q.get("question") or ""), opcoes)
                if not falado:
                    return PermissionResultDeny(message=sem_resposta)
                respostas[q.get("question")] = _casar_opcao(falado, opcoes)
            return PermissionResultAllow(updated_input={**entrada, "answers": respostas})

        # Permissão comum (o modo auto quase não pede, mas pode).
        self.saidas.put(Saida("mostrar", f"```\n{json.dumps(entrada, ensure_ascii=False, indent=1)[:2000]}\n```",
                              titulo=f"Pedido de permissão: {nome}"))
        o_que = str(entrada.get("description") or "").strip().rstrip(".")
        pergunta = (f"Preciso da tua permissão: {o_que[0].lower() + o_que[1:]}. Pode?"
                    if o_que else "Preciso da tua permissão pro que tá na janela. Pode?")
        falado = await self._perguntar(pergunta, ["Pode", "Não"])
        if not falado:
            return PermissionResultDeny(message=sem_resposta)
        sn = sim_ou_nao(falado)
        if sn:
            return PermissionResultAllow()
        if sn is False:
            return PermissionResultDeny(message="O usuário disse não.")
        return PermissionResultDeny(
            message=f"O usuário não autorizou e disse: «{falado}». Siga o que ele disse.")

    def _mandou_whats(self, jid: str, nome: str, texto: str) -> None:
        pessoa = self.whatsapp.pessoa(jid) if self.whatsapp else nome
        self.enviados_whats = (self.enviados_whats + [(pessoa, dt.datetime.now(), texto)])[-50:]
