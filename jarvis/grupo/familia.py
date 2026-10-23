"""O Jarvis no grupo da família do WhatsApp (23/10/2026, pedido do Léo).

Quem está no grupo conversa com o Jarvis escrevendo "Jarvis" em qualquer
parte da mensagem; ele lê pelo contexto se é com ele. A resposta sai pelo
WhatsApp do dono, com "🤖 Jarvis:" na frente.

**Trancado de verdade:** aqui o Claude roda à parte, sem a memória do dono e
SÓ com as ferramentas deste arquivo mais a pesquisa na internet; qualquer
outra é barrada no gancho, antes de rodar. O que mexe no PC ou nas coisas do
dono vira um pedido no celular dele (`jarvis/nucleo/aprovacoes.py`); se ele
aprovar, quem faz é o Jarvis do PC (`pegar()` -> o laço principal).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import queue
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from jarvis import ajustes
from jarvis.nucleo import aprovacoes
from jarvis.nucleo.atalhos import normalizar

PREFIXO = "🤖 Jarvis:"
PERSONA = Path(__file__).with_name("persona_grupo.md")
LISTA = Path.home() / ".local/share/jarvis/grupo-lista.json"
NOVIDADES = Path.home() / ".local/share/jarvis/novidades.jsonl"
# O limite do Claude é do dono: a família não pode gastar tudo.
MAX_POR_HORA = 30
PERMITIDAS = {"WebSearch", "WebFetch", "ToolSearch"}
_ITENS = {"type": "object", "properties": {"itens": {"type": "array", "items": {"type": "string"}}},
          "required": ["itens"]}


def _ler_lista() -> list[str]:
    try:
        lista = json.loads(LISTA.read_text(encoding="utf-8"))
        return [str(i) for i in lista] if isinstance(lista, list) else []
    except (OSError, ValueError):
        return []


def _gravar_lista(itens: list[str]) -> str:
    LISTA.parent.mkdir(parents=True, exist_ok=True)
    LISTA.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    return "Lista de compras:\n" + "\n".join(f"- {i}" for i in itens) if itens else "A lista está vazia."


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

    def _quem(self, remetente: str, minha: bool) -> str:
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
        return [(self._quem(s or "", bool(eu)), c or "(mídia)", self.whatsapp._quando(t))
                for s, eu, c, t in reversed(linhas)]

    def _mandar(self, jid: str, texto: str) -> None:
        self.whatsapp.enviar(jid, f"{PREFIXO} {texto.strip()}")

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
        novas = [m for m in self._mensagens(jid, 20) if m[2] > self._visto]
        if not novas:
            return
        self._visto = max(m[2] for m in novas)
        chamadas = [m for m in novas if "jarvis" in normalizar(m[1]) and not m[1].startswith(PREFIXO)]
        if not chamadas:
            return
        agora = time.time()
        while self._chamadas and self._chamadas[0] < agora - 3600:
            self._chamadas.popleft()
        if len(self._chamadas) >= MAX_POR_HORA:
            self._mandar(jid, "Por agora já conversei bastante; daqui a pouco eu volto.")
            return
        self._chamadas.append(agora)
        asyncio.run(self._atender(jid, chamadas))

    # -- o Claude, trancado --------------------------------------------------------

    async def _atender(self, jid: str, chamadas: list[tuple[str, str, dt.datetime]]) -> None:
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

        @tool("lista_ver", "Mostra a lista de compras do grupo.", {})
        async def lista_ver(args):
            itens = _ler_lista()
            return _t("\n".join(itens) if itens else "(vazia)")

        @tool("lista_adicionar", "Põe itens na lista de compras.", _ITENS)
        async def lista_adicionar(args):
            itens = _ler_lista()
            itens += [str(i).strip() for i in args.get("itens") or [] if str(i).strip()]
            return _t(_gravar_lista(itens))

        @tool("lista_remover", "Tira itens da lista de compras (pelo nome).", _ITENS)
        async def lista_remover(args):
            tirar = {normalizar(str(i)) for i in args.get("itens") or []}
            return _t(_gravar_lista([i for i in _ler_lista() if normalizar(i) not in tirar]))

        @tool("lista_limpar", "Esvazia a lista de compras.", {})
        async def lista_limpar(args):
            return _t(_gravar_lista([]))

        servidor = create_sdk_mcp_server("grupo", tools=[responder, nao_era_comigo, pedir_ao_dono, lista_ver,
                                                         lista_adicionar, lista_remover, lista_limpar])

        async def trancar(entrada, _id, _ctx) -> dict:
            nome = str(entrada.get("tool_name") or "")
            if nome.startswith("mcp__grupo__") or nome in PERMITIDAS:
                return {}
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": "No grupo da família você não tem essa ferramenta. "
                                            "Se precisar do PC ou das coisas do dono, use pedir_ao_dono."}}

        casa = Path.home() / ".local/share/jarvis/grupo"
        casa.mkdir(parents=True, exist_ok=True)
        nome_grupo = self.whatsapp.nome_de(jid) if hasattr(self.whatsapp, "nome_de") else "grupo"
        instrucoes = PERSONA.read_text(encoding="utf-8").replace("{usuario}", self._dono()) \
            .replace("{grupo}", nome_grupo)
        opcoes = ClaudeAgentOptions(
            cli_path=self.binario, cwd=str(casa), model=self.modelo,
            setting_sources=[],  # nada do dono: nem memória, nem MCPs, nem preferências
            system_prompt=instrucoes,
            mcp_servers={"grupo": servidor},
            permission_mode="bypassPermissions",
            hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[trancar])]},
            max_turns=12, stderr=lambda _linha: None,
        )
        conversa = "\n".join(f"[{q:%H:%M}] {quem}: {texto}" for quem, texto, q in self._mensagens(jid, 15))
        agora = dt.datetime.now().astimezone()
        pedido = (f"Agora: {agora:%d/%m/%Y %H:%M} (fuso UTC{agora:%z}).\n\n"
                  "As últimas mensagens do grupo, para contexto:\n" + conversa +
                  "\n\nAs NOVAS que mencionam o Jarvis (trate cada uma):\n" +
                  "\n".join(f"- {quem}: {texto}" for quem, texto, _ in chamadas))
        async for _ in query(prompt=pedido, options=opcoes):
            pass
