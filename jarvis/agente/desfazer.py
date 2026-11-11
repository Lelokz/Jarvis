"""O "Desfazer" do modo code (etapa 3 do tchan, 11/11/2026).

Antes de o Claude mexer num arquivo do projeto (Edit, Write, MultiEdit,
NotebookEdit), a trava guarda como ele ESTAVA. No fim da resposta, o que
mudou de verdade vira uma "alteração": o cartão "Alterou 3 arquivos" da
janela e do app, com o +/− de cada um e o botão Desfazer, que põe os
arquivos de volta como estavam antes DAQUELA resposta (o resto do projeto não
muda). Também vale "desfaz isso" falado.

Fica em ~/.local/share/jarvis/code-desfazer/<id>.json (as últimas 40). Arquivo
que nasceu na resposta vai para a LIXEIRA ao desfazer, nunca apagado de vez.
O "Desfazer arquivo" do painel Mudanças (contra o último commit) guarda uma
cópia do arquivo antes, no mesmo lugar.
"""

from __future__ import annotations

import difflib
import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path

PASTA = Path.home() / ".local/share/jarvis/code-desfazer"
MAX_ARQUIVO = 2_000_000     # maior que isso (ou binário) não entra no desfazer
MAX_GUARDADAS = 40


def _ler(arquivo: Path) -> str | None:
    """O texto do arquivo; None = não existe. Binário/enorme: ValueError."""
    if not arquivo.exists():
        return None
    if not arquivo.is_file() or arquivo.stat().st_size > MAX_ARQUIVO:
        raise ValueError("grande demais ou não é arquivo")
    dados = arquivo.read_bytes()
    if b"\0" in dados[:8000]:
        raise ValueError("binário")
    return dados.decode("utf-8")


def contar(antes: str | None, depois: str | None) -> tuple[int, int]:
    """Quantas linhas entraram e saíram."""
    a = (antes or "").splitlines()
    d = (depois or "").splitlines()
    mais = menos = 0
    for linha in difflib.unified_diff(a, d, lineterm="", n=0):
        if linha.startswith("+") and not linha.startswith("+++"):
            mais += 1
        elif linha.startswith("-") and not linha.startswith("---"):
            menos += 1
    return mais, menos


def diff(antes: str | None, depois: str | None, nome: str) -> str:
    return "\n".join(difflib.unified_diff((antes or "").splitlines(), (depois or "").splitlines(),
                                          f"a/{nome}", f"b/{nome}", lineterm="", n=3))


class Turno:
    """Os arquivos de UMA resposta: como estavam antes da primeira mexida."""

    def __init__(self, projeto: Path, pasta: Path = PASTA) -> None:
        self.projeto = Path(projeto)
        self.pasta = pasta
        self.antes: dict[str, str | None] = {}
        self.fora: set[str] = set()     # binário ou grande: não dá para desfazer

    def guardar(self, alvo: str) -> None:
        """Chamado ANTES da ferramenta mexer. Só a primeira vez vale."""
        if not alvo:
            return
        caminho = Path(alvo).expanduser()
        if not caminho.is_absolute():
            caminho = self.projeto / caminho
        try:
            caminho = caminho.resolve()
            rel = str(caminho.relative_to(self.projeto.resolve()))
        except (OSError, ValueError):
            return   # fora do projeto: não é deste cartão
        if rel in self.antes or rel in self.fora:
            return
        try:
            self.antes[rel] = _ler(caminho)
        except (OSError, ValueError, UnicodeDecodeError):
            self.fora.add(rel)

    def fechar(self, sessao: str = "") -> dict | None:
        """O fim da resposta: o resumo do que mudou de verdade (None = nada)."""
        arquivos, guardado = [], {}
        for rel, antes in sorted(self.antes.items()):
            try:
                depois = _ler(self.projeto / rel)
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            if depois == antes:
                continue
            mais, menos = contar(antes, depois)
            estado = "novo" if antes is None else "apagado" if depois is None else "mudou"
            arquivos.append({"arquivo": rel, "estado": estado, "mais": mais, "menos": menos})
            guardado[rel] = {"antes": antes, "depois": depois}
        self.antes.clear()
        self.fora.clear()
        if not arquivos:
            return None
        resumo = {"id": uuid.uuid4().hex[:12], "caminho": str(self.projeto), "sessao": sessao,
                  "quando": time.time(), "arquivos": arquivos,
                  "mais": sum(a["mais"] for a in arquivos), "menos": sum(a["menos"] for a in arquivos),
                  "desfeito": []}
        self.pasta.mkdir(parents=True, exist_ok=True)
        (self.pasta / f"{resumo['id']}.json").write_text(
            json.dumps({**resumo, "conteudo": guardado}, ensure_ascii=False), encoding="utf-8")
        _limpar(self.pasta)
        return resumo


