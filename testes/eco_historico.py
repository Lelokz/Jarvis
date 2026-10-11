"""Assistente falso: já nasce com conversa antiga e responde ao que chega.

Serve para dois testes da passada 4, nenhum deles precisando de GPU, modelo ou
microfone:
  - o histórico ponta a ponta (a janela abre e a conversa de antes está lá);
  - a medição de quadros, porque manda estado e nível de verdade.

    .venv/bin/python testes/eco_historico.py <socket> [--pulsar]
"""
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from jarvis.ponte.servidor import Servidor  # noqa: E402

caminho = sys.argv[1]
pulsar = "--pulsar" in sys.argv

srv = Servidor(caminho, fila_max=256,
               sessao={"v": 1, "nome": "Jarvis", "log": str(RAIZ / "rascunho/falso.jsonl")})
srv.iniciar()

# A conversa de ANTES de a janela abrir: é exatamente o caso que o histórico
# existe para cobrir.
anteriores = [
    ("voce_disse", {"texto": "abre o loft", "origem": "voz"}),
    ("jarvis_disse", {"texto": "Abri o Loft.", "acao": "abrir:loft", "perguntando": False}),
    ("voce_disse", {"texto": "que horas são?", "origem": "voz"}),
    ("jarvis_disse", {"texto": "São seis e meia da tarde.", "acao": None,
                      "perguntando": False}),
    ("voce_disse", {"texto": "renomeia o relatório para proposta", "origem": "texto"}),
    ("jarvis_disse", {"texto": "Renomeio relatório para proposta. Pode?", "acao": None,
                      "perguntando": True}),
]
for ev, dados in anteriores:
    srv.receber({"ev": ev, **dados})
srv.receber({"ev": "estado", "estado": "dormindo"})
print("PRONTO", flush=True)

while True:
    texto = srv.proximo_texto()
    if texto is not None:
        srv.receber({"ev": "estado", "estado": "pensando"})
        srv.receber({"ev": "voce_disse", "texto": texto, "origem": "texto"})
        time.sleep(0.5)
        srv.receber({"ev": "estado", "estado": "falando"})
        srv.receber({"ev": "jarvis_disse", "texto": "Pronto.", "acao": None,
                     "perguntando": False})
        time.sleep(0.4)
        srv.receber({"ev": "estado", "estado": "ouvindo"})
    if pulsar:
        # Estado mais pesado da esfera, para a medição de quadros.
        srv.receber({"ev": "estado", "estado": "pensando"})
        srv.receber({"ev": "nivel", "v": 0.4})
    time.sleep(0.066)
