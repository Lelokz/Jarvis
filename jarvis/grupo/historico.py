"""O histórico dos grupos (09/11/2026, pedido do Léo: o Jarvis tem que
conseguir ver todas as mensagens do grupo, desde que ele foi criado).

A ponte só tinha o que chegou desde que foi conectada (fim de julho/2026).
O WhatsApp deixa pedir ao celular as mensagens de antes da mais antiga que
temos, de 50 em 50 (/api/history da ponte). A resposta chega depois e vai
para o mesmo banco. Este puxador pede, espera, vê se a mais antiga mudou e
repete até o celular parar de mandar: aí aquele grupo "acabou".

Para o Jarvis e a Friday lerem, o histórico inteiro vira `historico.txt` na
pasta do grupo (uma linha por mensagem: data, quem, texto). O Claude procura
nesse arquivo sozinho, do jeito dele, sem ferramenta sob medida.

Limites: o celular tem que estar ligado; só vem o que ele ainda guarda;
foto, áudio e vídeo entram só como "(foto)", "(áudio)"...
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Callable

import requests

from jarvis import memorias

ARQUIVO = "historico.txt"
ESTADO = "historico-estado.json"
POR_PEDIDO = 50
ESPERA_S = 45          # quanto esperar a resposta do celular antes de ver se chegou
SEM_NOVIDADE = 4       # pedidos seguidos sem nada novo = acabou (ou o celular está fora)
REVER_S = 24 * 3600    # grupo que "acabou" é conferido de novo um dia depois
MIDIA = {"image": "(foto)", "video": "(vídeo)", "audio": "(áudio)", "document": "(arquivo)"}


def _estado(jid: str) -> dict:
    try:
        return json.loads((memorias.pasta_do_grupo(jid) / ESTADO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar(jid: str, estado: dict) -> None:
    pasta = memorias.pasta_do_grupo(jid)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / ESTADO).write_text(json.dumps(estado), encoding="utf-8")


class Puxador:
    """Um passo por vez (chamado de uma thread própria do grupo)."""

    def __init__(self, whatsapp, quem: Callable[[str, bool, str], str], prefixos: tuple[str, ...] = (),
                 audios=None) -> None:
        self.audios = audios  # jarvis/grupo/audios.py: o texto dos áudios (ou None)
        self.whatsapp = whatsapp
        self.quem = quem  # (remetente, é meu, texto) -> nome, o mesmo do grupo
        self.prefixos = prefixos  # "🤖 Jarvis:"...: o nome já vai na frente da linha
        self._escrito: dict[str, tuple[int, int]] = {}  # jid -> quantas mensagens o arquivo tinha

    def _mais_antiga(self, jid: str) -> tuple[str, bool, dt.datetime] | None:
        linhas = self.whatsapp._consultar(
            "SELECT id, is_from_me, timestamp FROM messages WHERE chat_jid = ? "
            "ORDER BY timestamp ASC LIMIT 1", (jid,))
        if not linhas:
            return None
        i, eu, t = linhas[0]
        return str(i), bool(eu), self.whatsapp._quando(t)

    def _pedir(self, jid: str, id_msg: str, eu: bool, quando: dt.datetime) -> bool:
        try:
            r = requests.post(self.whatsapp.api.rsplit("/", 1)[0] + "/history", timeout=15,
                              json={"chat": jid, "id": id_msg, "from_me": eu,
                                    "timestamp": int(quando.timestamp()), "count": POR_PEDIDO})
            return bool((r.json() if r.content else {}).get("success", r.ok))
        except (requests.RequestException, ValueError):
            return False

    def passo(self, jid: str, agora: float | None = None) -> str:
        """Pede o próximo pedaço de um grupo, se for a hora. Devolve o que fez
        ("pediu", "esperando", "acabou", "sem ponte", "vazio")."""
        agora = time.time() if agora is None else agora
        e = _estado(jid)
        if e.get("acabou") and agora - e.get("acabou_em", 0) < REVER_S:
            return "acabou"
        if agora - e.get("pedido_em", 0) < ESPERA_S:
            return "esperando"
        antiga = self._mais_antiga(jid)
        if not antiga:
            return "vazio"
        id_msg, eu, quando = antiga
        if e.get("pedido_id"):  # houve um pedido antes: chegou coisa mais velha?
            e["sem_novidade"] = e.get("sem_novidade", 0) + 1 if id_msg == e["pedido_id"] else 0
            if e["sem_novidade"] >= SEM_NOVIDADE:
                _guardar(jid, {"acabou": True, "acabou_em": agora, "desde": quando.isoformat()})
                return "acabou"
        if not self._pedir(jid, id_msg, eu, quando):
            return "sem ponte"  # não conta como tentativa: a ponte estava fora
        e.update(acabou=False, pedido_id=id_msg, pedido_em=agora, desde=quando.isoformat())
        _guardar(jid, e)
        return "pediu"

    def escrever(self, jid: str, nome_grupo: str) -> bool:
        """Reescreve o historico.txt quando o número de mensagens muda."""
        feitos = self.audios.todas(jid) if self.audios else {}
        dos_bots = self.audios.do_bot(jid) if self.audios else {}
        # Muda quando chega mensagem ou quando mais um áudio vira texto.
        total = (self.whatsapp._consultar("SELECT COUNT(*) FROM messages WHERE chat_jid = ?", (jid,))[0][0],
                 len(feitos))
        if self._escrito.get(jid) == total and (memorias.pasta_do_grupo(jid) / ARQUIVO).exists():
            return False
        linhas = self.whatsapp._consultar(
            "SELECT sender, is_from_me, content, timestamp, media_type, id FROM messages "
            "WHERE chat_jid = ? ORDER BY timestamp ASC", (jid,))
        nomes: dict[tuple[str, bool], str] = {}
        saida = [f"# Histórico do grupo \"{nome_grupo}\" (uma linha por mensagem, a mais antiga primeiro)", ""]
        for s, eu, c, t, midia, i in linhas:
            texto = (c or "").replace("\r", "").replace("\n", " / ").strip()
            chave = (s or "", bool(eu))
            if texto and eu:
                nome = self.quem(s or "", True, texto)  # "🤖 Jarvis:" vira Jarvis
                for pre in self.prefixos:
                    if texto.startswith(pre):
                        texto = texto[len(pre):].strip()
            else:
                if chave not in nomes:
                    nomes[chave] = self.quem(s or "", bool(eu), "")
                nome = nomes[chave]
            if midia == "audio" and self.audios:
                texto = self.audios.como_texto(feitos.get(str(i or "")))
                nome = dos_bots.get(str(i or ""), nome)  # o áudio que o Jarvis/Friday mandou
            elif midia:
                texto = f"{MIDIA.get(midia, '(mídia)')} {texto}".strip()
            quando = self.whatsapp._quando(t).strftime("%d/%m/%Y %H:%M")
            saida.append(f"[{quando}] {nome}: {texto}")
        pasta = memorias.pasta_do_grupo(jid)
        pasta.mkdir(parents=True, exist_ok=True)
        temp = pasta / (ARQUIVO + ".novo")
        temp.write_text("\n".join(saida) + "\n", encoding="utf-8")
        temp.replace(pasta / ARQUIVO)
        self._escrito[jid] = total
        return True
