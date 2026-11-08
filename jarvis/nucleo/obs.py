"""O OBS por voz (08/11/2026): gravar, parar, pausar, continuar, mutar o
microfone e o som do PC, trocar de cena. Pelo controle remoto do próprio OBS
(obs-websocket, protocolo v5, só neste PC; a senha é a que o OBS guarda).

    python -m jarvis.nucleo.obs estado | gravar | parar | pausar | continuar
    python -m jarvis.nucleo.obs mutar|desmutar microfone|desktop
    python -m jarvis.nucleo.obs cena <nome>      |  cenas

A coleção de gravar é a "Sem nome" (microfone na faixa 1, som do PC na faixa
2). A "Compartilhar Tela" é só para transmitir pro Lucas pelo VDO.Ninja.
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

from websockets.sync.client import connect

CONFIG = Path.home() / ".var/app/com.obsproject.Studio/config/obs-studio/plugin_config/obs-websocket/config.json"
ENDERECO = "ws://127.0.0.1:{porta}"
COLECAO_DE_GRAVAR = "Sem nome"
ABRIR = ["flatpak", "run", "com.obsproject.Studio", "--collection", COLECAO_DE_GRAVAR,
         "--profile", "Sem nome", "--minimize-to-tray", "--disable-shutdown-check"]


@dataclass
class Resultado:
    ok: bool
    mensagem: str


class SemOBS(Exception):
    """O OBS não está aberto (ou o controle remoto dele está desligado)."""


def _senha_e_porta() -> tuple[str, int]:
    d = json.loads(CONFIG.read_text())
    return (d.get("server_password", "") if d.get("auth_required") else ""), int(d.get("server_port", 4455))


class Conexao:
    def __init__(self, timeout: float = 3) -> None:
        senha, porta = _senha_e_porta()
        try:
            self.ws = connect(ENDERECO.format(porta=porta), open_timeout=timeout, close_timeout=1).__enter__()
        except OSError as e:
            raise SemOBS(str(e)) from None
        ola = json.loads(self.ws.recv(timeout))
        identificar = {"rpcVersion": 1, "eventSubscriptions": 0}
        auth = ola["d"].get("authentication")
        if auth:
            segredo = base64.b64encode(hashlib.sha256((senha + auth["salt"]).encode()).digest()).decode()
            identificar["authentication"] = base64.b64encode(
                hashlib.sha256((segredo + auth["challenge"]).encode()).digest()).decode()
        self.ws.send(json.dumps({"op": 1, "d": identificar}))
        resposta = json.loads(self.ws.recv(timeout))
        if resposta.get("op") != 2:
            raise SemOBS("o OBS recusou a senha")

    def pedir(self, tipo: str, dados: dict | None = None) -> dict:
        rid = uuid.uuid4().hex
        self.ws.send(json.dumps({"op": 6, "d": {"requestType": tipo, "requestId": rid, "requestData": dados or {}}}))
        while True:
            m = json.loads(self.ws.recv(5))
            if m.get("op") == 7 and m["d"].get("requestId") == rid:
                st = m["d"]["requestStatus"]
                if not st.get("result"):
                    raise RuntimeError(st.get("comment") or f"código {st.get('code')}")
                return m["d"].get("responseData") or {}

    def fechar(self) -> None:
        self.ws.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fechar()


def aberto() -> bool:
    try:
        Conexao(timeout=1).fechar()
        return True
    except (SemOBS, OSError, TimeoutError):
        return False


def _abrir_e_conectar(espera: float = 25) -> Conexao:
    subprocess.Popen(ABRIR, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    fim = time.monotonic() + espera
    while time.monotonic() < fim:
        time.sleep(1)
        try:
            return Conexao(timeout=2)
        except (SemOBS, OSError, TimeoutError):
            continue
    raise SemOBS("abri o OBS mas ele não respondeu")


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn").strip()


# ---------- os comandos ----------

def estado() -> dict:
    """{"aberto", "gravando", "pausado", "cena"}; sem OBS: aberto False."""
    try:
        with Conexao(timeout=1) as c:
            r = c.pedir("GetRecordStatus")
            cena = c.pedir("GetCurrentProgramScene").get("currentProgramSceneName", "")
            return {"aberto": True, "gravando": bool(r.get("outputActive")),
                    "pausado": bool(r.get("outputPaused")), "cena": cena}
    except (SemOBS, OSError, TimeoutError, RuntimeError):
        return {"aberto": False, "gravando": False, "pausado": False, "cena": ""}


def gravar() -> Resultado:
    try:
        c = Conexao()
    except SemOBS:
        try:
            c = _abrir_e_conectar()
        except SemOBS:
            return Resultado(False, "Não consegui abrir o OBS.")
    with c:
        if c.pedir("GetRecordStatus").get("outputActive"):
            return Resultado(True, "Já está gravando.")
        c.pedir("StartRecord")
    return Resultado(True, "Gravando.")


def _com_obs(fazer) -> Resultado:
    try:
        with Conexao() as c:
            return fazer(c)
    except SemOBS:
        return Resultado(False, "O OBS não está aberto.")
    except RuntimeError as e:
        return Resultado(False, f"O OBS não deixou: {e}")


def parar() -> Resultado:
    def f(c):
        if not c.pedir("GetRecordStatus").get("outputActive"):
            return Resultado(True, "Não estava gravando.")
        c.pedir("StopRecord")
        return Resultado(True, "Gravação parada.")
    return _com_obs(f)


def pausar() -> Resultado:
    def f(c):
        r = c.pedir("GetRecordStatus")
        if not r.get("outputActive"):
            return Resultado(False, "Não está gravando.")
        if r.get("outputPaused"):
            return Resultado(True, "Já está pausada.")
        c.pedir("PauseRecord")
        return Resultado(True, "Gravação pausada.")
    return _com_obs(f)


def continuar() -> Resultado:
    def f(c):
        r = c.pedir("GetRecordStatus")
        if not r.get("outputActive"):
            return Resultado(False, "Não está gravando.")
        if not r.get("outputPaused"):
            return Resultado(True, "Já está gravando.")
        c.pedir("ResumeRecord")
        return Resultado(True, "Gravando de novo.")
    return _com_obs(f)


def mutar(qual: str, mudo: bool = True) -> Resultado:
    """qual: "microfone" ou "desktop" (o som do PC)."""
    def f(c):
        especiais = c.pedir("GetSpecialInputs")
        nome = especiais.get("mic1" if qual == "microfone" else "desktop1")
        if not nome:
            return Resultado(False, "Não achei essa fonte de áudio no OBS.")
        c.pedir("SetInputMute", {"inputName": nome, "inputMuted": mudo})
        rotulo = "Microfone" if qual == "microfone" else "Som do PC"
        return Resultado(True, f"{rotulo} {'mutado' if mudo else 'ligado'}.")
    return _com_obs(f)


def cenas() -> list[str]:
    try:
        with Conexao() as c:
            return [s["sceneName"] for s in c.pedir("GetSceneList").get("scenes", [])]
    except (SemOBS, RuntimeError):
        return []


def cena(falada: str) -> Resultado:
    def f(c):
        nomes = [s["sceneName"] for s in c.pedir("GetSceneList").get("scenes", [])]
        alvo = _sem_acento(falada)
        achou = next((n for n in nomes if _sem_acento(n) == alvo), None) \
            or next((n for n in nomes if alvo in _sem_acento(n) or _sem_acento(n) in alvo), None)
        if achou is None:
            return Resultado(False, "Não achei essa cena. As cenas são: " + ", ".join(nomes) + ".")
        c.pedir("SetCurrentProgramScene", {"sceneName": achou})
        return Resultado(True, f"Cena {achou}.")
    return _com_obs(f)


def main(a: list[str]) -> int:
    acoes = {"gravar": gravar, "parar": parar, "pausar": pausar, "continuar": continuar}
    if a[:1] == ["estado"] or not a:
        print(json.dumps(estado(), ensure_ascii=False))
    elif a[0] in acoes:
        print(acoes[a[0]]().mensagem)
    elif a[0] in ("mutar", "desmutar") and a[1:2] in (["microfone"], ["desktop"]):
        print(mutar(a[1], a[0] == "mutar").mensagem)
    elif a[0] == "cena" and len(a) > 1:
        print(cena(" ".join(a[1:])).mensagem)
    elif a[0] == "cenas":
        print("\n".join(cenas()))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
