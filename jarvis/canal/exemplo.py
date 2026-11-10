"""Dados de EXEMPLO para fotografar a janela antes de o Léo conectar o
YouTube. Tudo inventado; só existe numa pasta temporária (JARVIS_DADOS).
"""

from __future__ import annotations

import datetime as dt
import json
import random
import subprocess
import time
from pathlib import Path

from jarvis.canal import dados

TITULOS = ["DOORS: zerei o HOTEL+ sem morrer?", "Minecraft 100% #6: o Wither apareceu", "A HISTÓRIA COMPLETA de Doors",
           "Minecraft 100% #5: fomos pro End", "Roblox mais difícil que já joguei", "Minecraft 100% #4: a vila tava amaldiçoada",
           "Doors Floor 2: tudo que mudou", "Minecraft 100% #3: diamantes e lava", "O segredo do Seek que ninguém viu",
           "Minecraft 100% #2: a primeira noite", "Joguei Doors com o Lucas e deu ruim", "Minecraft 100% #1: começou",
           "Pressure: o jogo inspirado em Doors", "A lore de The Rooms explicada", "Testei os piores jogos do Roblox",
           "Doors mas eu só posso agachar", "5 mistérios de Doors"]
CORES = ["#3b1d6e", "#1d3b6e", "#6e1d4a", "#1d6e5a", "#6e4a1d", "#2d1d6e", "#5a1d6e"]


def criar(fonte: Path | None = None) -> None:
    random.seed(7)
    hoje = dt.date.today()
    agora = dt.datetime.now(dt.timezone.utc)
    con = dados.abrir()
    con.execute("INSERT OR REPLACE INTO canal VALUES ('UC_EXEMPLO','Lelokz',913,58321,19,'UU_EXEMPLO','',?)", (time.time() - 600,))
    lista = [("agendado1", "Minecraft 100% #7: o dragão", None, (agora + dt.timedelta(days=2)).replace(hour=21, minute=0)),
             ("agendado2", "DOORS: o andar secreto", None, (agora + dt.timedelta(days=6)).replace(hour=18, minute=0))]
    for i, t in enumerate(TITULOS):
        lista.append((f"v{i}", t, agora - dt.timedelta(days=3 + i * 6, hours=random.randint(0, 5)), None))
    for vid, titulo, pub, ag in lista:
        views = 0 if ag else int(random.uniform(600, 4200) * (1.6 if "DOORS" in titulo else 1))
        if vid == "v0":
            views = 1480
        con.execute("INSERT OR REPLACE INTO videos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            vid, titulo, f"{titulo}\n\nSe inscreve no canal e ativa o sininho!\n#doors #minecraft #roblox",
            (pub or agora).isoformat().replace("+00:00", "Z"), random.randint(9 * 60, 48 * 60),
            views, views // 18, views // 90, "private" if ag else ("unlisted" if vid == "v9" else "public"),
            ag.isoformat().replace("+00:00", "Z") if ag else "", "", json.dumps(["doors", "roblox", "lelokz"]), time.time()))
        if pub:
            dia0 = pub.date()
            for k in range(min(30, (hoje - dia0).days + 1)):
                v = int(views * 0.33 * (0.62 ** k)) + random.randint(0, 8)
                if vid == "v0":
                    v = int(v * 1.25)
                con.execute("INSERT OR REPLACE INTO video_dias VALUES (?,?,?)", (vid, (dia0 + dt.timedelta(days=k)).isoformat(), v))
    for k in range(365):
        dia = hoje - dt.timedelta(days=k)
        base = 70 + 40 * (1 - k / 365) + 25 * (dia.weekday() >= 5)
        v = int(base + random.randint(-15, 25) + (90 if k in (3, 4) else 0))
        con.execute("INSERT OR REPLACE INTO dias VALUES (?,?,?,?,?,?)",
                    (dia.isoformat(), v, v * 6, random.randint(0, 3), random.randint(0, 1), v // 20))
    con.commit()
    con.close()
    from jarvis.canal import producao
    em = lambda d: (hoje + dt.timedelta(days=d)).isoformat()  # noqa: E731
    for campos in ({"titulo": "Minecraft 100% ep 7: o dragão", "jogo": "Minecraft", "coluna": "pronto"},
                   {"titulo": "DOORS andar secreto", "jogo": "Doors", "coluna": "editando",
                    "arquivos": ["/mnt/x/Gravacoes/2026-11-07 20-14-02.mov", "/mnt/x/Gravacoes/previa-doors.mp4"]},
                   {"titulo": "Os 5 piores sustos de Doors", "jogo": "Doors", "coluna": "pronto"},
                   {"titulo": "Dead Rails com o Lucas", "jogo": "Roblox", "coluna": "editando",
                    "arquivos": ["/mnt/x/Gravacoes/2026-11-08 19-02-11.mov"]},
                   {"titulo": "Pressure com o Lucas", "jogo": "Roblox", "coluna": "gravando", "data": em(9)},
                   {"titulo": "A lore de Doors parte 2", "jogo": "Doors", "coluna": "ideia", "data": em(12), "notas": "narração separada"},
                   {"titulo": "Minecraft 100% ep 8", "jogo": "Minecraft", "coluna": "ideia", "data": em(16)},
                   {"titulo": "Testar 10 jogos de terror do Roblox", "jogo": "Roblox", "coluna": "ideia"},
                   {"titulo": "DOORS: zerei o hotel", "jogo": "Doors", "coluna": "agendado"}):
        producao.criar(campos)
    # Thumbs de mentira: um degradê com o título (o ffmpeg desenha).
    dados.THUMBS.mkdir(parents=True, exist_ok=True)
    for n, (vid, titulo, _, _) in enumerate(lista):
        cor = CORES[n % len(CORES)]
        texto = titulo.upper().replace(":", "\\:").replace("'", "").replace("%", "\\%")
        filtro = f"drawtext=text='{texto}':fontcolor=white:fontsize=58:x=60:y=h-text_h-70:borderw=3:bordercolor=black@0.4"
        if fonte:
            filtro = filtro.replace("drawtext=", f"drawtext=fontfile='{fonte}':")
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"gradients=s=1280x720:c0={cor}:c1=#0b0a10:x0=0:y0=0:x1=1280:y1=720:nb_colors=2",
                        "-vf", filtro, "-frames:v", "1", "-q:v", "4", str(dados.thumb_local(vid))],
                       capture_output=True)
