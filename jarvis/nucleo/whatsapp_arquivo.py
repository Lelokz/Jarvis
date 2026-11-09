"""Arquivo do WhatsApp: guarda tudo, inclusive o que foi apagado."""
import sys
import time

from .memoria_viva import _abrir as _conectar  # cria as tabelas se faltar


def guardar(msg: dict):
    con = _conectar()
    with con:
        con.execute(
            "INSERT OR REPLACE INTO arquivo_mensagens"
            "(id, chat, autor, ts, texto, midia, apagada, tipo) VALUES (?,?,?,?,?,?,?,?)",
            (msg["id"], msg.get("chat"), msg.get("autor"), msg.get("ts", 0),
             msg.get("texto"), msg.get("midia"), int(msg.get("apagada", 0)),
             msg.get("tipo", "texto")))
    con.close()


def apagar(id_msg: str):
    con = _conectar()
    with con:
        con.execute("UPDATE arquivo_mensagens SET apagada = 1 WHERE id = ?", (id_msg,))
    con.close()


def conversa(chat: str, limite: int = 200) -> list[dict]:
    con = _conectar()
    linhas = con.execute(
        "SELECT autor, ts, texto, midia, apagada, tipo FROM arquivo_mensagens "
        "WHERE chat = ? ORDER BY ts DESC LIMIT ?", (chat, limite)).fetchall()
    con.close()
    return [dict(zip(("autor", "ts", "texto", "midia", "apagada", "tipo"), l))
            for l in reversed(linhas)]


def procurar(termo: str, limite: int = 50) -> list[dict]:
    con = _conectar()
    linhas = con.execute(
        "SELECT chat, autor, ts, texto, apagada FROM arquivo_mensagens "
        "WHERE texto LIKE ? ORDER BY ts DESC LIMIT ?", (f"%{termo}%", limite)).fetchall()
    con.close()
    return [dict(zip(("chat", "autor", "ts", "texto", "apagada"), l)) for l in linhas]


def main(a: list[str]) -> int:
    """python -m jarvis.nucleo.whatsapp_arquivo procurar <termo> | conversa <jid do chat>"""
    if len(a) >= 2 and a[0] == "procurar":
        linhas = procurar(" ".join(a[1:]))
    elif len(a) == 2 and a[0] == "conversa":
        linhas = conversa(a[1])
    else:
        print(main.__doc__)
        return 1
    for m in linhas:
        quando = time.strftime("%d/%m/%Y %H:%M", time.localtime(m["ts"] or 0))
        apagada = " (APAGADA)" if m["apagada"] else ""
        print(f"[{quando}] {m.get('chat', '')} {m['autor']}{apagada}: {m['texto'] or m.get('midia') or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
