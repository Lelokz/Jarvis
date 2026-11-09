"""Arquivo do WhatsApp: guarda tudo, inclusive o que foi apagado."""
import sqlite3
from pathlib import Path

from .memoria_viva import DB


def guardar(msg: dict):
    con = sqlite3.connect(DB)
    with con:
        con.execute(
            "INSERT OR REPLACE INTO arquivo_mensagens"
            "(id, chat, autor, ts, texto, midia, apagada, tipo) VALUES (?,?,?,?,?,?,?,?)",
            (msg["id"], msg.get("chat"), msg.get("autor"), msg.get("ts", 0),
             msg.get("texto"), msg.get("midia"), int(msg.get("apagada", 0)),
             msg.get("tipo", "texto")))
    con.close()


def apagar(id_msg: str):
    con = sqlite3.connect(DB)
    with con:
        con.execute("UPDATE arquivo_mensagens SET apagada = 1 WHERE id = ?", (id_msg,))
    con.close()


def conversa(chat: str, limite: int = 200) -> list[dict]:
    con = sqlite3.connect(DB)
    linhas = con.execute(
        "SELECT autor, ts, texto, midia, apagada, tipo FROM arquivo_mensagens "
        "WHERE chat = ? ORDER BY ts DESC LIMIT ?", (chat, limite)).fetchall()
    con.close()
    return [dict(zip(("autor", "ts", "texto", "midia", "apagada", "tipo"), l))
            for l in reversed(linhas)]


def procurar(termo: str, limite: int = 50) -> list[dict]:
    con = sqlite3.connect(DB)
    linhas = con.execute(
        "SELECT chat, autor, ts, texto, apagada FROM arquivo_mensagens "
        "WHERE texto LIKE ? ORDER BY ts DESC LIMIT ?", (f"%{termo}%", limite)).fetchall()
    con.close()
    return [dict(zip(("chat", "autor", "ts", "texto", "apagada"), l)) for l in linhas]