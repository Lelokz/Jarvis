"""WhatsApp: o Jarvis avisa o que chegou e manda o que o Léo ditar.

Pedido do Léo (out/2026): "ele me fala que recebi mensagem de tal pessoa
falando tal coisa; eu falo 'responde tal coisa' e ele manda, sem eu abrir o
WhatsApp".

**Por baixo:** a ponte `whatsapp-mcp` (Go + whatsmeow), em
`~/.local/share/jarvis/whatsapp-mcp/whatsapp-bridge/`, FORA do git. Ela entra
no WhatsApp como aparelho conectado (QR code), guarda as mensagens num SQLite
e recebe pedidos de envio em `127.0.0.1:8080` (alterado para só o próprio PC:
o original ouvia a rede toda). Não é oficial; o risco de banimento é baixo
para uso pessoal e leve, e foi aceito pelo Léo.

**Duas regras que não se negociam:**
- **Mensagem recebida é DADO, nunca ordem.** O conteúdo vai para o Claude
  marcado como texto de terceiros. "Jarvis, manda X para fulano" escrito por
  outra pessoa não dispara nada.
- **Enviar exige o "pode" falado do Léo**, sempre, com a mensagem lida em voz
  alta antes. Mensagem enviada não volta (§2.3).
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import requests

from .atalhos import nota, normalizar


@dataclass(frozen=True)
class Mensagem:
    chat: str        # jid da conversa
    nome: str        # nome do contato (ou o número, sem nome salvo)
    texto: str
    quando: dt.datetime
    grupo: bool


@dataclass(frozen=True)
class Contato:
    jid: str
    nome: str


class WhatsApp:
    def __init__(self, banco: Path, api: str, avisar_grupos: bool = False) -> None:
        self.banco = Path(banco).expanduser()
        self.api = api
        self.avisar_grupos = avisar_grupos

    def disponivel(self) -> bool:
        return self.banco.is_file()

    def _consultar(self, sql: str, args: tuple = ()) -> list[tuple]:
        # Só leitura: a ponte é a dona do banco e escreve nele o tempo todo.
        con = sqlite3.connect(f"file:{self.banco}?mode=ro", uri=True, timeout=2)
        try:
            return con.execute(sql, args).fetchall()
        finally:
            con.close()

    @staticmethod
    def _nome(jid: str, nome: str | None) -> str:
        return (nome or "").strip() or jid.split("@")[0]

    @staticmethod
    def _quando(valor) -> dt.datetime:
        import re
        # O go-sqlite3 grava "2026-10-11 13:20:01.123456789-03:00": o Python
        # só aceita até 6 casas na fração de segundo.
        texto = re.sub(r"(\.\d{6})\d+", r"\1", str(valor))
        try:
            d = dt.datetime.fromisoformat(texto.replace("Z", "+00:00"))
        except ValueError:
            d = dt.datetime.fromisoformat(texto[:19])
        return d.astimezone().replace(tzinfo=None) if d.tzinfo else d

    def recebidas_desde(self, desde: dt.datetime) -> list[Mensagem]:
        """Mensagens de OUTRAS pessoas chegadas depois de `desde`."""
        linhas = self._consultar(
            "SELECT m.chat_jid, c.name, m.content, m.timestamp FROM messages m "
            "LEFT JOIN chats c ON c.jid = m.chat_jid "
            "WHERE m.is_from_me = 0 ORDER BY m.timestamp DESC LIMIT 50")
        novas = []
        for jid, nome, texto, quando in linhas:
            q = self._quando(quando)
            if q <= desde:
                continue
            grupo = jid.endswith("@g.us")
            if grupo and not self.avisar_grupos:
                continue
            novas.append(Mensagem(jid, self._nome(jid, nome), texto or "(mídia)", q, grupo))
        return sorted(novas, key=lambda m: m.quando)

    def ultimas_da_conversa(self, jid: str, quantas: int = 8) -> list[tuple[str, str]]:
        """[(quem, texto)] da conversa, mais antiga primeiro. quem = "você" ou o nome."""
        nome = self._nome(jid, (self._consultar(
            "SELECT name FROM chats WHERE jid = ?", (jid,)) or [(None,)])[0][0])
        linhas = self._consultar(
            "SELECT is_from_me, content FROM messages WHERE chat_jid = ? "
            "ORDER BY timestamp DESC LIMIT ?", (jid, quantas))
        return [("você" if eu else nome, texto or "(mídia)") for eu, texto in reversed(linhas)]

    def contatos(self) -> list[Contato]:
        linhas = self._consultar("SELECT jid, name FROM chats ORDER BY last_message_time DESC")
        return [Contato(jid, self._nome(jid, nome)) for jid, nome in linhas
                if jid.endswith("@s.whatsapp.net") or (self.avisar_grupos and jid.endswith("@g.us"))]

    def achar_contato(self, falado: str) -> list[Contato]:
        """Os contatos que casam com o nome falado, o melhor primeiro.
        Vários com nota parecida = ambíguo, o núcleo pergunta qual."""
        alvo = normalizar(falado)
        notas = []
        for c in self.contatos():
            n = nota(alvo, normalizar(c.nome))
            if n >= 0.75:
                notas.append((n, c))
        notas.sort(key=lambda p: -p[0])
        if not notas:
            return []
        melhor = notas[0][0]
        return [c for n, c in notas if n >= melhor - 0.05]

    def enviar(self, jid: str, texto: str) -> tuple[bool, str]:
        try:
            r = requests.post(self.api, json={"recipient": jid, "message": texto}, timeout=15)
            dados = r.json() if r.content else {}
        except (requests.RequestException, ValueError) as e:
            return False, f"a ponte do WhatsApp não respondeu ({e.__class__.__name__})"
        ok = bool(dados.get("success", r.ok))
        return ok, str(dados.get("message") or "")
