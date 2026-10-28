"""Roda as peças da NOVA numa pasta de usuário vazia (HOME falso), sem
microfone nem som: o que um tester tem logo depois de instalar.

    mkdir -p rascunho/casa-vazia rascunho/casa-vazia-run
    ./contido.sh -m 2G -- env HOME=$PWD/rascunho/casa-vazia \
        XDG_RUNTIME_DIR=$PWD/rascunho/casa-vazia-run PATH=/usr/bin:/bin \
        .venv/bin/python testes/testar_pc_novo.py

Esperado: só o quem_fala dá ERRO (sem o perfil da voz; o Ciclo desliga o
reconhecimento) e o Claude sem `~/.local/bin/claude` também. Nenhuma conexão
"conectado" e nada criado além de ~/.local/share/jarvis/casa.
"""
import os, sys, time, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
assert "casa-vazia" in os.environ["HOME"], "rode com HOME falso"

def passo(nome, f):
    try:
        r = f()
        print(f"[ok]   {nome}: {r!r}"[:400])
        return r
    except BaseException as e:
        print(f"[ERRO] {nome}: {e.__class__.__name__}: {e}"[:400])
        traceback.print_exc(limit=3, file=sys.stdout)

from jarvis import config, ajustes, conexoes
cfg = passo("config", lambda: config.carregar(None) and "carregou") and config.carregar(None)
passo("ajustes", ajustes.ler)
passo("conexoes", lambda: conexoes.estado(cfg, ajustes.ler(), set()))
from jarvis.quem_fala import QuemFala
passo("quem_fala", lambda: QuemFala().perfil)
from jarvis.nucleo.whatsapp import WhatsApp
w = cfg.whatsapp
wa = passo("whatsapp", lambda: WhatsApp(w.banco, w.api, w.avisar_grupos))
passo("whatsapp.disponivel", lambda: wa.disponivel())
from jarvis.agente.agente import Agente
ag = passo("agente", lambda: Agente(cfg.agente, cfg.persona.nome, whatsapp=wa, persona_cfg=cfg.persona))
if ag:
    passo("memoria_para_janela", lambda: ag.memoria_para_janela() if callable(getattr(ag, "memoria_para_janela", None)) else "?")
    from jarvis.agente import sessoes
    passo("sessoes", lambda: sessoes.listar(ag.casa))
    from jarvis.nucleo import recados
    passo("recados", lambda: recados.vencidos(ag.casa / recados.NOME))
    passo("cerebro", lambda: ag.cerebro)
    passo("iniciar (Claude)", lambda: ag.iniciar())
from jarvis import memorias
passo("memorias.listar", lambda: memorias.listar() if hasattr(memorias, "listar") else dir(memorias))
from jarvis.grupo.familia import GrupoFamilia
g = passo("grupo", lambda: GrupoFamilia(wa, cfg.agente.binario, "sonnet"))
if g:
    passo("grupo._uma_volta", lambda: g._uma_volta())
from jarvis.nucleo import aprovacoes
passo("aprovacoes", lambda: aprovacoes.pendentes())
from jarvis import som
passo("som.disponivel", som.disponivel)
print("\nArquivos criados no HOME falso:")
for p in sorted(Path(os.environ["HOME"]).rglob("*")):
    print("  ", p.relative_to(os.environ["HOME"]))
