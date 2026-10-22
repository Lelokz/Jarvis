"""Khan Academy: os minutos de aprendizagem da semana, do jeito que o Khan conta.

Usa o perfil do navegador do Jarvis (navegador.py), onde o Léo entrou com o
Google: o cookie do Khan dura semanas.
"""

from __future__ import annotations

import re

from .navegador import ARGS, CHROMIUM, PERFIL

PROGRESSO = "https://pt.khanacademy.org/profile/me/progress"
META_SEMANA_MIN = 6 * 60  # a meta do padrasto: 6 h por semana


class Deslogado(Exception):
    pass


def ler(playwright) -> dict:
    contexto = playwright.chromium.launch_persistent_context(
        str(PERFIL), executable_path=str(CHROMIUM), headless=True, args=ARGS)
    try:
        pagina = contexto.new_page()
        pagina.goto(PROGRESSO, wait_until="load", timeout=60000)
        try:
            pagina.wait_for_selector("text=minutos totais de aprendizagem", timeout=30000)
        except Exception:
            raise Deslogado("o Khan não abriu o progresso (deslogou?)") from None
        pagina.wait_for_timeout(2000)
        texto = pagina.inner_text("body")
        total = re.search(r"(\d+)\s*minutos totais de aprendizagem", texto)
        exercicios = re.search(r"(\d+)\s*minutos de exercícios", texto)
        atividades = []
        for linha in pagina.locator("tr").all()[1:]:
            celulas = [c.inner_text().strip() for c in linha.locator("td").all()]
            if len(celulas) >= 6:
                nome = " — ".join(p for p in celulas[0].split("\n") if p.strip())
                atividades.append({"atividade": nome, "quando": celulas[1],
                                   "acertos": celulas[4], "minutos": celulas[5]})
        return {
            "minutos_semana": int(total.group(1)) if total else None,
            "minutos_exercicios_semana": int(exercicios.group(1)) if exercicios else None,
            "meta_semana_minutos": META_SEMANA_MIN,
            "atividades_semana": atividades,
        }
    finally:
        contexto.close()
