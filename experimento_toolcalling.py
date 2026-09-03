#!/usr/bin/env python3
"""Etapa 1, Fase 1 — EXPERIMENTO de tool calling. Não é implementação.

Resolve a pendência §8.6 do ESCOPO: *"testar tool calling do qwen3:8b em
português antes de construir qualquer coisa em cima. Se falhar feio, a
arquitetura muda."*

**Sem microfone e sem voz.** A entrada são frases de texto, porque o que está
sob teste é o modelo, não o Whisper. Misturar os dois esconderia de quem é o
erro — e essa é a mesma linha núcleo/cliente do ESCOPO §4, aplicada ao teste.

Mede o que decide a Etapa 1:

  1. o modelo chama `abrir` quando deve, e NÃO chama quando não deve
  2. o nome que ele extrai, passado pela tabela, chega no atalho certo
  3. quanto custa por comando com o modelo quente
  4. quanto custa o primeiro comando com o modelo frio — o número da decisão
     de `keep_alive`

Compara duas formas de perguntar: com o modelo **cego** para a tabela (o
desenho do ESCOPO: ele só extrai o nome) e com a **lista** dos nomes no prompt.
A diferença entre as duas é um resultado, não um detalhe.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

from jarvis.nucleo.atalhos import Desfecho, Tabela

RAIZ = Path(__file__).resolve().parent
OLLAMA = "http://localhost:11434"
MODELO = "qwen3:8b"
REGUA = "─" * 74


@dataclass(frozen=True)
class Caso:
    frase: str
    esperado: str | None  # nome do atalho, ou None se não é para abrir nada


# O conjunto cobre o que o Léo fala de verdade, inclusive o que dá errado.
CASOS = [
    # diretas
    Caso("abre o loft", "loft"),
    Caso("abre gravações", "gravações"),
    Caso("abre o projeto loft", "projeto loft"),
    # com enfeite
    Caso("abre o projeto loft pra mim", "projeto loft"),
    Caso("põe o loft na tela", "loft"),
    Caso("abre a pasta de gravações", "gravações"),
    Caso("dá uma aberta no loft aí", "loft"),
    # erros de transcrição do Whisper — é assim que a frase chega de verdade
    Caso("abre o lofti", "loft"),
    Caso("abre gravasoes", "gravações"),
    Caso("abre o projeto lofit", "projeto loft"),
    # negativas: não pode chamar abrir
    Caso("que horas são?", None),
    Caso("tudo bem?", None),
    Caso("obrigado", None),
    Caso("toca uma música", None),
    Caso("qual a temperatura da GPU?", None),
]

FERRAMENTA = {
    "type": "function",
    "function": {
        "name": "abrir",
        "description": (
            "Abre uma coisa no computador do usuário: um site, uma pasta ou um "
            "projeto. Use apenas quando o usuário pedir para abrir, mostrar ou "
            "acessar alguma coisa."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nome": {
                    "type": "string",
                    "description": (
                        "O nome da coisa que o usuário pediu para abrir, "
                        "exatamente como ele falou, sem artigos e sem verbos."
                    ),
                }
            },
            "required": ["nome"],
        },
    },
}


def perguntar(frase: str, nomes: list[str] | None) -> tuple[str | None, float, float]:
    """Manda a frase ao modelo. Devolve (nome extraído, segundos, carga)."""
    mensagens = []
    if nomes:
        mensagens.append(
            {
                "role": "system",
                "content": (
                    "As coisas que você sabe abrir são exatamente estas: "
                    + ", ".join(f'"{n}"' for n in nomes)
                    + ". Ao chamar a função, use o nome desta lista que "
                    "corresponde ao pedido."
                ),
            }
        )
    mensagens.append({"role": "user", "content": frase})

    inicio = time.monotonic()
    r = requests.post(
        f"{OLLAMA}/api/chat",
        json={
            "model": MODELO,
            "messages": mensagens,
            "tools": [FERRAMENTA],
            "stream": False,
            # Sem "thinking": é latência pura num modelo que só precisa
            # escolher uma função e extrair uma palavra.
            "think": False,
        },
        timeout=300,
    )
    decorrido = time.monotonic() - inicio
    r.raise_for_status()
    d = r.json()
    carga = d.get("load_duration", 0) / 1e9

    chamadas = d.get("message", {}).get("tool_calls") or []
    if not chamadas:
        return None, decorrido, carga
    return chamadas[0]["function"]["arguments"].get("nome"), decorrido, carga


def rodar(tabela: Tabela, nomes: list[str] | None, rotulo: str) -> dict:
    print(f"\n{REGUA}\n  VARIANTE: {rotulo}\n{REGUA}")
    print(f"  {'frase':<32} {'extraiu':<15} {'resolveu':<15} {'':<9} {'s':>5}")
    print("  " + "-" * 72)

    acertos_decisao = 0
    diretos = 0          # resolveu certo e sem perguntar
    com_pergunta = 0     # resolveu certo, mas vai perguntar antes
    errados = []
    tempos = []
    linhas = []

    for caso in CASOS:
        nome, seg, _ = perguntar(caso.frase, nomes)
        tempos.append(seg)

        chamou = nome is not None
        devia = caso.esperado is not None
        decisao_ok = chamou == devia
        acertos_decisao += decisao_ok

        resolvido, desfecho = None, "—"
        if chamou:
            c = tabela.casar(nome)
            desfecho = c.desfecho.name
            resolvido = c.atalho.nome if c.atalho else None

        marca = " "
        if devia and resolvido == caso.esperado:
            if desfecho == Desfecho.CERTO.name:
                diretos += 1
            else:
                com_pergunta += 1
                marca = "?"
        elif not decisao_ok or (devia and resolvido != caso.esperado):
            errados.append((caso, nome, resolvido))
            marca = "X"

        print(
            f"{marca} {caso.frase:<32} {str(nome or '—'):<15} "
            f"{str(resolvido or '—'):<15} {desfecho:<9} {seg:>5.2f}"
        )
        linhas.append(
            {
                "frase": caso.frase,
                "esperado": caso.esperado,
                "extraiu": nome,
                "resolveu": resolvido,
                "desfecho": desfecho,
                "decisao_ok": decisao_ok,
                "segundos": round(seg, 3),
            }
        )

    n = len(CASOS)
    positivos = sum(1 for c in CASOS if c.esperado)
    print("  " + "-" * 72)
    print(f"  decisão certa (chamou/não chamou)   {acertos_decisao}/{n}"
          f"   {acertos_decisao / n:.0%}")
    print(f"  resolveu direto, sem perguntar      {diretos}/{positivos}"
          f"   {diretos / positivos:.0%}")
    print(f"  resolveu certo, mas perguntando     {com_pergunta}/{positivos}")
    print(f"  ERRADOS                             {len(errados)}")
    for caso, nome, resolvido in errados:
        print(f"      \"{caso.frase}\" → extraiu {nome!r} → {resolvido!r}"
              f"  (esperado {caso.esperado!r})")
    print(f"  latência por comando (quente)       "
          f"mín {min(tempos):.2f}s · média {sum(tempos)/len(tempos):.2f}s · "
          f"máx {max(tempos):.2f}s")

    return {
        "variante": rotulo,
        "decisao": f"{acertos_decisao}/{n}",
        "diretos": f"{diretos}/{positivos}",
        "com_pergunta": com_pergunta,
        "errados": len(errados),
        "latencia_media_s": round(sum(tempos) / len(tempos), 3),
        "linhas": linhas,
    }


def medir_carga_fria() -> float:
    """Descarrega o modelo e mede o custo do primeiro comando.

    É o número que decide o `keep_alive`: com 5 minutos, é isto que o Léo
    espera se falar depois de um período parado.
    """
    requests.post(
        f"{OLLAMA}/api/chat",
        json={"model": MODELO, "messages": [], "keep_alive": 0},
        timeout=60,
    )
    time.sleep(3)  # dar tempo de o Ollama liberar a VRAM
    _, seg, carga = perguntar("abre o loft", None)
    return seg, carga


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Etapa 1 — experimento de tool calling")
    p.add_argument("--sem-carga-fria", action="store_true",
                   help="pula a medição de carga a frio (que descarrega o modelo)")
    args = p.parse_args(argv)

    try:
        requests.get(f"{OLLAMA}/api/tags", timeout=5).raise_for_status()
    except Exception:
        print(f"\nOllama não responde em {OLLAMA}.\n"
              "  Suba com:  ollama serve\n", file=sys.stderr)
        return 1

    tabela = Tabela.carregar(RAIZ / "atalhos.toml")
    nomes = [a.nome for a in tabela.atalhos]

    print(f"\nExperimento de tool calling — {MODELO}")
    print(f"  atalhos na tabela   {len(tabela)}: {', '.join(nomes)}")
    print(f"  frases de teste     {len(CASOS)}"
          f"  ({sum(1 for c in CASOS if c.esperado)} positivas, "
          f"{sum(1 for c in CASOS if not c.esperado)} negativas)")

    fria = None
    if not args.sem_carga_fria:
        print("\n  medindo carga a frio (descarrega e recarrega o modelo)...", flush=True)
        seg, carga = medir_carga_fria()
        fria = {"primeiro_comando_s": round(seg, 2), "load_duration_s": round(carga, 2)}
        print(f"  primeiro comando com o modelo frio: {seg:.2f}s "
              f"(sendo {carga:.2f}s só de carga)")

    resultados = [
        rodar(tabela, None, "CEGO — o modelo não vê a tabela (desenho do ESCOPO)"),
        rodar(tabela, nomes, "COM LISTA — os nomes vão no prompt"),
    ]

    destino = RAIZ / "medicoes"
    destino.mkdir(exist_ok=True)
    caminho = destino / f"etapa1-toolcalling-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    with caminho.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"tipo": "sessao", "modelo": MODELO,
                            "momento": datetime.now().isoformat(timespec="seconds"),
                            "carga_fria": fria,
                            "atalhos": nomes}, ensure_ascii=False) + "\n")
        for r in resultados:
            f.write(json.dumps({"tipo": "variante", **r}, ensure_ascii=False) + "\n")

    print(f"\n{REGUA}\n  medições em {caminho.relative_to(RAIZ)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
