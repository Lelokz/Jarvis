"""As conversas do Jarvis, para a barra lateral da janela (out/2026).

Cada conversa é uma sessão do Claude Code, guardada por ele mesmo em
`~/.claude/projects/<casa>/<id>.jsonl`. O SDK lista as sessões (com o título
que o próprio Claude Code dá, o `custom_title`) e devolve as mensagens na
ordem certa; daqui sai o formato das falas do protocolo da ponte (`quem`,
`texto`, `origem`, `quando`), o mesmo do histórico ao vivo.

Lê, renomeia e manda para a lixeira (pedidos da barra lateral). Quem troca
de conversa é o `Agente`.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from pathlib import Path

import claude_agent_sdk as sdk

# "[voz, qua 21/10, 18:45, voz do Léo]" — o cabeçalho que o Agente põe em cada pedido.
_CABECALHO = re.compile(r"^\[(\w+)[^\]\n]*\]\s*")
CALADO = "[calado]"


def _origem(texto: str) -> str:
    m = _CABECALHO.match(texto or "")
    return m.group(1) if m else ""


def _sem_cabecalho(texto: str) -> str:
    """O pedido sem o cabeçalho e sem as notas de contexto do sistema (linhas
    entre colchetes logo depois dele: anexos, WhatsApp)."""
    linhas = _CABECALHO.sub("", texto or "", count=1).splitlines()
    while linhas and linhas[0].startswith("[") and linhas[0].rstrip().endswith("]"):
        linhas.pop(0)
    return "\n".join(linhas).strip()


def _arquivo_fixadas(casa: Path) -> Path:
    return casa.parent / "fixadas.json"


def fixadas(casa: Path) -> list[str]:
    try:
        lista = json.loads(_arquivo_fixadas(casa).read_text(encoding="utf-8"))
        return [str(x) for x in lista] if isinstance(lista, list) else []
    except (OSError, ValueError):
        return []


def fixar(casa: Path, sessao: str, sim: bool) -> None:
    """Fixa (ou solta) a conversa no topo da barra lateral (janela beta 0.7.0)."""
    lista = [s for s in fixadas(casa) if s != sessao]
    if sim:
        lista.insert(0, sessao)
    _arquivo_fixadas(casa).write_text(json.dumps(lista), encoding="utf-8")


def listar(casa: Path, limite: int = 200) -> list[dict]:
    """As conversas: as fixadas primeiro, depois da mais nova para a mais antiga."""
    presas = set(fixadas(casa))
    conversas = []
    for s in sdk.list_sessions(directory=str(casa), limit=limite):
        primeiro = s.first_prompt or ""
        titulo = s.custom_title or s.summary or _sem_cabecalho(primeiro) or "Conversa"
        conversas.append({
            "id": s.session_id,
            "titulo": " ".join(titulo.split())[:120],
            "quando": int(s.last_modified or 0) / 1000,
            "criada": int(s.created_at or s.last_modified or 0) / 1000,
            "origem": _origem(primeiro),
            "fixada": s.session_id in presas,
        })
    conversas.sort(key=lambda c: (c["fixada"], c["quando"]), reverse=True)
    return conversas


def renomear(casa: Path, sessao: str, titulo: str) -> None:
    """O título que o Léo deu (o último vale; o SDK acrescenta no arquivo)."""
    sdk.rename_session(sessao, " ".join(titulo.split())[:120], directory=str(casa))


def apagar(casa: Path, sessao: str) -> None:
    """Manda a conversa para a LIXEIRA (dá para desfazer), nunca apaga de vez:
    a regra da casa. Só conversa desta casa."""
    if sessao not in {c["id"] for c in listar(casa, limite=1000)}:
        raise FileNotFoundError("conversa não encontrada")
    alvos = []
    for arquivo in (Path.home() / ".claude" / "projects").glob(f"*/{sessao}.jsonl"):
        alvos.append(arquivo)
        pasta = arquivo.with_suffix("")   # subagentes e resultados grandes, se houver
        if pasta.is_dir():
            alvos.append(pasta)
    if not alvos:
        raise FileNotFoundError("conversa não encontrada")
    subprocess.run(["gio", "trash", *map(str, alvos)], check=True, timeout=20,
                   capture_output=True)


def _horarios(sessao: str) -> dict[str, float]:
    """uuid da mensagem -> quando (época). O SDK não devolve o horário; ele
    está no próprio arquivo da sessão."""
    horas: dict[str, float] = {}
    for arquivo in (Path.home() / ".claude" / "projects").glob(f"*/{sessao}.jsonl"):
        with open(arquivo, encoding="utf-8") as f:
            for linha in f:
                try:
                    e = json.loads(linha)
                    horas[e["uuid"]] = dt.datetime.fromisoformat(
                        e["timestamp"].replace("Z", "+00:00")).timestamp()
                except (ValueError, KeyError, TypeError):
                    continue
    return horas


def _resumo(nome: str, entrada: dict) -> str:
    detalhe = entrada.get("description") or entrada.get("command") or entrada.get("file_path") \
        or entrada.get("url") or entrada.get("pattern") or entrada.get("query") or ""
    nome = nome.removeprefix("mcp__").replace("__", ": ")
    return f"{nome} — {str(detalhe)[:160]}" if detalhe else nome


def falas(casa: Path, sessao: str) -> list[dict]:
    """A conversa inteira no formato das falas do protocolo, em ordem."""
    horas = _horarios(sessao)
    saida: list[dict] = []
    for m in sdk.get_session_messages(sessao, directory=str(casa)):
        if m.parent_tool_use_id:  # dentro de um subagente
            continue
        msg = m.message or {}
        quando = horas.get(m.uuid, 0.0)
        conteudo = msg.get("content")
        if m.type == "user":
            if isinstance(conteudo, list):
                texto = "\n".join(b.get("text", "") for b in conteudo
                                  if isinstance(b, dict) and b.get("type") == "text")
            else:
                texto = str(conteudo or "")
            if not texto.strip() or texto.lstrip().startswith(("[sistema", "<")):
                continue  # resultado de ferramenta, aviso do sistema, comando interno
            limpo = _sem_cabecalho(texto)
            if limpo:
                saida.append({"quem": "voce", "texto": limpo, "origem": _origem(texto),
                              "quando": quando})
        elif m.type == "assistant" and isinstance(conteudo, list):
            for b in conteudo:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    t = b.get("text", "").strip()
                    if t and not t.endswith(CALADO):
                        saida.append({"quem": "jarvis", "texto": t, "acao": None,
                                      "perguntando": False, "quando": quando})
                elif b.get("type") == "tool_use" and b.get("name") not in ("AskUserQuestion",
                                                                          "mcp__jarvis__chamar_o_opus"):
                    saida.append({"quem": "atividade", "texto": _resumo(b.get("name", ""),
                                                                        b.get("input") or {}),
                                  "quando": quando})
    return saida
