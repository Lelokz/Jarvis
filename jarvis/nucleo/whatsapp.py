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
    # Últimos 4 dígitos do telefone: o que separa dois contatos com o MESMO
    # nome salvo ("Pedro Silva, final 4321, ou final 8765?").
    final: str = ""
    # Salvo na agenda do Léo. False = só o nome que a PRÓPRIA pessoa pôs no
    # perfil (alguém de um grupo): em 20/10/2026 o Jarvis mandou para uma
    # "Cris" assim, em vez do "Chris" (padrasto) salvo na agenda.
    salvo: bool = True


# Conversa com UMA pessoa. Lista do que é permitido, e não do que é proibido:
# a primeira versão só barrava grupo (@g.us), e canal (@newsletter) e status
# (@broadcast) eram anunciados como "alguém fora dos teus contatos", com
# "Quer responder?" — num canal em que ninguém além do dono escreve.
_INDIVIDUAL = ("@s.whatsapp.net", "@lid")


def _conversa_que_avisa(jid: str, grupos: bool) -> bool:
    return jid.endswith(_INDIVIDUAL) or (grupos and jid.endswith("@g.us"))


class WhatsApp:
    def __init__(self, banco: Path, api: str, avisar_grupos: bool = False) -> None:
        self.banco = Path(banco).expanduser()
        # O banco da própria biblioteca (whatsmeow): tem a agenda e o mapa
        # LID -> telefone. Ver `_nomes`.
        self.banco_whatsmeow = self.banco.parent / "whatsapp.db"
        self.api = api
        self.avisar_grupos = avisar_grupos
        self._cache_nomes: tuple[float, dict, dict, dict] | None = None
        self._salvos: set[str] = set()  # telefones e LIDs com nome NA AGENDA do Léo

    def disponivel(self) -> bool:
        return self.banco.is_file()

    def _consultar(self, sql: str, args: tuple = ()) -> list[tuple]:
        # Só leitura: a ponte é a dona do banco e escreve nele o tempo todo.
        # A ponte foi alterada para WAL (ler enquanto ela grava); o timeout
        # cobre o resto. Sem WAL, o banco travava durante a sincronização.
        con = sqlite3.connect(f"file:{self.banco}?mode=ro", uri=True, timeout=5)
        try:
            return con.execute(sql, args).fetchall()
        finally:
            con.close()

    # -- quem é quem -----------------------------------------------------------
    #
    # O WhatsApp passou a identificar as pessoas por "LID" (`123...@lid`), um
    # número interno, no lugar do telefone. A ponte guarda esse número como
    # nome da conversa, e no primeiro teste real o Jarvis anunciou "um monte
    # de número aleatório muito rápido" em vez do nome. O nome de verdade está
    # no banco do whatsmeow: LID -> telefone (whatsmeow_lid_map) e telefone ->
    # nome da agenda (whatsmeow_contacts).

    def _nomes(self) -> tuple[dict, dict, dict]:
        """(lid -> telefone, telefone -> nome, lid -> nome), relido a cada minuto."""
        import time
        if self._cache_nomes and time.monotonic() - self._cache_nomes[0] < 60:
            return self._cache_nomes[1:]
        lid_pn: dict[str, str] = {}
        pn_nome: dict[str, str] = {}
        lid_nome: dict[str, str] = {}
        salvos: set[str] = set()
        try:
            con = sqlite3.connect(f"file:{self.banco_whatsmeow}?mode=ro", uri=True, timeout=5)
            try:
                lid_pn = dict(con.execute("SELECT lid, pn FROM whatsmeow_lid_map"))
                for jid, full, first, push, negocio in con.execute(
                        "SELECT their_jid, full_name, first_name, push_name, business_name "
                        "FROM whatsmeow_contacts"):
                    nome = (full or first or push or negocio or "").strip()
                    if not nome:
                        continue
                    usuario, _, servidor = jid.partition("@")
                    if (full or first or "").strip():
                        salvos.add(usuario)
                    (lid_nome if servidor == "lid" else pn_nome)[usuario] = nome
            finally:
                con.close()
        except sqlite3.Error:
            pass
        self._cache_nomes = (time.monotonic(), lid_pn, pn_nome, lid_nome)
        self._salvos = salvos
        return lid_pn, pn_nome, lid_nome

    def nome_de(self, jid: str, nome_do_chat: str | None = None) -> str:
        lid_pn, pn_nome, lid_nome = self._nomes()
        usuario, _, servidor = jid.partition("@")
        if servidor == "lid":
            nome = pn_nome.get(lid_pn.get(usuario, "")) or lid_nome.get(usuario)
        else:
            nome = pn_nome.get(usuario)
        if nome:
            return nome
        chat = (nome_do_chat or "").strip()
        if chat and not chat.split("@")[0].replace("+", "").isdigit():
            return chat
        # Nunca ler número em voz alta: além de inútil, é dado de terceiro.
        return "alguém fora dos teus contatos"

    def _jids_da_pessoa(self, jid: str) -> list[str]:
        """O mesmo contato pode ter conversa guardada como telefone ou como LID."""
        lid_pn, _, _ = self._nomes()
        usuario, _, servidor = jid.partition("@")
        if servidor == "lid":
            pn = lid_pn.get(usuario)
            return [jid] + ([f"{pn}@s.whatsapp.net"] if pn else [])
        lids = [l for l, p in lid_pn.items() if p == usuario]
        return [jid] + [f"{l}@lid" for l in lids]

    def pessoa(self, jid: str) -> str:
        """Uma chave por PESSOA (o telefone), seja a conversa @lid ou @s.whatsapp.net."""
        lid_pn, _, _ = self._nomes()
        usuario, _, servidor = jid.partition("@")
        return lid_pn.get(usuario, usuario) if servidor == "lid" else usuario

    def eu_mandei_desde(self, jid: str, desde: dt.datetime) -> list[tuple[dt.datetime, str]]:
        """Mensagens MINHAS nessa conversa depois de `desde`: (quando, texto).
        A ponte não guarda o que o Jarvis manda, então o que aparece aqui veio
        do celular (ou de outro aparelho do Léo)."""
        jids = self._jids_da_pessoa(jid)
        marcas = ",".join("?" * len(jids))
        linhas = self._consultar(
            f"SELECT timestamp, content FROM messages WHERE is_from_me = 1 "
            f"AND chat_jid IN ({marcas}) ORDER BY timestamp DESC LIMIT 20", tuple(jids))
        return [(q, t or "") for q, t in ((self._quando(a), b) for a, b in linhas) if q > desde]

    def _nome(self, jid: str, nome: str | None) -> str:
        return self.nome_de(jid, nome)

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
            if not _conversa_que_avisa(jid, self.avisar_grupos):
                continue
            grupo = jid.endswith("@g.us")
            novas.append(Mensagem(jid, self._nome(jid, nome), texto or "(mídia)", q, grupo))
        return sorted(novas, key=lambda m: m.quando)

    def ultimas_da_conversa(self, jid: str, quantas: int = 8) -> list[tuple[str, str]]:
        """[(quem, texto)] da conversa, mais antiga primeiro. quem = "você" ou o nome."""
        nome = self.nome_de(jid)
        jids = self._jids_da_pessoa(jid)
        marcas = ",".join("?" * len(jids))
        linhas = self._consultar(
            f"SELECT is_from_me, content FROM messages WHERE chat_jid IN ({marcas}) "
            "ORDER BY timestamp DESC LIMIT ?", (*jids, quantas))
        return [("você" if eu else nome, texto or "(mídia)") for eu, texto in reversed(linhas)]

    def contatos(self) -> list[Contato]:
        """A agenda (nome salvo no celular), mais as conversas com nome conhecido.

        Uma pessoa = um TELEFONE, não um nome. A primeira versão juntava por
        nome, e dois contatos salvos com o mesmo nome viravam um só — a
        mensagem ia para um deles sem perguntar (achado pela pergunta do Léo).
        """
        lid_pn, pn_nome, _ = self._nomes()
        vistos: set[str] = set()   # telefones (ou jid, sem telefone conhecido)
        lista: list[Contato] = []

        def chave(jid: str) -> str:
            usuario, _, servidor = jid.partition("@")
            return lid_pn.get(usuario, usuario) if servidor == "lid" else usuario

        def salvo(jid: str) -> bool:
            usuario = jid.partition("@")[0]
            return usuario in self._salvos or chave(jid) in self._salvos

        for jid, nome in self._consultar(
                "SELECT jid, name FROM chats ORDER BY last_message_time DESC"):
            if not _conversa_que_avisa(jid, self.avisar_grupos):
                continue
            n = self.nome_de(jid, nome)
            k = chave(jid)
            if n != "alguém fora dos teus contatos" and k not in vistos:
                vistos.add(k)
                lista.append(Contato(jid, n, k[-4:] if k.isdigit() else "", salvo(jid)))
        for pn, n in pn_nome.items():
            if pn not in vistos:
                vistos.add(pn)
                lista.append(Contato(f"{pn}@s.whatsapp.net", n, pn[-4:], pn in self._salvos))
        return lista

    def meu_jid(self) -> str:
        """O número do próprio Léo (o chat com ele mesmo): avisos do Jarvis
        que precisam chegar na hora no celular, como o pedido de desbloqueio."""
        try:
            con = sqlite3.connect(f"file:{self.banco_whatsmeow}?mode=ro", uri=True, timeout=5)
            try:
                linha = con.execute("select jid from whatsmeow_device").fetchone()
            finally:
                con.close()
        except sqlite3.Error:
            return ""
        if not linha:
            return ""
        return linha[0].split("@")[0].split(":")[0] + "@s.whatsapp.net"

    def esta_salvo(self, jid: str) -> bool:
        """O número está na agenda do Léo (e não só no perfil de alguém)?"""
        lid_pn, _, _ = self._nomes()
        usuario, _, servidor = jid.partition("@")
        return usuario in self._salvos or (servidor == "lid" and lid_pn.get(usuario, "") in self._salvos)

    def achar_contato(self, falado: str) -> list[Contato]:
        """Os contatos que casam com o nome falado, o melhor primeiro.
        Vários com nota parecida = ambíguo, o núcleo pergunta qual."""
        alvo = normalizar(falado)
        notas = []
        for c in self.contatos():
            n = nota(alvo, normalizar(c.nome))
            if n >= 0.75:
                notas.append((n, c))
        if not notas:
            return []
        # Quem está salvo na agenda vem antes de quem só tem nome de perfil,
        # mesmo com nota menor: "Cris" falado tem que achar o "Chris" salvo, e
        # não uma "Cris" de grupo (20/10/2026). Os não salvos só voltam se
        # nenhum salvo casou.
        salvos = [(n, c) for n, c in notas if c.salvo]
        notas = sorted(salvos or notas, key=lambda p: -p[0])
        melhor = notas[0][0]
        return [c for n, c in notas if n >= melhor - 0.05]

    def enviar(self, jid: str, texto: str, arquivo: str | None = None) -> tuple[bool, str]:
        """`arquivo`: caminho absoluto de um arquivo para mandar junto (o texto
        vira a legenda). A ponte lê o arquivo do disco (`media_path`)."""
        corpo = {"recipient": jid, "message": texto}
        if arquivo:
            corpo["media_path"] = arquivo
        try:
            r = requests.post(self.api, json=corpo, timeout=60 if arquivo else 15)
            dados = r.json() if r.content else {}
        except (requests.RequestException, ValueError) as e:
            return False, f"a ponte do WhatsApp não respondeu ({e.__class__.__name__})"
        ok = bool(dados.get("success", r.ok))
        return ok, str(dados.get("message") or "")
