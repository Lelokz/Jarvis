"""O app "Painel do Canal" (12/11/2026): as rotas /painel/* da porta remota.
Dados de EXEMPLO numa pasta temporária; nada fala com o YouTube.
"""
from __future__ import annotations

import dataclasses
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ["JARVIS_DADOS"] = tempfile.mkdtemp(prefix="jarvis-painel-remoto-")

from starlette.testclient import TestClient  # noqa: E402

import porta_remota  # noqa: E402
from jarvis import config  # noqa: E402
from jarvis.youtube import exemplo, producao  # noqa: E402

ok = falhou = 0


def checa(nome, cond, detalhe=""):
    global ok, falhou
    if cond:
        ok += 1
        print(f"  PASSOU  {nome}", flush=True)
    else:
        falhou += 1
        print(f"  FALHOU  {nome}  {detalhe}", flush=True)


def main() -> int:
    exemplo.criar()
    base = Path(os.environ["JARVIS_DADOS"])
    cfg = config.carregar()
    cfg = dataclasses.replace(cfg, remoto=dataclasses.replace(cfg.remoto, chave=str(base / "chave")))
    app = porta_remota.criar_app(cfg)
    chave = (base / "chave").read_text().strip()
    c = TestClient(app)
    h = {"Authorization": f"Bearer {chave}"}

    checa("dados sem a chave: 401", c.get("/painel/dados").status_code == 401)
    checa("dados com chave errada: 401", c.get("/painel/dados", headers={"Authorization": "Bearer x"}).status_code == 401)
    r = c.get("/painel/dados", headers=h)
    d = r.json()
    checa("dados com a chave: o pacote da janela", r.status_code == 200 and d.get("temDados") is True
          and d["canal"]["titulo"] == "Lelokz", str(d)[:200])
    checa("thumbs viram caminho da porta (nada de file://)",
          all(v["thumb"].startswith("/painel/thumb?id=") for v in d["videos"] if v["thumb"]) and
          not any("file://" in v["thumb"] for v in d["videos"]))
    vid = d["videos"][0]["id"]
    t = c.get(f"/painel/thumb?id={vid}", headers=h)
    checa("thumb com a chave: a imagem", t.status_code == 200 and t.content[:2] == b"\xff\xd8", str(t.status_code))
    checa("thumb sem a chave: 401", c.get(f"/painel/thumb?id={vid}").status_code == 401)
    checa("thumb com caminho solto: 404", c.get("/painel/thumb?id=../../token", headers=h).status_code == 404)

    antes = len(producao.listar())
    r = c.post("/painel/acao", headers=h, json={"acao": "criar_card", "campos": {"titulo": "Teste do app", "coluna": "ideia"}})
    checa("criar card pelo app", r.json().get("ok") is True and len(producao.listar()) == antes + 1, r.text)
    novo = max(producao.listar(), key=lambda x: x["id"])
    r = c.post("/painel/acao", headers=h, json={"acao": "mover_card", "card": novo["id"], "coluna": "gravando"})
    checa("mover card pelo app", r.json().get("ok") is True and
          next(x for x in producao.listar() if x["id"] == novo["id"])["coluna"] == "gravando", r.text)
    r = c.post("/painel/acao", headers=h, json={"acao": "apagar_card", "card": novo["id"]})
    checa("apagar card pelo app", r.json().get("ok") is True and len(producao.listar()) == antes, r.text)
    r = c.post("/painel/acao", headers=h, json={"acao": "mover_card"})
    checa("pedido torto: 400", r.status_code == 400, r.text)
    r = c.post("/painel/acao", headers=h, json={"acao": "voar"})
    checa("pedido desconhecido: recusado", r.json().get("ok") is False)
    nl = d.get("naoLidos", 0)
    com = d["comentarios"][0]["id"]
    c.post("/painel/acao", headers=h, json={"acao": "lido", "comentario": com})
    checa("marcar lido pelo app", c.get("/painel/dados", headers=h).json().get("naoLidos") == nl - 1)
    r = c.post("/painel/acao", headers=h, json={"acao": "dias_video", "video": vid})
    checa("dias do vídeo (o gráfico da ficha)", isinstance(r.json().get("dias"), list))
    checa("acao sem a chave: 401", c.post("/painel/acao", json={"acao": "todos_lidos"}).status_code == 401)
    v = c.get("/painel/versao")
    checa("versão do app do Painel: sem chave, 200 ou 404", v.status_code in (200, 404))
    checa("/painel/versao não cai na rota com chave", v.status_code != 401)

    print(f"\n{ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
