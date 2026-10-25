"""O Jarvis no grupo da família do WhatsApp (23/10/2026, pedido do Léo).

Quem está no grupo conversa com o Jarvis escrevendo "Jarvis" em qualquer
parte da mensagem; ele lê pelo contexto se é com ele. Depois que ele
responde, a conversa fica aberta por uns minutos: a resposta de quem falou
com ele chega mesmo sem "Jarvis" (o Chris respondeu ao "em que posso
ajudar?" e ficou no vácuo, 23/10/2026). A resposta sai pelo
WhatsApp do dono, com "🤖 Jarvis:" na frente.

**O Claude completo, com as coisas do dono fechadas (25/10/2026).** Antes
era trancado com meia dúzia de ferramentas fechadas (lista de compras etc.)
e, sem ter como lembrar alguém numa hora, pediu aprovação do Léo para
"lembra a Karyn que segunda tem o CIEE". O Léo: o Jarvis tem que saber fazer,
sem ferramenta para tudo. Agora ele tem terminal, internet e uma pasta só
dele para anotar; o que é do dono (pastas, conversas, memória, e-mail,
agenda, código do Jarvis) é barrado no gancho (`trava_do_grupo`), e mexer no
PC ou nas coisas dele vira um pedido no celular (`jarvis/nucleo/aprovacoes.py`;
se ele aprovar, quem faz é o Jarvis do PC: `pegar()` -> o laço principal).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import queue
import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from jarvis import ajustes
from jarvis.agente import travas
from jarvis.nucleo import aprovacoes, recados
from jarvis.nucleo.atalhos import normalizar

PREFIXO = "🤖 Jarvis:"
PERSONA = Path(__file__).with_name("persona_grupo.md")
CASA = Path.home() / ".local/share/jarvis/grupo"  # a pasta só dele: anotações, listas, lembretes
NOVIDADES = Path.home() / ".local/share/jarvis/novidades.jsonl"
# O limite do Claude é do dono: a família não pode gastar tudo.
MAX_POR_HORA = 30
# Depois de cada resposta no grupo, as mensagens seguintes vão para o Claude
# mesmo sem "Jarvis", e ele decide se são com ele.
CONVERSA_ABERTA_S = 5 * 60
_MEXE_EM_ARQUIVO = {"criar ou editar arquivo", "apagar, mover ou mexer em arquivo", "apagar ou mexer em arquivo"}
_CAMINHO_DE_FORA = re.compile(r"(^|[\s\"'=<>|;&(])/(?!dev/null\b)")
_NUNCA = re.compile(r"\b(sudo|chmod|chown|dd|crontab|shred|truncate|git|ln)\b")
_COM_CAMINHO = {"Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep", "LS"}
# No terminal: qualquer caminho da casa do dono que não seja a pasta do grupo,
# sair da pasta com "..", e os bancos/segredos pelo nome.
_PESSOAL = re.compile(r"(~|\$HOME|\$\{HOME\}|/home/[\w.-]+)(?!/\.local/share/jarvis/grupo\b)"
                      r"|\.\./|/root\b|/etc/(shadow|passwd)|\bsqlite3?\b|messages\.db|whatsapp\.db"
                      r"|\.ssh\b|\.env\b|senha|password|token|cookie", re.I)


def trava_do_grupo(ferramenta: str, entrada: dict, casa: Path | None = None) -> str | None:
    """Por que a ferramenta é barrada no grupo, ou None se pode.

    Livre: conversar, internet, terminal e anotar na própria pasta. Barrado:
    tudo que é do dono (fora da pasta do grupo), o que as travas da voz
    barram para outra pessoa (apagar, instalar, desligar...), a tela e os
    conectores da conta dele (Gmail, Agenda, Drive)."""
    casa = casa or CASA
    if ferramenta.startswith("mcp__"):
        return None if ferramenta.startswith("mcp__grupo__") else "as contas do dono (e-mail, agenda...)"
    if ferramenta in _COM_CAMINHO:
        caminho = str(entrada.get("file_path") or entrada.get("notebook_path") or entrada.get("path") or "")
        padrao = str(entrada.get("pattern") or "") if ferramenta == "Glob" else ""
        for c in (caminho, padrao):
            if c and (c.startswith(("/", "~")) or ".." in c):
                alvo = Path(c.split("*")[0] or "/").expanduser()
                alvo = (casa / alvo).resolve() if not alvo.is_absolute() else alvo.resolve()
                if alvo != casa.resolve() and casa.resolve() not in alvo.parents:
                    return "abrir ou mexer em coisa do dono (fora da sua pasta)"
        return None
    if ferramenta == "Bash":
        comando = str(entrada.get("command") or "")
        if travas.mexe_na_tela(comando):
            return "bloquear ou desbloquear o PC"
        if _PESSOAL.search(comando):
            return "abrir coisa do dono (fora da sua pasta)"
        motivo = travas.precisa_do_leo("Bash", entrada, casa / "nada.md")
        # Gravar, mover e apagar na própria pasta (o terminal roda dentro dela)
        # pode; com qualquer caminho de fora, ou sudo/permissões, não.
        if motivo in _MEXE_EM_ARQUIVO and not _CAMINHO_DE_FORA.search(comando) and not _NUNCA.search(comando):
            return None
        return motivo
    return None


class GrupoFamilia(threading.Thread):
    def __init__(self, whatsapp, binario: str, modelo: str) -> None:
        super().__init__(name="grupo-familia", daemon=True)
        self.whatsapp = whatsapp
        self.binario = binario
        self.modelo = modelo
        # Para o laço principal: ("executar", texto) e ("notificar", texto).
        self._saidas: queue.Queue[tuple[str, str]] = queue.Queue()
        self._chamadas: deque[float] = deque()
        self._visto = dt.datetime.now()
        self._aberta_ate = 0.0

    def pegar(self) -> tuple[str, str] | None:
        try:
            return self._saidas.get_nowait()
        except queue.Empty:
            return None

    # -- o grupo ----------------------------------------------------------------

    def _jid(self) -> str:
        a = ajustes.ler()
        return a["grupo_jid"] if a["grupo_ligado"] and a["grupo_jid"] else ""

    def _dono(self) -> str:
        return ajustes.nome_de_quem_usa() or "dono"

    def _quem(self, remetente: str, minha: bool, texto: str = "") -> str:
        if minha and texto.startswith(PREFIXO):
            return "Jarvis (você)"
        if minha:
            return self._dono()
        try:
            return self.whatsapp.nome_de(remetente if "@" in remetente else remetente + "@lid")
        except Exception:
            return "alguém"

    def _mensagens(self, jid: str, quantas: int = 15) -> list[tuple[str, str, dt.datetime]]:
        """[(quem, texto, quando)], mais antiga primeiro."""
        linhas = self.whatsapp._consultar(
            "SELECT sender, is_from_me, content, timestamp FROM messages WHERE chat_jid = ? "
            "ORDER BY timestamp DESC LIMIT ?", (jid, quantas))
        return [(self._quem(s or "", bool(eu), c or ""), c or "(mídia)", self.whatsapp._quando(t))
                for s, eu, c, t in reversed(linhas)]

    def _mandar(self, jid: str, texto: str) -> None:
        self.whatsapp.enviar(jid, f"{PREFIXO} {texto.strip()}")
        self._aberta_ate = time.time() + CONVERSA_ABERTA_S

    def _notificar(self, texto: str) -> None:
        """Para o dono: notificação no PC e no app (nada de WhatsApp)."""
        subprocess.run(["notify-send", "-a", "Jarvis", "-i", "jarvis-atomo", "Grupo da família", texto],
                       check=False, timeout=10)
        NOVIDADES.touch(mode=0o600, exist_ok=True)
        with NOVIDADES.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": time.time_ns() // 1_000_000, "titulo": "Grupo da família",
                                "texto": texto, "tipo": "grupo"}, ensure_ascii=False) + "\n")
        self._saidas.put(("notificar", texto))

    # -- o laço -----------------------------------------------------------------

    def run(self) -> None:
        while True:
            time.sleep(3)
            try:
                self._uma_volta()
            except Exception:
                pass  # banco ocupado, ponte fora: tenta na próxima

    def _uma_volta(self) -> None:
        jid = self._jid()
        for a in aprovacoes.resolvidas("grupo"):
            if not jid:
                continue
            if a["estado"] == "aprovado":
                self._saidas.put(("executar",
                    f"[Pedido de {a['quem']} no grupo da família do WhatsApp, APROVADO pelo "
                    f"{self._dono()} no celular] {a['pedido']}\n"
                    f"Faça o pedido. Depois responda no grupo com a ferramenta whatsapp_mandar "
                    f"(jid {jid}, nome \"grupo da família\"), começando o texto com \"{PREFIXO}\"."))
            else:
                motivo = "não liberou" if a["estado"] == "recusado" else "não respondeu a tempo"
                self._mandar(jid, f"O {self._dono()} {motivo} o pedido de {a['quem']}.")
        if not jid:
            self._visto = dt.datetime.now()
            return
        # O relógio interno: recados que ele deixou para si mesmo (jarvis/nucleo/recados.py).
        venceram = recados.vencidos(CASA / recados.NOME)
        if venceram:
            asyncio.run(self._atender(jid, [], recados_da_hora=venceram))
        novas = [m for m in self._mensagens(jid, 20) if m[2] > self._visto]
        if not novas:
            return
        self._visto = max(m[2] for m in novas)
        novas = [m for m in novas if not m[1].startswith(PREFIXO)]
        chamadas = [m for m in novas if "jarvis" in normalizar(m[1])]
        aberta = time.time() < self._aberta_ate
        if aberta:
            chamadas = novas  # pode ser a resposta ao que ele perguntou
        if not chamadas:
            return
        agora = time.time()
        while self._chamadas and self._chamadas[0] < agora - 3600:
            self._chamadas.popleft()
        if len(self._chamadas) >= MAX_POR_HORA:
            if any("jarvis" in normalizar(m[1]) for m in chamadas):
                # Direto, sem _mandar: não reabre a conversa.
                self.whatsapp.enviar(jid, f"{PREFIXO} Por agora já conversei bastante; daqui a pouco eu volto.")
            return
        self._chamadas.append(agora)
        asyncio.run(self._atender(jid, chamadas, aberta))

    # -- o Claude, trancado --------------------------------------------------------

    async def _atender(self, jid: str, chamadas: list[tuple[str, str, dt.datetime]],
                       aberta: bool = False, recados_da_hora: list[str] | None = None) -> None:
        from claude_agent_sdk import (ClaudeAgentOptions, HookMatcher, create_sdk_mcp_server, query,
                                      tool)

        def _t(texto: str) -> dict:
            return {"content": [{"type": "text", "text": texto}]}

        @tool("responder", "Manda uma mensagem no grupo (o \"🤖 Jarvis:\" entra sozinho).", {"texto": str})
        async def responder(args):
            self._mandar(jid, str(args.get("texto") or ""))
            return _t("Mandado no grupo.")

        @tool("nao_era_comigo", "A mensagem só falava SOBRE o Jarvis: avisa o dono, sem responder no grupo.",
              {"quem": str, "resumo": str})
        async def nao_era_comigo(args):
            self._notificar(f"{args.get('quem') or 'Alguém'} falou do Jarvis no grupo: {args.get('resumo') or ''}")
            return _t("O dono foi avisado.")

        @tool("pedir_ao_dono", "Pede ao dono, no celular dele, para liberar um pedido que mexe no PC ou nas "
              "coisas dele. Se ele aprovar, o Jarvis do PC faz.", {"quem": str, "pedido": str})
        async def pedir_ao_dono(args):
            a = aprovacoes.criar(str(args.get("quem") or "alguém"), str(args.get("pedido") or ""))
            self._saidas.put(("aprovacao", a["id"]))
            return _t(f"Pedi para o {self._dono()} liberar (vale por 5 minutos). Avise no grupo.")

        servidor = create_sdk_mcp_server("grupo", tools=[responder, nao_era_comigo, pedir_ao_dono])

        async def trancar(entrada, _id, _ctx) -> dict:
            motivo = trava_do_grupo(str(entrada.get("tool_name") or ""), entrada.get("tool_input") or {})
            if motivo is None:
                return {}
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": f"No grupo da família você não pode {motivo}. Se a pessoa "
                                            "precisa disso, use pedir_ao_dono; senão, resolva de outro jeito."}}

        casa = CASA
        casa.mkdir(parents=True, exist_ok=True)
        nome_grupo = self.whatsapp.nome_de(jid) if hasattr(self.whatsapp, "nome_de") else "grupo"
        instrucoes = PERSONA.read_text(encoding="utf-8").replace("{usuario}", self._dono()) \
            .replace("{grupo}", nome_grupo).replace("{casa}", str(casa)).replace("{recados}", recados.COMO_USAR)
        opcoes = ClaudeAgentOptions(
            cli_path=self.binario, cwd=str(casa), model=self.modelo,
            setting_sources=[],  # nada do dono: nem memória, nem MCPs, nem preferências
            system_prompt=instrucoes,
            mcp_servers={"grupo": servidor},
            permission_mode="bypassPermissions",
            hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[trancar])]},
            max_turns=20, stderr=lambda _linha: None,
        )
        conversa = "\n".join(f"[{q:%H:%M}] {quem}: {texto}" for quem, texto, q in self._mensagens(jid, 15))
        agora = dt.datetime.now().astimezone()
        if recados_da_hora:
            pedido = (f"Agora: {agora:%A, %d/%m/%Y %H:%M} (fuso UTC{agora:%z}).\n\n"
                      "As últimas mensagens do grupo, para contexto:\n" + conversa +
                      "\n\nCHEGOU A HORA destes recados que VOCÊ deixou para si mesmo; faça o que anotou "
                      "(normalmente, mandar no grupo com `responder`):\n" +
                      "\n".join(f"- {r}" for r in recados_da_hora))
            async for _ in query(prompt=pedido, options=opcoes):
                pass
            return
        pedido = (f"Agora: {agora:%A, %d/%m/%Y %H:%M} (fuso UTC{agora:%z}).\n\n"
                  "As últimas mensagens do grupo, para contexto:\n" + conversa +
                  ("\n\nVocê acabou de falar no grupo. As NOVAS (podem ser com você mesmo sem "
                   "\"Jarvis\", ou só conversa entre eles; trate cada uma):\n" if aberta else
                   "\n\nAs NOVAS que mencionam o Jarvis (trate cada uma):\n") +
                  "\n".join(f"- {quem}: {texto}" for quem, texto, _ in chamadas))
        async for _ in query(prompt=pedido, options=opcoes):
            pass
