"""Liga e desliga a NOVA no Windows: o irmão do jarvis.sh (que segue sendo o do
Linux). É o que os atalhos do Menu Iniciar e da pasta Inicializar chamam:

    pythonw -m jarvis.ligar               liga o que falta e abre a janela
    pythonw -m jarvis.ligar --desligar    desliga tudo
    pythonw -m jarvis.ligar --na-bandeja  liga com a janela escondida (ao entrar no PC)

Cada parte que sobe anota o número dela (PID) em logs/<parte>.pid: "está ligada"
é o número existir e o programa dele ainda rodar. O que ela imprimiria num
terminal vai para logs/<parte>.log.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJETO = Path(__file__).resolve().parent.parent
LOGS = PROJETO / "logs"
WINDOWS = os.name == "nt"
PYTHON = PROJETO / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
PONTE = Path.home() / ".local/share/jarvis/whatsapp-mcp/whatsapp-bridge"
PONTE_EXE = PONTE / ("whatsapp-bridge.exe" if WINDOWS else "whatsapp-bridge")
# Sem uma janela preta de terminal por parte, e solta do atalho que a ligou.
SOLTO = ({"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS
         else {"start_new_session": True})
PARTES = ("janela", "assistente", "porta", "ponte", "rvc", "friday")


def _rodando(pid: int) -> bool:
    if WINDOWS:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        codigo = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(codigo))
        k.CloseHandle(h)
        return codigo.value == 259              # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _pid(parte: str) -> int | None:
    try:
        pid = int((LOGS / f"{parte}.pid").read_text())
    except (OSError, ValueError):
        return None
    return pid if _rodando(pid) else None


def _subir(parte: str, cmd: list, cwd: Path = PROJETO, caminho: Path | None = None) -> None:
    """Liga a parte se ela não estiver ligada. `caminho`: uma pasta a mais no PATH (o FFmpeg)."""
    if _pid(parte):
        return
    LOGS.mkdir(exist_ok=True)
    env = dict(os.environ)
    if caminho is not None:
        env["PATH"] = str(caminho) + os.pathsep + env.get("PATH", "")
    with open(LOGS / f"{parte}.log", "a", encoding="utf-8") as log:
        log.write(f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} ligando ===\n")
        log.flush()
        p = subprocess.Popen([str(c) for c in cmd], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                             stdout=log, stderr=subprocess.STDOUT, **SOLTO)
    (LOGS / f"{parte}.pid").write_text(str(p.pid))


def ligar(argumentos: list[str]) -> None:
    from jarvis import config, vozes
    cfg = config.carregar()
    v = vozes.achar(procurar=True)
    programas = vozes.programas()

    # A ponte do WhatsApp só sobe sozinha se já foi pareada (tem o banco): num PC
    # novo quem sobe é o Conectar de Ajustes → Conexões, para mostrar o QR.
    if PONTE_EXE.exists() and (PONTE / "store" / "whatsapp.db").exists():
        _subir("ponte", [PONTE_EXE], cwd=PONTE)
    # As vozes dubladas, se o instalador pôs os programas delas.
    if programas and cfg.tts.motor == "rvc" and v["jarvis"]:
        # De dentro da pasta do Applio: ele acha os modelos dele (rmvpe, contentvec) por ali.
        _subir("rvc", [programas["python"], "-u", PROJETO / "servidor_rvc.py",
                       "--modelo", v["jarvis"] / "rvc" / "jarvis-dublado.pth",
                       "--index", v["jarvis"] / "rvc" / "jarvis-dublado.index"],
               cwd=programas["applio"], caminho=programas["ffmpeg"])
    if programas and cfg.friday is not None and cfg.friday.ligada and v["friday"]:
        _subir("friday", [programas["python"], "-u", PROJETO / "servidor_friday.py", "--pasta", v["friday"],
                          "--modelo", "friday-emilia-v1", "--whisper", cfg.stt.modelo],
               caminho=programas["ffmpeg"])
    _subir("assistente", [PYTHON, "-u", PROJETO / "assistente.py"])
    _subir("porta", [PYTHON, "-u", PROJETO / "porta_remota.py"])
    # A janela sobe na hora e mostra "esperando o Jarvis subir" enquanto o assistente
    # carrega. Já aberta, ela mesma só vem para a frente (e o número anotado é o da primeira).
    if _pid("janela"):
        subprocess.Popen([str(PYTHON), str(PROJETO / "interface.py"), *argumentos], cwd=PROJETO,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **SOLTO)
    else:
        _subir("janela", [PYTHON, PROJETO / "interface.py", *argumentos])


def desligar() -> None:
    # No Linux o assistente trata o SIGTERM como ctrl+c (grava o resumo). No Windows o
    # mesmo pedido para o programa na hora.
    for parte in PARTES:
        pid = _pid(parte)
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        (LOGS / f"{parte}.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--desligar"]:
        desligar()
    else:
        ligar(sys.argv[1:])
