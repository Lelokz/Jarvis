"""Mexer nos vídeos que já estão no canal (Painel do Canal, etapa 2).

Título, descrição, tags, visibilidade e thumb. Mudou na janela (ou pelo
Jarvis), muda no YouTube na hora, e o banco do PC acompanha.
"""

from __future__ import annotations

import json

from jarvis.youtube import conta, dados

VISIBILIDADES = ("public", "unlisted", "private")
LIMITE_TITULO = 100        # regras do YouTube
LIMITE_DESCRICAO = 5000
LIMITE_TAGS = 500          # caracteres somados


class Recusado(ValueError):
    """O YouTube não aceitaria (e o motivo, em português)."""


def conferir(titulo: str, descricao: str, tags: list[str], visibilidade: str) -> None:
    if not titulo.strip():
        raise Recusado("o título não pode ficar vazio")
    if len(titulo) > LIMITE_TITULO:
        raise Recusado(f"o título passou de {LIMITE_TITULO} letras ({len(titulo)})")
    if "<" in titulo or ">" in titulo or "<" in descricao or ">" in descricao:
        raise Recusado("o YouTube não aceita < nem > no título e na descrição")
    if len(descricao.encode("utf-8")) > LIMITE_DESCRICAO:
        raise Recusado(f"a descrição passou do limite de {LIMITE_DESCRICAO} caracteres")
    if sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1) > LIMITE_TAGS:
        raise Recusado(f"as tags somadas passaram de {LIMITE_TAGS} caracteres")
    if visibilidade not in VISIBILIDADES:
        raise Recusado(f"visibilidade desconhecida: {visibilidade}")


def salvar_video(video: str, titulo: str, descricao: str, tags: list[str], visibilidade: str, yt=None) -> None:
    tags = [t.strip() for t in tags if t.strip()]
    conferir(titulo, descricao, tags, visibilidade)
    yt = yt or conta.youtube()
    # O update troca o snippet INTEIRO: pega o atual (categoria, idioma...) e muda só o que é nosso.
    atual = yt.videos().list(part="snippet,status", id=video).execute().get("items", [])
    if not atual:
        raise Recusado("esse vídeo não existe mais no canal")
    sn, st = atual[0]["snippet"], atual[0]["status"]
    snippet = {k: sn[k] for k in ("categoryId", "defaultLanguage", "defaultAudioLanguage") if k in sn}
    snippet.update(title=titulo, description=descricao, tags=tags)
    status = {k: st[k] for k in ("embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids",
                                 "publishAt") if k in st}
    status["privacyStatus"] = visibilidade
    if visibilidade != "private":
        status.pop("publishAt", None)   # tornou público/não listado: deixa de ser agendado
    yt.videos().update(part="snippet,status", body={"id": video, "snippet": snippet, "status": status}).execute()
    con = dados.abrir()
    with con:
        con.execute("UPDATE videos SET titulo = ?, descricao = ?, tags = ?, visibilidade = ?, "
                    "agendado = CASE WHEN ? = 'private' THEN agendado ELSE '' END WHERE id = ?",
                    (titulo, descricao, json.dumps(tags, ensure_ascii=False), visibilidade, visibilidade, video))
    con.close()


def trocar_thumb(video: str, imagem: str, yt=None) -> None:
    from googleapiclient.http import MediaFileUpload
    from pathlib import Path
    caminho = Path(imagem)
    if caminho.suffix.lower() not in (".jpg", ".jpeg", ".png"):
        raise Recusado("a thumb tem que ser JPG ou PNG")
    if caminho.stat().st_size > 2 * 1024 ** 2:
        raise Recusado("a thumb passou de 2 MB (limite do YouTube)")
    yt = yt or conta.youtube()
    tipo = "image/png" if caminho.suffix.lower() == ".png" else "image/jpeg"
    yt.thumbnails().set(videoId=video, media_body=MediaFileUpload(str(caminho), mimetype=tipo)).execute()
    dados.THUMBS.mkdir(parents=True, exist_ok=True)
    dados.thumb_local(video).write_bytes(caminho.read_bytes())


# -- agendar (etapa 3) ------------------------------------------------------------------

def quando_de(data: str, hora: str):
    """"14/11/2026" + "18:30" (hora do PC) -> datetime com fuso. Recusa passado."""
    import datetime as dt
    try:
        d = dt.datetime.strptime(f"{data.strip()} {hora.strip()}", "%d/%m/%Y %H:%M").astimezone()
    except ValueError:
        raise Recusado("data ou hora no formato errado (use 14/11/2026 e 18:30)") from None
    if d <= dt.datetime.now().astimezone() + dt.timedelta(minutes=5):
        raise Recusado("o agendamento tem que ser pelo menos 5 minutos no futuro")
    return d


def agendar(video: str, quando, yt=None) -> None:
    """Vídeo PRIVADO que já está no YouTube sai sozinho em `quando`."""
    import datetime as dt
    yt = yt or conta.youtube()
    atual = yt.videos().list(part="status", id=video).execute().get("items", [])
    if not atual:
        raise Recusado("esse vídeo não existe mais no canal")
    st = atual[0]["status"]
    if st.get("privacyStatus") != "private":
        raise Recusado("só dá pra agendar vídeo que está como Privado (este já saiu)")
    utc = quando.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    status = {k: st[k] for k in ("embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids") if k in st}
    status.update(privacyStatus="private", publishAt=utc)
    yt.videos().update(part="status", body={"id": video, "status": status}).execute()
    con = dados.abrir()
    with con:
        con.execute("UPDATE videos SET visibilidade = 'private', agendado = ? WHERE id = ?", (utc, video))
    con.close()


def desagendar(video: str, yt=None) -> None:
    """Tira do agendamento: continua Privado e não sai sozinho."""
    yt = yt or conta.youtube()
    atual = yt.videos().list(part="status", id=video).execute().get("items", [])
    if not atual:
        raise Recusado("esse vídeo não existe mais no canal")
    st = {k: v for k, v in atual[0]["status"].items()
          if k in ("embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids")}
    st["privacyStatus"] = "private"
    yt.videos().update(part="status", body={"id": video, "status": st}).execute()
    con = dados.abrir()
    with con:
        con.execute("UPDATE videos SET agendado = '' WHERE id = ?", (video,))
    con.close()
