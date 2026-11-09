"""Os áudios dos grupos viram texto (09/11/2026, pedido do Léo).

Com o NOSSO Whisper (o mesmo que ouve o Léo no microfone), nunca a
transcrição do próprio WhatsApp: "ela é uma merda" (Léo). O áudio é baixado
pela ponte (/api/download), transcrito e apagado na hora. O texto fica em
`transcricoes.json` na pasta do grupo (id da mensagem -> texto) e entra no
histórico e na conversa como "(áudio) ...". Assim quem chama "Jarvis, ..."
por áudio é atendido igual a quem escreve.

Áudio muito velho pode não baixar mais (o WhatsApp apaga a mídia dos
servidores dele depois de um tempo): fica marcado e não é tentado de novo.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np

from jarvis import memorias

ARQUIVO = "transcricoes.json"
DOS_BOTS = "audios_dos_bots.json"   # id -> "Jarvis"/"Friday": os áudios que eles mesmos mandaram
NAO_BAIXOU = ""          # marcado assim: não tenta de novo
TEXTO_NAO_BAIXOU = "(áudio que não deu pra baixar)"
MAX_S = 15 * 60          # áudio mais longo que isso: só os primeiros 15 minutos
DE_NOVO_S = 3600         # celular sem responder ou ponte fora: tenta de novo depois disto


def decodificar(caminho: str) -> np.ndarray:
    """Qualquer áudio do WhatsApp (ogg/opus) -> 16 kHz mono float32, como o Whisper quer."""
    saida = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-t", str(MAX_S), "-i", caminho,
         "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, timeout=120, check=True).stdout
    return np.frombuffer(saida, dtype=np.float32).copy()


class Audios:
    def __init__(self, whatsapp, transcrever: Callable[[np.ndarray], str]) -> None:
        self.whatsapp = whatsapp
        self._transcrever = transcrever
        self._trava = threading.Lock()  # o grupo e o puxador do histórico usam ao mesmo tempo
        self._adiados: dict[str, float] = {}  # id -> quando tentar de novo

    # -- o arquivo de cada grupo -------------------------------------------------

    def _caminho(self, jid: str) -> Path:
        return memorias.pasta_do_grupo(jid) / ARQUIVO

    def todas(self, jid: str) -> dict[str, str]:
        try:
            dados = json.loads(self._caminho(jid).read_text(encoding="utf-8"))
            return dados if isinstance(dados, dict) else {}
        except (OSError, ValueError):
            return {}

    def _guardar(self, jid: str, id_msg: str, texto: str) -> None:
        with self._trava:
            dados = self.todas(jid)
            dados[id_msg] = texto
            c = self._caminho(jid)
            c.parent.mkdir(parents=True, exist_ok=True)
            temp = c.with_suffix(".novo")
            temp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            temp.replace(c)

    def do_bot(self, jid: str) -> dict[str, str]:
        try:
            dados = json.loads((memorias.pasta_do_grupo(jid) / DOS_BOTS).read_text(encoding="utf-8"))
            return dados if isinstance(dados, dict) else {}
        except (OSError, ValueError):
            return {}

    def marcar_do_bot(self, jid: str, id_msg: str, nome: str, texto: str) -> None:
        """O áudio que o Jarvis/Friday mandou: já tem o texto (nunca é
        transcrito) e é dele (nunca é atendido como se fosse do Léo)."""
        self._guardar(jid, id_msg, texto)
        with self._trava:
            dados = self.do_bot(jid)
            dados[id_msg] = nome
            c = memorias.pasta_do_grupo(jid) / DOS_BOTS
            c.parent.mkdir(parents=True, exist_ok=True)
            c.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def como_texto(transcricao: str | None) -> str:
        """Como o áudio aparece no histórico e na conversa."""
        if transcricao is None:
            return "(áudio)"
        if transcricao == NAO_BAIXOU:
            return TEXTO_NAO_BAIXOU
        return f"(áudio) {transcricao}"

    # -- transcrever -------------------------------------------------------------

    def transcrever(self, jid: str, id_msg: str) -> str:
        """Baixa, transcreve, apaga o arquivo e guarda. Devolve o texto
        (ou NAO_BAIXOU). Já transcrito: devolve o guardado."""
        feito = self.todas(jid).get(id_msg)
        if feito is not None:
            return feito
        caminho = self.whatsapp.baixar(jid, id_msg)
        if not caminho:
            erro = getattr(self.whatsapp, "erro_do_download", "")
            if "não respondeu" in erro or "ponte fora" in erro:
                # O celular desligado ou a ponte fora não querem dizer que o áudio
                # sumiu: fica para depois, sem marcar.
                self._adiados[id_msg] = time.time() + DE_NOVO_S
                return NAO_BAIXOU
            self._guardar(jid, id_msg, NAO_BAIXOU)
            return NAO_BAIXOU
        try:
            texto = (self._transcrever(decodificar(caminho)) or "").strip() or "(sem fala)"
        except (subprocess.SubprocessError, OSError, ValueError):
            texto = NAO_BAIXOU
        finally:
            try:
                Path(caminho).unlink()
            except OSError:
                pass
        self._guardar(jid, id_msg, texto)
        return texto

    def pendentes(self, jid: str) -> list[str]:
        """Os áudios do grupo que ainda não viraram texto, o mais novo primeiro."""
        feitos = self.todas(jid)
        linhas = self.whatsapp._consultar(
            "SELECT id FROM messages WHERE chat_jid = ? AND media_type = 'audio' "
            "ORDER BY timestamp DESC", (jid,))
        agora = time.time()
        return [str(i) for (i,) in linhas
                if str(i) not in feitos and self._adiados.get(str(i), 0) <= agora]
