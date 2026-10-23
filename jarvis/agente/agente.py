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
    sessao     a conversa mudou (`texto` = id; `janela` = "nova" ou "continuada")
    parcial    um pedaço do texto enquanto ele escreve (`texto` = o pedaço,
               `titulo` = o número do bloco; `janela` = "descartar": jogue
               fora o que veio, o rápido passou para o Opus)

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
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, HookMatcher,
                              PermissionResultAllow, PermissionResultDeny, RateLimitEvent,
                              ResultMessage, StreamEvent, TextBlock, ToolUseBlock)

from jarvis.agente import travas
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


# O dono do Jarvis: a voz que as travas reconhecem (jarvis/quem_fala.py).
def _dono() -> str:
    """O nome de quem usa (Ajustes, "Seu nome"); sem nome, "usuário"."""
    from jarvis import ajustes
    return ajustes.nome_de_quem_usa() or "usuário"

# O que dá para escolher na janela (out/2026). "auto" são os dois cérebros do
# config: o rápido atende e passa o pesado para o Opus.
MODELOS = ("auto", "haiku", "sonnet", "opus")
ESFORCOS = ("low", "medium", "high", "xhigh", "max")
SONNET = "claude-sonnet-5-5"


def etiqueta_da_voz(voz, dono: str | None = None) -> str:
    dono = dono or _dono()
    """O pedaço do cabeçalho que diz ao Claude quem falou (persona, "Outras vozes")."""
    if voz.quem == "leo":
        return f"voz do {dono}"
    if voz.quem == "outra":
        return f"voz de OUTRA pessoa, não do {dono} (nota {voz.nota:.2f})"
    return "fala curta demais para reconhecer a voz"


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
        # O uso da assinatura, das janelas de 5 h e da semana (o RateLimitEvent
        # traz as duas em `raw["unifiedWindows"]`): {"cinco_horas": {"uso":
        # 0-1, "volta_em": época}, "semana": {...}}. Vazio até o 1º pedido.
        self.uso: dict = {}
        self.offline = False
        # O que o Léo falou desde que a tarefa começou (pedido, correções e
        # respostas). É o que a trava de envio do WhatsApp olha.
        self._falas: list[str] = []
        # (pessoa, quando, texto) do que o Jarvis mandou no WhatsApp: os
        # avisos usam para separar o que veio do celular.
        self.enviados_whats: list[tuple[str, dt.datetime, str]] = []
        # Quem falou por último (jarvis/quem_fala.py): as travas da voz olham
        # isto. None = digitado ou sem o reconhecimento: vale como o Léo.
        self.voz = None
        # Pedido de bloquear a tela: o Ciclo bloqueia quando a fala terminar.
        self.bloquear_ao_terminar = False
        # Os dois cérebros (config [agente] modelo_rapido): o rápido atende; o
        # pedido pesado ele passa para o forte (ferramenta chamar_o_opus).
        self._subir = False     # o rápido pediu o Opus: ao fim do turno, troca
        self._no_opus = False   # o pedido atual está com o Opus
        # A conversa (sessão do Claude Code) aberta agora, e o modelo e o
        # esforço com que ela está rodando. O que o Léo escolhe na janela fica
        # em `cerebro` (e no disco) e vale a partir do próximo pedido.
        self.sessao: str | None = None
        self._modelo_atual = ""
        self._esforco_atual = ""
        self._arquivo_cerebro = self.casa.parent / "cerebro.json"
        self.cerebro = self._ler_cerebro()
        self._trava: asyncio.Lock | None = None
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
        # Cada vez que o Jarvis liga é um chat novo (pedido do Léo, 22/10/2026,
        # com a janela nova: as conversas antigas ficam na barra lateral e dá
        # para voltar a qualquer uma). Antes ele continuava a de menos de 3 h.
        if not Path(self.binario).is_file():
            raise ErroDoAgente(f"Claude Code não encontrado em {self.binario}.\n"
                               "  Instale: curl -fsSL https://claude.ai/install.sh | bash")
        try:
            self._rodar(self._conectar(), espera=90)
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

    def _opcoes(self, retomar: str | None) -> ClaudeAgentOptions:
        servidor = ferramentas.criar_servidor(
            mostrar=lambda titulo, texto: self.saidas.put(Saida("mostrar", texto, titulo)),
            whatsapp=self.whatsapp,
            falas_do_pedido=lambda: list(self._falas),
            ao_mandar=self._mandou_whats,
            chamar_o_opus=self._pedir_o_opus if self.cfg.modelo_rapido else None,
            bloquear_pc=self._bloquear_pc,
            pedir_desbloqueio=self._pedir_desbloqueio,
        )
        self._no_opus = False
        self._modelo_atual = self._modelo_desejado()
        self._esforco_atual = self.cerebro["esforco"]
        return ClaudeAgentOptions(
            cli_path=self.binario,
            cwd=str(self.casa),
            model=self._modelo_atual,
            effort=self._esforco_atual,
            # "user": os MCPs, skills e preferências do Léo, iguais ao VS Code.
            # "project": o CLAUDE.md da casa, que é a memória dele.
            setting_sources=["user", "project"],
            permission_mode=self.cfg.modo_permissao,
            can_use_tool=self._pode,
            # As travas da voz rodam antes de TODA ferramenta, inclusive no
            # modo auto (o can_use_tool quase nunca é chamado nele).
            hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[self._trava_da_voz])]},
            system_prompt={"type": "preset", "preset": "claude_code",
                           "append": self._instrucoes()},
            mcp_servers={"jarvis": servidor},
            # O texto em pedaços, enquanto ele escreve (a janela mostra; beta 0.5).
            include_partial_messages=True,
            # Conversa nova com id escolhido aqui (a janela precisa saber qual
            # é), ou uma antiga retomada pela barra lateral.
            session_id=None if retomar else self.sessao,
            resume=retomar,
            stderr=lambda _linha: None,
            # Uma foto aberta pelo Read volta numa mensagem só, em base64. O
            # padrão (1 MB) quebrava a conexão com uma foto de 2 MB do
            # celular ("JSON message exceeded maximum buffer size", 20/10/2026).
            max_buffer_size=64 * 1024 * 1024,
        )

    def _instrucoes(self) -> str:
        return PERSONA.read_text().replace("{nome}", self.nome).replace("{usuario}", _dono())

    async def _conectar(self, retomar: str | None = None) -> None:
        """Abre o Claude Code numa conversa nova, ou na `retomar` (um id)."""
        antes = self.sessao
        if not retomar:
            self.sessao = str(uuid.uuid4())
        self._cliente = ClaudeSDKClient(self._opcoes(retomar))
        try:
            await self._cliente.connect()
        except Exception:
            if not retomar:
                raise
            # A conversa de antes sumiu ou não abriu: começa uma nova.
            retomar, self.sessao = None, str(uuid.uuid4())
            self._cliente = ClaudeSDKClient(self._opcoes(None))
            await self._cliente.connect()
        if retomar:
            self.sessao = retomar
        self._leitor = asyncio.create_task(self._ler(self._cliente))
        # Reabrir a MESMA conversa (caiu, ou mudou o esforço) não é troca.
        if self.sessao != antes or not retomar:
            self.saidas.put(Saida("sessao", self.sessao, janela="continuada" if retomar else "nova"))

    async def _desconectar(self) -> None:
        cliente, self._cliente = self._cliente, None
        if self._leitor is not None:
            self._leitor.cancel()
        if cliente is not None:
            await cliente.disconnect()

    # -- o que o ciclo chama ----------------------------------------------

    def pedir(self, texto: str, origem: str = "voz", contexto: str = "", voz=None) -> None:
        """Manda uma fala. Com uma tarefa em andamento, ela entra NA tarefa
        (medido: o Claude incorpora a fala nova e responde as duas coisas).
        `voz`: quem falou (`quem_fala.Voz`); None = digitado, vale como o Léo."""
        if not self.ocupado:
            self._falas = []
        self._falas.append(texto)
        self.ocupado = True
        self.voz = voz
        agora = dt.datetime.now()
        quem = "" if voz is None else ", " + etiqueta_da_voz(voz)
        cabecalho = f"[{origem}, {relogio.data_curta(agora.date())}, {agora:%H:%M}{quem}]"
        mensagem = "\n".join(p for p in (cabecalho, contexto, texto) if p)
        self._rodar(self._enviar(mensagem))

    def interromper(self) -> None:
        if self._cliente is not None and self.ocupado:
            self._rodar(self._cliente.interrupt())

    # -- a janela: conversas e cérebro --------------------------------------

    def nova_conversa(self) -> bool:
        """Começa um chat novo. False com uma tarefa em andamento (ela seria
        cortada no meio). A troca chega pela saída "sessao"."""
        if self.ocupado:
            return False
        self._rodar(self._trocar(None))
        return True

    def continuar_conversa(self, sessao: str) -> bool:
        """Volta para uma conversa antiga (a barra lateral). Mesma regra."""
        if self.ocupado:
            return False
        if sessao != self.sessao:
            self._rodar(self._trocar(sessao))
        return True

    def definir_cerebro(self, modelo: str | None = None, esforco: str | None = None) -> dict:
        """O modelo e o esforço escolhidos na janela. Valem a partir do próximo
        pedido: o modelo troca na mesma conversa; o esforço reabre a conversa
        por baixo (o SDK só aceita esforço ao abrir), sem perder nada."""
        if modelo in MODELOS:
            self.cerebro["modelo"] = modelo
        if esforco in ESFORCOS:
            self.cerebro["esforco"] = esforco
        try:
            self._arquivo_cerebro.write_text(json.dumps(self.cerebro) + "\n")
        except OSError:
            pass
        return dict(self.cerebro)

    def _ler_cerebro(self) -> dict:
        cerebro = {"modelo": "auto" if self.cfg.modelo_rapido else "opus",
                   "esforco": self.cfg.effort}
        try:
            salvo = json.loads(self._arquivo_cerebro.read_text())
        except (OSError, ValueError):
            salvo = {}
        if salvo.get("modelo") in MODELOS:
            cerebro["modelo"] = salvo["modelo"]
        if salvo.get("esforco") in ESFORCOS:
            cerebro["esforco"] = salvo["esforco"]
        if cerebro["modelo"] == "auto" and not self.cfg.modelo_rapido:
            cerebro["modelo"] = "opus"
        return cerebro

    def _modelo_desejado(self) -> str:
        """O modelo que deve atender o PRÓXIMO pedido."""
        escolha = self.cerebro["modelo"]
        if escolha == "auto":
            return self.cfg.modelo_rapido or self.cfg.modelo
        return {"haiku": self.cfg.modelo_rapido or "claude-haiku-5-5",
                "sonnet": SONNET}.get(escolha, self.cfg.modelo)

    async def _trocar(self, retomar: str | None) -> None:
        async with self._travar():
            try:
                await self._desconectar()
                await self._conectar(retomar)
                self._marca.touch()
            except Exception as e:
                self._falhou(e)

    def _travar(self) -> asyncio.Lock:
        # Criada dentro do laço do agente: trocar de conversa e mandar pedido
        # nunca se cruzam (o pedido esperaria a conversa nova abrir).
        if self._trava is None:
            self._trava = asyncio.Lock()
        return self._trava

    def responder(self, saida: Saida, falado: str | None, voz=None) -> None:
        """A resposta dele a uma pergunta (None: não respondeu a tempo)."""
        if falado:
            self._falas.append(falado)
            # None = digitado: vale como o Léo, e desfaz uma "outra voz" de
            # antes (21/10/2026: o "pode apagar" digitado continuava barrado).
            self.voz = voz
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
        return {"fatos": fatos, "conversas": [], "texto": "\n".join(linhas)}

    # -- por dentro ---------------------------------------------------------

    async def _enviar(self, mensagem: str) -> None:
        async with self._travar():
            try:
                # Sem "conversa nova depois de 3 h parado" (era o `recomecar_apos_h`):
                # com a janela nova, quem escolhe é o Léo (Novo chat; cada vez que
                # o Jarvis liga já é um). E a troca no meio do pedido apagava da
                # tela a fala que ele tinha acabado de mandar (22/10/2026).
                if self._cliente is None:
                    # Caiu: reabre a mesma conversa, se tem uma.
                    await self._conectar(self.sessao)
                elif self._esforco_atual != self.cerebro["esforco"]:
                    # O esforço mudou na janela: reabre a MESMA conversa com ele.
                    await self._desconectar()
                    await self._conectar(self.sessao)
                elif self._modelo_atual != self._modelo_desejado():
                    self._modelo_atual = self._modelo_desejado()
                    await self._cliente.set_model(self._modelo_atual)
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
        # Os pedaços do texto. O começo de cada bloco fica segurado enquanto
        # pode ser um "[calado]" (fala que não era com ele: nada aparece).
        bloco, segurado, soltou = 0, "", False

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
                if isinstance(m, StreamEvent):
                    if m.parent_tool_use_id:  # subagente
                        continue
                    e = m.event or {}
                    if e.get("type") == "content_block_start" \
                            and (e.get("content_block") or {}).get("type") == "text":
                        bloco, segurado, soltou = bloco + 1, "", False
                    elif e.get("type") == "content_block_delta" \
                            and (e.get("delta") or {}).get("type") == "text_delta":
                        pedaco = e["delta"].get("text") or ""
                        if not soltou:
                            segurado += pedaco
                            inicio = segurado.lstrip()
                            if inicio.startswith(CALADO) or (inicio and CALADO.startswith(inicio)) \
                                    or not inicio:
                                continue
                            pedaco, soltou = segurado, True
                        self.saidas.put(Saida("parcial", pedaco, titulo=str(bloco)))
                    continue
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
                    janelas = (info.raw or {}).get("unifiedWindows") or {}
                    uso = {nome: {"uso": float(j.get("utilization") or 0),
                                  "volta_em": j.get("resetsAt")}
                           for nome, j in (("cinco_horas", janelas.get("five_hour")),
                                           ("semana", janelas.get("seven_day"))) if j}
                    if uso:
                        self.uso = uso
                elif isinstance(m, ResultMessage) and self._subir and not m.is_error \
                        and not (getattr(m, "terminal_reason", None) or "").startswith("aborted"):
                    # O rápido passou o pedido: o que ele escreveu não vale, e o
                    # turno continua com o Opus (mesma conversa).
                    self._subir, self._no_opus, pendente = False, True, None
                    self.saidas.put(Saida("parcial", janela="descartar"))
                    self.saidas.put(Saida("atividade", "Pensando com calma"))
                    asyncio.create_task(self._subir_pro_opus(cliente))
                elif isinstance(m, ResultMessage):
                    self._subir = False
                    if self._no_opus:
                        asyncio.create_task(self._voltar_pro_rapido(cliente))
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

    def _pedir_o_opus(self, motivo: str) -> str:
        if self.cerebro["modelo"] != "auto":
            return ("O usuário escolheu o modelo na janela: siga você mesmo com o pedido, "
                    "sem chamar o Opus.")
        if self._no_opus:
            return "Você já é o Opus: siga com o pedido."
        self._subir = True
        return ("Combinado: o Opus assume este pedido assim que você terminar. Termine o "
                "turno AGORA, sem escrever nada para o usuário.")

    async def _subir_pro_opus(self, cliente: ClaudeSDKClient) -> None:
        try:
            await cliente.set_model(self.cfg.modelo)
            self._modelo_atual = self.cfg.modelo
            await cliente.query("[sistema: o modelo rápido passou este pedido para você, o Opus. "
                                "Atenda o último pedido do usuário acima, do começo, como se ninguém "
                                "tivesse respondido. Não chame chamar_o_opus.]")
        except Exception as e:
            self._no_opus = False
            self._falhou(e)

    async def _voltar_pro_rapido(self, cliente: ClaudeSDKClient) -> None:
        try:
            if self._modelo_desejado() != self._modelo_atual:
                await cliente.set_model(self._modelo_desejado())
                self._modelo_atual = self._modelo_desejado()
        except Exception:
            pass
        self._no_opus = False

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

    async def _trava_da_voz(self, entrada, _id, _ctx) -> dict:
        """Barra o que só o Léo pode pedir quando a voz não é a dele."""
        comando = str((entrada.get("tool_input") or {}).get("command") or "")
        if entrada.get("tool_name") == "Bash" and re.search(r"(localhost|127\.0\.0\.1):8080/api/send", comando):
            # A ponte direto pula as travas do WhatsApp (pedido, número fora da
            # agenda, voz): foi o contorno do Jarvis para mandar arquivo (20/10/2026).
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": "Use a ferramenta whatsapp_mandar (ela manda arquivo "
                                            "também, no campo `arquivo`), nunca a ponte direto."}}
        if entrada.get("tool_name") == "Bash" and travas.mexe_na_tela(comando):
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": "Para bloquear use a ferramenta bloquear_pc; para "
                                            "desbloquear, pedir_desbloqueio (confirma no "
                                            "celular). Nunca comando direto."}}
        voz = self.voz
        if voz is None or voz.quem == "leo":
            return {}
        o_que = travas.precisa_do_leo(str(entrada.get("tool_name") or ""),
                                      entrada.get("tool_input") or {}, self.casa / "CLAUDE.md")
        if o_que is None:
            return {}
        quem = ("a fala foi curta demais para reconhecer a voz" if voz.quem == "curta"
                else f"a voz não é a do {_dono()} (nota {voz.nota:.2f})")
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Bloqueado pelas travas da voz: {quem}, e isso ({o_que}) só o "
                f"{_dono()} pode pedir. Diga isso em uma frase e não tente outro caminho."),
        }}

    def _bloquear_pc(self) -> str:
        from jarvis.nucleo import tela
        if tela.bloqueada():
            return "A tela já está bloqueada."
        # O Ciclo bloqueia quando a resposta terminar de ser falada (antes,
        # o Claude bloqueava no meio da fala).
        self.bloquear_ao_terminar = True
        return "Feito: a tela bloqueia assim que você terminar de falar."

    def _pedir_desbloqueio(self) -> str:
        from jarvis.nucleo import desbloqueio, tela
        if not tela.bloqueada():
            return "A tela já está desbloqueada."
        pedido = desbloqueio.criar()
        # O aviso é só pelo app do Jarvis (notificação e "Desbloquear o PC?").
        # Nada de WhatsApp: o Léo não pediu (23/10/2026).
        self.saidas.put(Saida("desbloqueio", pedido["id"]))
        return ("Mandei a confirmação pro celular do usuário. O PC só desbloqueia se ele tocar "
                "em Sim no app, nos próximos 3 minutos. Diga isso em uma frase.")

    def _mandou_whats(self, jid: str, nome: str, texto: str) -> None:
        pessoa = self.whatsapp.pessoa(jid) if self.whatsapp else nome
        voz = self.voz
        if voz is not None and voz.quem != "leo":
            # Decisão do Léo: outra pessoa pode mandar (o Claude julga), mas ele
            # sempre fica sabendo.
            linha = (f"{dt.datetime.now():%d/%m %H:%M} — voz que não era a dele "
                     f"({voz.quem}, nota {voz.nota:.2f}) mandou pra {pessoa}: {texto}")
            with open(Path(__file__).resolve().parents[2] / "logs" / "outras-vozes.log", "a") as f:
                f.write(linha + "\n")
            self.saidas.put(Saida("mostrar", linha, titulo="Mensagem mandada por outra voz"))
        self.enviados_whats = (self.enviados_whats + [(pessoa, dt.datetime.now(), texto)])[-50:]
