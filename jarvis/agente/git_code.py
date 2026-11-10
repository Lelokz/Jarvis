"""As mudanças do projeto no modo code (10/11/2026), para o painel "Mudanças"
da janela e do app: os arquivos mexidos, quanto entrou e saiu, o diff e se
tem commit esperando push. Só lê; commit e push são do Jarvis (com o OK).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

MAX_DIFF = 150_000   # o resto vira "(cortado)": a tela não precisa de 10 MB


def _git(caminho: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(caminho), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout if r.returncode == 0 else ""


def mudancas(caminho: Path) -> dict:
    caminho = Path(caminho)
    if not (caminho / ".git").exists():
        return {"git": False, "arquivos": [], "diff": "", "ramo": "", "a_frente": 0, "remoto": False}
    estados = {}
    for linha in _git(caminho, "status", "--porcelain=v1", "-uall").splitlines():
        if len(linha) < 4:
            continue
        x, nome = linha[:2], linha[3:].split(" -> ")[-1].strip('"')
        estados[nome] = "novo" if x == "??" or "A" in x else "apagado" if "D" in x else "mudou"
    contas = {}
    for linha in _git(caminho, "diff", "HEAD", "--numstat").splitlines():
        partes = linha.split("\t")
        if len(partes) == 3:
            mais, menos, nome = partes
            contas[nome] = (int(mais) if mais.isdigit() else 0, int(menos) if menos.isdigit() else 0)
    arquivos = []
    for nome, estado in sorted(estados.items()):
        mais, menos = contas.get(nome, (0, 0))
        if estado == "novo" and not mais:
            try:
                mais = sum(1 for _ in (caminho / nome).open(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
        arquivos.append({"arquivo": nome, "estado": estado, "mais": mais, "menos": menos})
    diff = _git(caminho, "diff", "HEAD")
    novos = [a["arquivo"] for a in arquivos if a["estado"] == "novo"]
    for nome in novos[:20]:
        try:
            texto = (caminho / nome).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        diff += f"\ndiff --git a/{nome} b/{nome}\nnovo arquivo\n+++ b/{nome}\n" + \
            "".join(f"+{l}\n" for l in texto.splitlines()[:400])
    if len(diff) > MAX_DIFF:
        diff = diff[:MAX_DIFF] + "\n(cortado: o resto está no git)\n"
    ramo = _git(caminho, "branch", "--show-current").strip()
    remoto = bool(_git(caminho, "remote").strip())
    a_frente = _git(caminho, "rev-list", "--count", "@{u}..HEAD").strip() if remoto else ""
    return {"git": True, "arquivos": arquivos, "diff": diff, "ramo": ramo,
            "a_frente": int(a_frente) if a_frente.isdigit() else 0, "remoto": remoto}


def diff_da_ferramenta(nome: str, entrada: dict, max_linhas: int = 120) -> str | None:
    """O antes/depois de um Edit/Write do Claude, em ```diff (a janela pinta)."""
    linhas: list[str] = []
    if nome == "Edit":
        linhas += [f"-{l}" for l in str(entrada.get("old_string", "")).splitlines()]
        linhas += [f"+{l}" for l in str(entrada.get("new_string", "")).splitlines()]
    elif nome == "MultiEdit":
        for e in entrada.get("edits") or []:
            linhas += [f"-{l}" for l in str(e.get("old_string", "")).splitlines()]
            linhas += [f"+{l}" for l in str(e.get("new_string", "")).splitlines()]
            linhas.append("@@")
    elif nome == "Write":
        linhas += [f"+{l}" for l in str(entrada.get("content", "")).splitlines()]
    else:
        return None
    if not linhas:
        return None
    sobra = len(linhas) - max_linhas
    corpo = "\n".join(linhas[:max_linhas]) + (f"\n… mais {sobra} linhas" if sobra > 0 else "")
    return f"```diff\n{corpo}\n```"
