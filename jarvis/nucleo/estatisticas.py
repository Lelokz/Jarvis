"""As contas de Ajustes → Uso e Tempo e foco (etapa 4 do tchan, 11/11/2026).

**Uso.** O Claude só diz quanto do limite JÁ foi usado (5 h e semana). Para
saber quanto foi em cada dia, cada mudança do "uso" vira uma linha em
~/.local/share/jarvis/uso-historico.jsonl, com o cérebro e o projeto do modo
code daquela hora: a diferença entre duas linhas é o que aquele pedaço gastou.
Daí saem o gasto por dia, o ritmo (quando a semana acaba se continuar assim) e
o que mais gastou hoje.

**Tempo conversando.** Sai dos registros que a NOVA já guarda (logs/jarvis-*):
de "acordou" a "dormiu", mais cada pedido do celular até a resposta.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

ARQUIVO = Path.home() / ".local/share/jarvis/uso-historico.jsonl"
MAX_LINHAS = 20_000


def _nome_do_cerebro(modelo: str) -> str:
    m = (modelo or "").lower()
    for nome in ("opus", "sonnet", "haiku"):
        if nome in m:
            return nome.capitalize()
    return "Local" if m else ""


def registrar(uso: dict, modelo: str = "", code: str = "", arquivo: Path = ARQUIVO, agora: float | None = None) -> None:
    """Uma foto do uso (o evento "uso" do agente)."""
    semana = (uso or {}).get("semana") or {}
    if "uso" not in semana:
        return
    linha = {"t": round(agora or time.time(), 1), "semana": float(semana["uso"]),
             "volta": semana.get("volta_em"), "cinco": float(((uso or {}).get("cinco_horas") or {}).get("uso") or 0),
             "cerebro": _nome_do_cerebro(modelo), "code": code}
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    with open(arquivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    try:
        if arquivo.stat().st_size > 3_000_000:   # guarda só o fim
            linhas = arquivo.read_text(encoding="utf-8").splitlines()[-MAX_LINHAS // 2:]
            arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    except OSError:
        pass


def _ler(arquivo: Path) -> list[dict]:
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except OSError:
        return []
    saida = []
    for l in texto.splitlines():
        try:
            saida.append(json.loads(l))
        except ValueError:
            continue
    return sorted(saida, key=lambda x: x.get("t", 0))


def _gastos(linhas: list[dict]) -> list[tuple[float, float, dict]]:
    """(quando, quanto da semana, a linha de ANTES: o cérebro/projeto que gastou)."""
    saida = []
    for a, b in zip(linhas, linhas[1:]):
        if a.get("volta") != b.get("volta") and b["semana"] < a["semana"]:
            delta = b["semana"]          # a semana renovou no meio
        else:
            delta = b["semana"] - a["semana"]
        if delta > 0:
            saida.append((b["t"], delta, a))
    return saida


def uso(arquivo: Path = ARQUIVO, agora: float | None = None, dias: int = 7) -> dict:
    agora = agora or time.time()
    linhas = _ler(arquivo)
    gastos = _gastos(linhas)
    hoje = dt.date.fromtimestamp(agora)
    por_dia = defaultdict(float)
    for t, d, _ in gastos:
        por_dia[dt.date.fromtimestamp(t)] += d
    lista = [{"dia": (hoje - dt.timedelta(days=i)).isoformat(),
              "pct": round(por_dia.get(hoje - dt.timedelta(days=i), 0.0) * 100, 1)}
             for i in reversed(range(dias))]

    # O ritmo: o que foi gasto nas últimas 24 h (precisa de 3 h de dados).
    previsao = None
    if linhas:
        ultima = linhas[-1]
        recentes = [g for g in gastos if g[0] >= agora - 86400]
        inicio = max(agora - 86400, linhas[0]["t"])
        horas = (agora - inicio) / 3600
        gasto = sum(d for _, d, _ in recentes)
        if horas >= 3 and gasto > 0 and ultima["semana"] < 1:
            acaba = agora + (1 - ultima["semana"]) / (gasto / horas) * 3600
            volta = float(ultima.get("volta") or 0)
            previsao = {"acaba_em": round(acaba), "antes_de_renovar": bool(volta and acaba < volta)}

    do_dia = [g for g in gastos if dt.date.fromtimestamp(g[0]) == hoje]
    total = sum(d for _, d, _ in do_dia)
    cerebros, projetos = Counter(), Counter()
    for _, d, a in do_dia:
        if a.get("cerebro"):
            cerebros[a["cerebro"]] += d
        if a.get("code"):
            projetos[a["code"]] += d
    cerebro = cerebros.most_common(1)[0] if cerebros else None
    projeto = projetos.most_common(1)[0] if projetos else None
    return {"dias": lista, "previsao": previsao,
            "cerebro": {"nome": cerebro[0], "pct": round(cerebro[1] / total * 100)} if cerebro and total else None,
            "code": {"nome": projeto[0], "pct": round(projeto[1] * 100, 1)} if projeto else None}


def _registros(pasta: Path, desde: float) -> list[Path]:
    saida = []
    for p in sorted(pasta.glob("jarvis-*.jsonl")):
        try:
            if p.stat().st_mtime >= desde:
                saida.append(p)
        except OSError:
            continue
    return saida


def _quando(momento: str) -> float | None:
    try:
        return dt.datetime.fromisoformat(momento).timestamp()
    except (TypeError, ValueError):
        return None


def tempo_e_pedidos(pasta: Path, agora: float | None = None, dias: int = 7) -> dict:
    """Os minutos conversando por dia (os últimos `dias`) e os pedidos de hoje por origem."""
    agora = agora or time.time()
    hoje = dt.date.fromtimestamp(agora)
    comeco = dt.datetime.combine(hoje - dt.timedelta(days=dias - 1), dt.time()).timestamp()
    intervalos: list[tuple[float, float]] = []
    origens: Counter = Counter()
    for arquivo in _registros(pasta, comeco):
        acordou = pedido = None
        ultimo = None
        try:
            linhas = arquivo.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for l in linhas:
            if '"estado"' not in l:
                continue
            try:
                e = json.loads(l)
            except ValueError:
                continue
            t = _quando(e.get("momento"))
            if t is None:
                continue
            ultimo = t
            estado = e.get("estado")
            if estado == "acordou":
                acordou = acordou or t
            elif estado == "dormiu" and acordou is not None:
                intervalos.append((acordou, t)); acordou = None
            elif estado == "pedido":
                pedido = t
                if dt.date.fromtimestamp(t) == hoje:
                    origens[e.get("origem") or "voz"] += 1
            elif estado == "resposta" and pedido is not None:
                intervalos.append((pedido, t + 30)); pedido = None
        if acordou is not None and ultimo is not None:   # o registro acabou acordado
            intervalos.append((acordou, ultimo))
    # Junta os pedaços que se cruzam e soma por dia.
    por_dia = defaultdict(float)
    juntos: list[list[float]] = []
    for a, b in sorted(intervalos):
        if juntos and a <= juntos[-1][1]:
            juntos[-1][1] = max(juntos[-1][1], b)
        else:
            juntos.append([a, b])
    for a, b in juntos:
        while a < b:
            fim_do_dia = dt.datetime.combine(dt.date.fromtimestamp(a) + dt.timedelta(days=1), dt.time()).timestamp()
            pedaco = min(b, fim_do_dia) - a
            por_dia[dt.date.fromtimestamp(a)] += pedaco
            a += pedaco
    lista = [{"dia": (hoje - dt.timedelta(days=i)).isoformat(),
              "min": round(por_dia.get(hoje - dt.timedelta(days=i), 0.0) / 60)}
             for i in reversed(range(dias))]
    return {"dias": lista, "pedidos": dict(origens)}


def montar(pasta_logs: Path, arquivo: Path = ARQUIVO, agora: float | None = None) -> dict:
    """O evento "estatisticas" inteiro (Uso + Tempo e foco)."""
    t = tempo_e_pedidos(pasta_logs, agora)
    return {"uso": uso(arquivo, agora), "conversa": t["dias"], "pedidos": t["pedidos"]}
