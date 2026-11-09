"""Memória viva: tudo que ele vê e ouve, indexado e buscável."""
import json, os, re, sqlite3, sys, threading, time, urllib.request
from pathlib import Path

import numpy as np

BASE = Path(os.environ.get("JARVIS_DADOS", Path.home() / ".local/share/jarvis"))
DB = BASE / "memoria_viva.db"
ESQUEMA = Path(__file__).with_name("esquema.sql")
OLLAMA = "http://127.0.0.1:11434"


def _abrir() -> sqlite3.Connection:
    BASE.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.executescript(ESQUEMA.read_text(encoding="utf-8"))
    return con


def _embed(texto: str) -> np.ndarray | None:
    try:
        # /api/embed (o /api/embeddings antigo volta vazio no Ollama novo). 30 s:
        # a primeira vez carrega o modelo na placa.
        corpo = json.dumps({"model": "nomic-embed-text", "input": texto}).encode()
        req = urllib.request.Request(f"{OLLAMA}/api/embed", corpo,
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return np.array(json.load(r)["embeddings"][0], dtype=np.float32)
    except Exception:
        return None


def gravar(tipo: str, texto: str, fonte: str = "") -> int:
    texto = " ".join(texto.split())
    if len(texto) < 3:
        return 0
    con = _abrir()
    with con:
        cur = con.execute("INSERT INTO fatos(tipo, ts, fonte, texto) VALUES (?,?,?,?)",
                          (tipo, time.time(), fonte, texto))
        vet = _embed(texto)
        if vet is not None:
            con.execute("INSERT INTO vetores(id, vetor) VALUES (?,?)",
                        (cur.lastrowid, vet.tobytes()))
    con.close()
    return cur.lastrowid


def _palavras(consulta: str) -> list[str]:
    # Aspas e símbolos quebram a busca do FTS5: só letras e números.
    return re.findall(r"\w+", consulta)


def _fts(con, consulta: str, limite: int):
    if not _palavras(consulta):
        return []
    try:
        return con.execute(
            "SELECT f.id, f.tipo, f.ts, f.texto FROM fatos_fts "
            "JOIN fatos f ON f.id = fatos_fts.rowid "
            "WHERE fatos_fts MATCH ? ORDER BY rank LIMIT ?",
            (" OR ".join(f'"{p}"*' for p in _palavras(consulta)), limite)).fetchall()
    except sqlite3.OperationalError:
        return []


def buscar(consulta: str, limite: int = 8) -> list[dict]:
    con = _abrir()
    achados = {r[0]: r for r in _fts(con, consulta, limite * 3)}
    vet = _embed(consulta)
    if vet is not None:
        linhas = con.execute(
            "SELECT f.id, f.tipo, f.ts, f.texto, v.vetor FROM vetores v "
            "JOIN fatos f ON f.id = v.id").fetchall()
        notas = []
        for i, tipo, ts, texto, blob in linhas:
            v = np.frombuffer(blob, dtype=np.float32)
            notas.append((float(v @ vet / (np.linalg.norm(v) * np.linalg.norm(vet) + 1e-9)),
                          (i, tipo, ts, texto)))
        for _, linha in sorted(notas, reverse=True)[:limite]:
            achados.setdefault(linha[0], linha)
    con.close()
    return [{"id": i, "tipo": t, "ts": ts, "texto": x}
            for i, t, ts, x in list(achados.values())[:limite]]


def gravar_depois(tipo: str, texto: str, fonte: str = "") -> None:
    """Grava sem segurar quem chamou (o Ollama pode levar uns segundos)."""
    def _ir():
        try:
            gravar(tipo, texto, fonte)
        except Exception as e:  # noqa: BLE001 - memória nunca derruba o Jarvis
            print(f"  memória viva: {e}", flush=True)
    threading.Thread(target=_ir, daemon=True, name="memoria-viva").start()


def main(a: list[str]) -> int:
    """python -m jarvis.nucleo.memoria_viva buscar <texto> | gravar <tipo> <texto>"""
    if len(a) >= 2 and a[0] == "buscar":
        for f in buscar(" ".join(a[1:])):
            print(f"[{time.strftime('%d/%m/%Y %H:%M', time.localtime(f['ts']))}] ({f['tipo']}) {f['texto']}")
        return 0
    if len(a) >= 3 and a[0] == "gravar":
        print(gravar(a[1], " ".join(a[2:]), "comando"))
        return 0
    print(main.__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
