"""A porta remota (o celular), de ponta a ponta — sem assistente, sem GPU.

Uma ponte de verdade num socket temporário, a porta remota de verdade numa
porta livre de 127.0.0.1, e um cliente WebSocket fazendo o papel do celular:
chave errada, texto, fala gravada, a voz indo SÓ para o aparelho que pediu, e
o que um celular não pode pedir.

Roda dentro do contido.sh (sobe threads de rede). O que é temporário mora num
diretório dentro do $XDG_RUNTIME_DIR, apagado no fim.
"""
from __future__ import annotations

import dataclasses
import io
import json
import math
import shutil
import socket
import struct
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import uvicorn  # noqa: E402
from websockets.sync.client import connect  # noqa: E402

import porta_remota  # noqa: E402
from jarvis import config  # noqa: E402
from jarvis.ponte import protocolo  # noqa: E402
from jarvis.ponte.servidor import Servidor  # noqa: E402

ok = falhou = 0


def checa(nome, cond, detalhe=""):
    global ok, falhou
    if cond:
        ok += 1
        print(f"  PASSOU  {nome}", flush=True)
    else:
        falhou += 1
        print(f"  FALHOU  {nome}  {detalhe}", flush=True)


def esperar_pedido(srv, timeout=5.0):
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        p = srv.proximo_pedido()
        if p is not None:
            return p
        time.sleep(0.01)
    return None


def receber_ate(ws, tipo, timeout=3.0):
    """Lê eventos até achar um do tipo pedido (ou None no prazo)."""
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        try:
            ev = json.loads(ws.recv(timeout=max(0.05, fim - time.monotonic())))
        except TimeoutError:
            return None
        if ev.get("ev") == tipo:
            return ev
    return None


def wav_de_teste(segundos=1.0, taxa=24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / taxa)))
                               for i in range(int(segundos * taxa))))
    return buf.getvalue()


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="jarvis-teste-remoto-", dir=protocolo.pasta_audio().parent))
    try:
        cfg = config.carregar()
        cfg = dataclasses.replace(
            cfg,
            ponte=dataclasses.replace(cfg.ponte, socket=str(base / "ponte.sock")),
            remoto=dataclasses.replace(cfg.remoto, porta=porta_livre(), chave=str(base / "chave")),
        )
        srv = Servidor(base / "ponte.sock", fila_max=64, sessao={"v": protocolo.VERSAO, "nome": "Jarvis",
                                                                  "log": "/x.jsonl"})
        srv.iniciar()
        app = porta_remota.criar_app(cfg)
        chave = (base / "chave").read_text().strip()
        checa("a chave nasce só para o usuário (0600)", (base / "chave").stat().st_mode & 0o777 == 0o600)
        servidor_web = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=cfg.remoto.porta,
                                                     log_level="error"))
        threading.Thread(target=servidor_web.run, daemon=True).start()
        fim = time.monotonic() + 10
        while not servidor_web.started and time.monotonic() < fim:
            time.sleep(0.05)
        url = f"ws://127.0.0.1:{cfg.remoto.porta}/ws"

        # 1. Chave errada: erro e fecha, sem chegar na ponte.
        with connect(url) as ws:
            ws.send(json.dumps({"chave": "errada"}))
            ev = receber_ate(ws, "erro")
            checa("chave errada é recusada", ev is not None and ev.get("motivo") == "chave errada")
        time.sleep(0.2)
        checa("e nem chega a abrir cliente na ponte", srv.n_clientes == 0, f"{srv.n_clientes}")

        # 2. Chave certa: a sessão chega com o id, e a ponte o vê como corpo.
        celular = connect(url)
        celular.send(json.dumps({"chave": chave, "historico": 10}))
        sessao = receber_ate(celular, "sessao")
        checa("chave certa: chega a sessão, com id", sessao is not None and isinstance(sessao.get("id"), int))
        meu_id = sessao["id"] if sessao else -1

        # 3. Texto do celular vira pedido com voz própria.
        celular.send(json.dumps({"pedir": "falar", "texto": "que horas são"}))
        p = esperar_pedido(srv)
        checa("o texto chega na ponte como pedido do celular",
              p is not None and p.tipo == "falar" and p.valor == "que horas são"
              and p.cliente == meu_id and p.voz, repr(p))

        # 4. A voz vai só para quem pediu: um segundo cliente (a janela) não recebe.
        janela = socket.socket(socket.AF_UNIX)
        janela.connect(str(base / "ponte.sock"))
        janela.sendall(protocolo.codificar({"pedir": "ola", "quem": "interface"}))
        janela.settimeout(2)
        time.sleep(0.2)
        srv.receber({"ev": "voz", "para": meu_id, "taxa": 24000, "pcm": "AAAA"})
        srv.receber({"ev": "jarvis_disse", "texto": "São três.", "acao": None, "perguntando": False})
        ev = receber_ate(celular, "voz")
        checa("a voz chega no celular", ev is not None and ev.get("pcm") == "AAAA")
        recebido = b""
        try:
            while b"jarvis_disse" not in recebido:
                recebido += janela.recv(65536)
        except OSError:
            pass
        checa("a janela recebe o texto mas não a voz",
              b"jarvis_disse" in recebido and b'"voz"' not in recebido, recebido[-200:])
        janela.close()

        # 5. Fala gravada: vira PCM 16 kHz na pasta da ponte, e pedido "ouvir".
        celular.send(wav_de_teste(1.0))
        p = esperar_pedido(srv)
        tamanho = Path(p.valor).stat().st_size if p and Path(p.valor).exists() else 0
        checa("a fala gravada vira pedido 'ouvir' com o arquivo na pasta da ponte",
              p is not None and p.tipo == "ouvir" and Path(p.valor).parent == protocolo.pasta_audio()
              and p.voz, repr(p))
        checa("convertida para 1 s de PCM 16 kHz (32.000 bytes, ±5%)",
              abs(tamanho - 32000) < 1600, f"{tamanho} bytes")
        if p and p.tipo == "ouvir":
            Path(p.valor).unlink(missing_ok=True)

        # 6. Áudio que não é áudio: erro, sem pedido.
        celular.send(b"isto nao e audio" * 100)
        ev = receber_ate(celular, "erro")
        checa("lixo binário volta como erro", ev is not None and "áudio" in ev.get("motivo", ""))
        checa("e não vira pedido", esperar_pedido(srv, 0.5) is None)

        # 7. O que um celular não pode pedir não passa.
        celular.send(json.dumps({"pedir": "ola", "voz": False}))
        celular.send(json.dumps({"pedir": "ouvir", "arquivo": "/etc/passwd"}))
        checa("'ola' e 'ouvir' direto do celular são ignorados", esperar_pedido(srv, 0.5) is None)

        # 8. A ponte recusa 'ouvir' de fora da pasta mesmo vindo de outro cliente.
        try:
            protocolo.ler_pedido(json.dumps({"pedir": "ouvir", "arquivo": "/etc/passwd"}).encode())
            recusou = False
        except protocolo.ErroDeProtocolo:
            recusou = True
        checa("a ponte recusa 'ouvir' fora da pasta de áudio", recusou)

        celular.close()
        servidor_web.should_exit = True
        srv.encerrar()
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print(f"\n  {ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
