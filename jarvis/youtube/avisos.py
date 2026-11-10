"""Os avisos do canal que o Jarvis fala sozinho (Painel do Canal, etapa 6).

A sincronização (timer, a cada 30 min) compara antes e depois e deixa as
falas em avisos.jsonl. O assistente pega com `pegar()` e fala pela mesma fila
do alerta do Monitor: nunca no meio de uma fala, nunca jogando ou gravando,
e só das 8h às 23h (fora disso fica pro bom dia).

O que avisa:
- comentário novo com pergunta (vários juntos viram uma frase só);
- vídeo passando de 100, 250, 500, mil, 2.500, 5 mil... views;
- o canal passando de 100, 250, 500, mil... inscritos.
Na primeira sincronização nada é avisado (senão seriam dezenas de marcos velhos).
"""

from __future__ import annotations

import datetime as dt
import json
import time

from jarvis.youtube import conta, dados

ARQUIVO = conta.PASTA / "avisos.jsonl"
ESQUEMA = "CREATE TABLE IF NOT EXISTS marcos (chave TEXT PRIMARY KEY, quando REAL);"
HORA_INICIO, HORA_FIM = 8, 23


def degraus(ate: int) -> list[int]:
    r, base = [], 100
    while base <= ate:
        for m in (1, 2.5, 5):
            if base * m <= ate:
                r.append(int(base * m))
        base *= 10
    return r


def _falado(n: int) -> str:
    if n >= 1_000_000:
        return f"{n // 1_000_000} milh{'ão' if n < 2_000_000 else 'ões'}"
    if n >= 1000:
        mil = n / 1000
        return ("mil" if mil == 1 else f"{mil:g}".replace(".", ",") + " mil")
    return str(n)


def _guardar(falas: list[str]) -> None:
    if not falas:
        return
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    with ARQUIVO.open("a", encoding="utf-8") as f:
        for fala in falas:
            f.write(json.dumps({"fala": fala, "quando": time.time()}, ensure_ascii=False) + "\n")


def conferir(primeira: bool, perguntas_novas: list[dict]) -> list[str]:
    """Chamada no fim da sincronização. Devolve (e guarda) as falas novas."""
    con = dados.abrir()
    con.executescript(ESQUEMA)
    falas: list[str] = []
    passados = {r[0] for r in con.execute("SELECT chave FROM marcos")}
    novos = []
    c = con.execute("SELECT inscritos FROM canal").fetchone()
    if c:
        for d in degraus(c["inscritos"]):
            chave = f"inscritos:{d}"
            if chave not in passados:
                novos.append(chave)
                if not primeira:
                    falas.append(f"O canal acabou de passar de {_falado(d)} inscritos!")
    for v in con.execute("SELECT id, titulo, views FROM videos WHERE visibilidade = 'public'"):
        maior = None
        for d in degraus(v["views"]):
            chave = f"views:{v['id']}:{d}"
            if chave not in passados:
                novos.append(chave)
                maior = d
        if maior and not primeira:
            falas.append(f"O vídeo \"{v['titulo']}\" passou de {_falado(maior)} views.")
    with con:
        con.executemany("INSERT OR IGNORE INTO marcos VALUES (?, ?)", [(k, time.time()) for k in novos])
    con.close()
    if perguntas_novas and not primeira:
        if len(perguntas_novas) == 1:
            p = perguntas_novas[0]
            falas.append(f"{p['autor'].lstrip('@')} perguntou no vídeo \"{p['video_titulo'] or 'teu vídeo'}\": {p['texto'][:160]}")
        else:
            falas.append(f"Chegaram {len(perguntas_novas)} comentários novos com pergunta no canal.")
    _guardar(falas)
    return falas


def pegar(agora: dt.datetime | None = None, ocupado: bool = False) -> list[str]:
    """As falas guardadas, se for hora de falar; e esvazia o arquivo. Velhas
    de mais de 12 h não são faladas (o bom dia conta o resumo)."""
    agora = agora or dt.datetime.now()
    if ocupado or not (HORA_INICIO <= agora.hour < HORA_FIM) or not ARQUIVO.exists():
        return []
    try:
        linhas = [json.loads(x) for x in ARQUIVO.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        linhas = []
    ARQUIVO.unlink(missing_ok=True)
    limite = agora.timestamp() - 12 * 3600
    return [x["fala"] for x in linhas if x.get("quando", 0) >= limite]
