"""O Painel do Canal pelo celular (app "Painel do Canal", 12/11/2026).

A porta remota (porta_remota.py) chama estas funções. O PC guarda o token do
YouTube; o app só mostra e pede. Tudo o que a janela faz (jarvis/youtube/
janela.py), menos o que precisa do PC na mão (trocar thumb, abrir arquivo).
"""

from __future__ import annotations

import datetime as dt
import threading

from jarvis.youtube import comentarios, conta, dados, editar, producao

# Uma coisa por vez falando com o YouTube, igual à janela.
_trava = threading.Lock()


def pacote() -> dict:
    """O mesmo pacote da janela, com as thumbs como caminho da porta remota."""
    r = dados.para_janela()
    for v in r.get("videos", []):
        v["thumb"] = f"/painel/thumb?id={v['id']}" if v.get("thumb") else ""
    return r


def thumb(video: str):
    """O arquivo da thumb, só de um vídeo que existe no banco (nada de caminho solto)."""
    if not video or "/" in video or "." in video:
        return None
    arq = dados.thumb_local(video)
    return arq if arq.is_file() else None


def _youtube(fazer, ok: str) -> dict:
    if not _trava.acquire(blocking=False):
        return {"ok": False, "texto": "Espera terminar o que está fazendo."}
    try:
        fazer()
        return {"ok": True, "texto": ok}
    except (editar.Recusado, conta.SemConexao) as e:
        return {"ok": False, "texto": f"Não deu: {e}."}
    except Exception as e:  # noqa: BLE001 - erro do YouTube vira aviso no app
        return {"ok": False, "texto": f"O YouTube recusou: {e}"}
    finally:
        _trava.release()


def _no_pc(fazer, ok: str = "") -> dict:
    try:
        fazer()
        return {"ok": True, "texto": ok}
    except ValueError as e:
        return {"ok": False, "texto": f"Não deu: {e}."}


def acao(p: dict) -> dict:
    """Um pedido do app: {"acao": ..., campos}. Devolve {"ok", "texto"}."""
    a = p.get("acao")
    s = lambda k: str(p.get(k) or "")  # noqa: E731
    if a == "sincronizar":
        return _youtube(dados.sincronizar, "Atualizado agora.")
    if a == "salvar":
        tags = [t.strip() for t in s("tags").split(",")]
        return _youtube(lambda: editar.salvar_video(s("video"), s("titulo"), s("descricao"), tags, s("visibilidade")),
                        "Salvo no YouTube.")
    if a == "agendar":
        try:
            quando = editar.quando_de(s("data"), s("hora"))
        except editar.Recusado as e:
            return {"ok": False, "texto": f"Não deu: {e}."}
        return _youtube(lambda: editar.agendar(s("video"), quando), f"Agendado pra {quando:%d/%m às %H:%M}.")
    if a == "reagendar_dia":
        atual = next((v for v in dados.para_janela().get("videos", []) if v["id"] == s("video")), None)
        if not atual or not atual.get("agendado"):
            return {"ok": False, "texto": "Esse vídeo não está agendado."}
        antes = dt.datetime.fromisoformat(atual["agendado"].replace("Z", "+00:00")).astimezone()
        dia = dt.date.fromisoformat(s("dia"))
        return acao({"acao": "agendar", "video": s("video"), "data": f"{dia:%d/%m/%Y}", "hora": f"{antes:%H:%M}"})
    if a == "desagendar":
        return _youtube(lambda: editar.desagendar(s("video")), "Tirado do agendamento (continua privado).")
    if a == "responder":
        return _youtube(lambda: comentarios.responder(s("comentario"), s("texto")), "Resposta publicada.")
    if a == "lido":
        comentarios.marcar_lido([s("comentario")])
        return {"ok": True, "texto": ""}
    if a == "todos_lidos":
        comentarios.marcar_lido(None)
        return {"ok": True, "texto": "Tudo marcado como lido."}
    if a == "criar_card":
        return _no_pc(lambda: producao.criar(dict(p.get("campos") or {})), "Card criado.")
    if a == "salvar_card":
        return _no_pc(lambda: producao.atualizar(int(p["card"]), dict(p.get("campos") or {})), "Card salvo.")
    if a == "mover_card":
        return _no_pc(lambda: producao.mover(int(p["card"]), s("coluna")))
    if a == "apagar_card":
        return _no_pc(lambda: producao.apagar(int(p["card"])), "Card apagado.")
    if a == "dias_video":
        return {"ok": True, "texto": "", "dias": dados.dias_do_video(s("video"))}
    return {"ok": False, "texto": "Pedido desconhecido."}