def _limpar(pasta: Path) -> None:
    velhas = sorted(pasta.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[MAX_GUARDADAS:]
    for p in velhas:
        p.unlink(missing_ok=True)


def abrir(ident: str, pasta: Path = PASTA) -> dict | None:
    if not ident.isalnum():
        return None
    try:
        return json.loads((pasta / f"{ident}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ultima(projeto: Path, pasta: Path = PASTA) -> dict | None:
    """A alteração mais nova desse projeto que ainda não foi desfeita toda."""
    for p in sorted(pasta.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("caminho") == str(Path(projeto)) and \
                len(d.get("desfeito") or []) < len(d.get("arquivos") or []):
            return d
    return None


def _lixeira(caminho: Path) -> None:
    subprocess.run(["gio", "trash", str(caminho)], check=True, timeout=20, capture_output=True)


def desfazer(ident: str, arquivo: str = "", pasta: Path = PASTA) -> dict:
    """Põe os arquivos (ou só um) como estavam antes daquela resposta.
    Devolve {"id", "voltaram": [...], "desfeito": [...]}. ValueError com o motivo."""
    d = abrir(ident, pasta)
    if d is None:
        raise ValueError("não achei essa mudança (já é antiga)")
    projeto = Path(d["caminho"])
    alvos = [a["arquivo"] for a in d["arquivos"] if not arquivo or a["arquivo"] == arquivo]
    alvos = [a for a in alvos if a not in d.get("desfeito", [])]
    if not alvos:
        raise ValueError("já estava desfeito")
    voltaram = []
    for rel in alvos:
        antes = d["conteudo"][rel]["antes"]
        caminho = projeto / rel
        if antes is None:
            if caminho.exists():
                _lixeira(caminho)
        else:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(antes, encoding="utf-8")
        voltaram.append(rel)
    d["desfeito"] = list(dict.fromkeys((d.get("desfeito") or []) + voltaram))
    (pasta / f"{ident}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return {"id": ident, "caminho": d["caminho"], "voltaram": voltaram, "desfeito": d["desfeito"]}


def desfazer_git(projeto: Path, arquivo: str, pasta: Path = PASTA) -> str:
    """O "Desfazer arquivo" do painel Mudanças: o arquivo volta como está no
    último commit (novo, sem commit: vai para a lixeira). Antes, uma cópia de
    como está agora fica guardada. Devolve onde ficou a cópia."""
    projeto = Path(projeto).resolve()
    caminho = (projeto / arquivo).resolve()
    if not caminho.is_relative_to(projeto) or caminho == projeto:
        raise ValueError("arquivo fora do projeto")
    copia = pasta / "copias" / time.strftime("%Y%m%d-%H%M%S") / arquivo
    if caminho.is_file():
        copia.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(caminho, copia)
    no_git = subprocess.run(["git", "-C", str(projeto), "cat-file", "-e", f"HEAD:{arquivo}"],
                            capture_output=True, timeout=20).returncode == 0
    if no_git:
        r = subprocess.run(["git", "-C", str(projeto), "restore", "--source=HEAD", "--staged", "--worktree",
                            "--", arquivo], capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            raise ValueError(r.stderr.strip()[:200] or "o git não deixou")
    elif caminho.exists():
        subprocess.run(["git", "-C", str(projeto), "rm", "--cached", "-q", "--", arquivo],
                       capture_output=True, timeout=20)
        _lixeira(caminho)
    return str(copia)
