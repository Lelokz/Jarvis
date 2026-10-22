"""python -m jarvis.escola ler | manter | entrar

- ler: lê o Khan e o Estudante Online, grava o resumo em escola.json (que o
  Jarvis consulta quando o Léo pergunta) e notifica o que for NOVO;
- manter: só visita o Estudante Online para a sessão não cair;
- entrar: abre a janela para o Léo entrar de novo no Estudante Online.

A última linha impressa é um JSON para a vigia (vigia.py): {"novidades": [...]}.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

from . import estudante, khan

RESUMO = Path.home() / ".local/share/jarvis/escola.json"
# Marca de "o Estudante Online saiu da conta e o Léo já foi avisado": avisa
# uma vez só e para de tentar até ele entrar de novo.
DESLOGADO = Path.home() / ".local/share/jarvis/escola-deslogado"
MEDIA = 6.0  # abaixo disso a nota aparece como baixa
SEM_NOTA = "Sem avaliação ou notas não liberadas."


def notificar(texto: str) -> None:
    """Notificação no canto da tela do PC (o celular recebe pela vigia)."""
    subprocess.run(["notify-send", "-a", "Jarvis", "-i", "jarvis-atomo", "Escola", texto],
                   check=False, timeout=10)


def _avaliacoes(texto: str) -> dict[str, str]:
    """"PR1 Prova de células 28/04/2026 08:58:15 2,00" -> {"PR1 Prova de células": "2,00"}."""
    return {f"{sigla} {nome}".strip(): nota for sigla, nome, nota in
            re.findall(r"([A-Z]{2,3}\d+) (.*?) ?\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} (\d+,\d+)", texto)}


def _baixa(nota: str) -> bool:
    try:
        return float(nota.replace(",", ".")) < MEDIA
    except ValueError:
        return False


def _titulo(materia: str) -> str:
    return materia.capitalize() if materia.isupper() else materia


def novidades(antes: dict, agora: dict) -> list[str]:
    """O que apareceu desde a última leitura. Na primeira, nada (é a base)."""
    if not antes:
        return []
    saida = []
    for dia, itens in agora.get("agenda", {}).items():
        velhos = antes.get("agenda", {}).get(dia, [])
        novos = [i for i in itens if i not in velhos]
        if novos:
            data = dt.date.fromisoformat(dia).strftime("%d/%m")
            saida.append(f"Agenda {data}: " + " · ".join(novos))
    for periodo, materias in agora.get("notas", {}).items():
        for materia, texto in materias.items():
            velhas = _avaliacoes(antes.get("notas", {}).get(periodo, {}).get(materia, ""))
            for nome, nota in _avaliacoes(texto).items():
                if velhas.get(nome) != nota:
                    alerta = " (abaixo da média)" if _baixa(nota) else ""
                    saida.append(f"Nota nova em {_titulo(materia)}: {nota} em {nome}{alerta}")
    for periodo, materias in agora.get("boletim", {}).items():
        for materia, linha in materias.items():
            velha = antes.get("boletim", {}).get(periodo, {}).get(materia, {}).get("media")
            if linha.get("media") and velha != linha["media"]:
                alerta = " (abaixo da média)" if _baixa(linha["media"]) else ""
                saida.append(f"Média de {_titulo(materia)} no {periodo}: {linha['media']}{alerta}")
    return saida


def _khan_resumo(k: dict) -> dict:
    meta = k["meta_semana_minutos"]
    feitos = k["minutos_semana"] or 0
    dias = 7 - dt.date.today().weekday()  # contando hoje, até domingo
    falta = max(0, meta - feitos)
    return {**k, "faltam_minutos": falta, "por_dia_para_bater_a_meta": -(-falta // dias)}


def ler() -> list[str]:
    from playwright.sync_api import sync_playwright
    antes = json.loads(RESUMO.read_text(encoding="utf-8")) if RESUMO.exists() else {}
    resumo = {"lido_em": dt.datetime.now().isoformat(timespec="minutes"), "media_minima": MEDIA,
              "khan": antes.get("khan"), "estudante": antes.get("estudante"), "problemas": []}
    with sync_playwright() as p:
        try:
            resumo["khan"] = _khan_resumo(khan.ler(p))
            resumo["khan"]["lido_em"] = resumo["lido_em"]
        except Exception as erro:
            resumo["problemas"].append(f"Khan: {erro}")
        if DESLOGADO.exists():
            resumo["problemas"].append("Estudante Online: saiu da conta, o Léo precisa entrar de novo")
        else:
            try:
                resumo["estudante"] = estudante.ler(p)
                resumo["estudante"]["lido_em"] = resumo["lido_em"]
            except estudante.PrecisaDoLeo:
                _saiu_da_conta()
                resumo["problemas"].append("Estudante Online: saiu da conta, o Léo precisa entrar de novo")
            except Exception as erro:
                resumo["problemas"].append(f"Estudante Online: {erro}")
    novas = []
    if resumo["estudante"] is not antes.get("estudante"):  # leu agora
        novas = novidades(antes.get("estudante") or {}, resumo["estudante"])
    RESUMO.touch(mode=0o600, exist_ok=True)
    RESUMO.write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    if novas:
        notificar("\n".join(novas))
    return novas


def _saiu_da_conta() -> None:
    DESLOGADO.touch()
    notificar("O Estudante Online saiu da sua conta. Quando estiver no PC, "
              "pede pro Jarvis: \"entra no Estudante Online\".")


def manter() -> list[str]:
    if DESLOGADO.exists():
        return []
    try:
        if not estudante.manter():
            _saiu_da_conta()
            return ["O Estudante Online saiu da sua conta."]
    except estudante.PrecisaDoLeo:
        _saiu_da_conta()
    return []


def entrar() -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        navegador, _ = estudante.entrar_com_o_leo(p)
        estudante.fechar_janela(navegador)
    DESLOGADO.unlink(missing_ok=True)
    print("Entrou. A sessão está guardada.")


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else "ler"
    if comando == "entrar":
        entrar()
        sys.exit(0)
    novas = ler() if comando == "ler" else manter()
    print(json.dumps({"novidades": novas}, ensure_ascii=False))
