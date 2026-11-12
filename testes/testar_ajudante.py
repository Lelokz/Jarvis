"""Modo Ajudante (12/11/2026): o cursor da NOVA e as ferramentas tela_olhar/tela_fazer,
numa tela INVISÍVEL própria (Xvfb), isolada da sessão do Léo. Nada aparece na tela dele.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

ok = falhou = 0


def checa(nome, cond, detalhe=""):
    global ok, falhou
    if cond:
        ok += 1
        print(f"  PASSOU  {nome}", flush=True)
    else:
        falhou += 1
        print(f"  FALHOU  {nome}  {detalhe}", flush=True)


def main() -> int:
    if not shutil.which("Xvfb") or not shutil.which("xed"):
        print("sem Xvfb/xed: pulando"); return 0
    run = Path(tempfile.mkdtemp(prefix="nova-aj-"))
    casa = Path(tempfile.mkdtemp(prefix="nova-aj-casa-", dir=RAIZ / "rascunho" if (RAIZ / "rascunho").is_dir() else None))
    os.chmod(run, 0o700)
    for k in ("SESSION_MANAGER", "XAUTHORITY", "DESKTOP_AUTOSTART_ID", "DBUS_SESSION_BUS_ADDRESS"):
        os.environ.pop(k, None)
    os.environ.update(DISPLAY=":61", XDG_RUNTIME_DIR=str(run), HOME=str(casa), GIO_USE_VFS="local", LANG="pt_BR.UTF-8")
    procs = [subprocess.Popen(["Xvfb", ":61", "-screen", "0", "1920x1080x24", "-nolisten", "tcp"], stderr=subprocess.DEVNULL)]
    time.sleep(1.5)
    r = subprocess.run(["dbus-daemon", "--session", "--fork", "--print-address=1", "--print-pid=1"], capture_output=True, text=True)
    endereco, dbus_pid = r.stdout.split()[:2]
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = endereco
    procs.append(subprocess.Popen(["metacity", "--replace"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    time.sleep(1)
    procs.append(subprocess.Popen(["xed", "--standalone"], cwd=str(casa), stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL))
    time.sleep(3)
    try:
        from jarvis import ajudante
        from jarvis.agente import ferramentas, travas
        checa("o canal do cursor mora na pasta de canais", str(ajudante.SOCKET).startswith(str(run)))
        t0 = time.monotonic()
        ajudante.garantir()
        checa("o cursor sobe sozinho", ajudante.no_ar(), f"{time.monotonic() - t0:.1f}s")
        jpg, esc = ajudante.foto()
        checa("a foto tem 1280 de largura (escala 1,5 numa tela 1920)", jpg[:2] == b"\xff\xd8" and abs(esc - 1.5) < 1e-6)
        lista = ferramentas._ferramentas_da_tela(lambda: "#ff6fb5")
        olhar = next(t for t in lista if t.name == "tela_olhar")
        fazer = next(t for t in lista if t.name == "tela_fazer")
        r = asyncio.run(olhar.handler({}))
        checa("tela_olhar devolve a foto", r["content"][0]["type"] == "image")
        t0 = time.monotonic()
        r = asyncio.run(fazer.handler({"acoes": [{"clicar": [430, 270]}, {"digitar": "banana\nmaçã\n"},
                                                 {"tecla": "ctrl+s"}, {"esperar": 1.2},
                                                 {"digitar": "teste-ajudante.txt"}, {"tecla": "Return"}, {"esperar": 1}]}))
        texto = r["content"][0]["text"]
        if os.environ.get("FOTO_TESTE"):
            import base64
            Path(os.environ["FOTO_TESTE"]).write_bytes(base64.b64decode(r["content"][-1]["data"]))
        checa("tela_fazer faz várias ações numa olhada", texto.count("-> ok") == 7, texto[:300])
        checa("e devolve a foto do resultado", r["content"][-1]["type"] == "image")
        salvo = list(casa.rglob("teste-ajudante.txt"))
        checa("o arquivo foi salvo de verdade (com acento)", bool(salvo) and "maçã" in salvo[0].read_text(),
              str(salvo))
        r = asyncio.run(fazer.handler({"acoes": []}))
        checa("lista vazia é recusada", r.get("is_error") is True)
        checa("outra voz não pode mexer no PC com o cursor",
              travas.precisa_do_leo("mcp__jarvis__tela_fazer", {}, casa / "CLAUDE.md") == "mexer no PC com o cursor")
        checa("olhar a tela não precisa do Léo", travas.precisa_do_leo("mcp__jarvis__tela_olhar", {}, casa / "CLAUDE.md") is None)
        print(f"  (as 7 ações levaram {time.monotonic() - t0:.1f}s)")
    finally:
        # Só o cursor DESTA tela de teste (DISPLAY :61); o da NOVA de verdade fica.
        for pid in os.listdir("/proc"):
            try:
                cmd = Path(f"/proc/{pid}/cmdline").read_bytes()
                if b"jarvis.ajudante.cursor" in cmd and b"DISPLAY=:61\0" in Path(f"/proc/{pid}/environ").read_bytes():
                    os.kill(int(pid), 15)
            except (OSError, ValueError):
                pass
        for p in reversed(procs):
            p.terminate()
        try:
            os.kill(int(dbus_pid), 15)
        except Exception:
            pass
        shutil.rmtree(run, ignore_errors=True); shutil.rmtree(casa, ignore_errors=True)
    print(f"\n{ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
