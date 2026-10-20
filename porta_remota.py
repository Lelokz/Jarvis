#!/usr/bin/env python3
"""A porta remota do Jarvis: o celular (o app, ou a página de teste) ↔ a ponte.

O cérebro, o Whisper e a voz continuam no PC. O celular é só mais um "corpo":
manda texto ou a fala gravada e recebe as respostas, com a voz do JARVIS,
pelo mesmo vocabulário da ponte (`jarvis/ponte/protocolo.py`), por WebSocket.

**Segurança, em duas camadas:**
- Escuta SÓ em 127.0.0.1. Quem leva a porta para o celular é o
  `tailscale serve` (HTTPS, e só para os aparelhos da conta do Léo); da
  internet aberta ninguém chega aqui.
- O aparelho apresenta a chave (`[remoto] chave`, criada aqui na primeira vez,
  0600) na primeira mensagem; chave errada, a conexão fecha.

Processo separado do assistente, como a janela: travar aqui (rede ruim,
celular que parou de ler) não leva junto quem ouve. Cai a porta, a voz no PC
segue igual.

    porta_remota.py              sobe a porta (o jarvis.sh faz isso)
    porta_remota.py --endereco   mostra o link, com a chave, para abrir no celular

Fluxo de uma conexão:
    celular -> {"chave": "...", "historico": 80}
    porta   -> (abre um cliente da ponte com "voz": true e repassa tudo)
    celular -> {"pedir": "falar", "texto": "..."}     texto
    celular -> <binário: a fala gravada, webm/ogg/wav/m4a>
               (a porta converte para PCM 16 kHz, deixa na pasta da ponte e
                pede "ouvir")
    porta   -> os eventos da ponte, um por mensagem de texto (os "voz" trazem
               o áudio da resposta em base64)
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import secrets
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from jarvis import config  # noqa: E402
from jarvis.ponte import protocolo  # noqa: E402

PAGINA = RAIZ / "jarvis" / "remoto" / "pagina.html"
# Fala gravada maior que isto não é uma frase: 8 MB de webm são vários minutos.
MAX_AUDIO_BYTES = 8 * 1024 * 1024
# Um minuto de PCM 16 kHz: o resto é cortado antes de ir para o Whisper.
MAX_PCM_BYTES = 16000 * 2 * 60
# Os eventos "voz" trazem uma frase inteira em base64 (centenas de KB).
LIMITE_LINHA_PONTE = 32 * 1024 * 1024
PEDIDOS_DO_CELULAR = {"falar", "memoria"}


def ler_chave(caminho: Path) -> str:
    """A chave do celular. Criada na primeira vez, só o usuário lê."""
    caminho = caminho.expanduser()
    if caminho.is_file():
        chave = caminho.read_text().strip()
        if chave:
            return chave
    caminho.parent.mkdir(parents=True, exist_ok=True)
    chave = secrets.token_urlsafe(24)
    fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(chave + "\n")
    return chave


def para_pcm16k(dados: bytes) -> bytes:
    """Qualquer áudio que o celular gravar (webm/opus do navegador, wav, m4a)
    → PCM int16 mono 16 kHz, o que o Whisper do assistente espera."""
    import av

    saida = bytearray()
    with av.open(io.BytesIO(dados)) as arquivo:
        conversor = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for quadro in arquivo.decode(audio=0):
            for q in conversor.resample(quadro):
                saida += q.to_ndarray().tobytes()
            if len(saida) >= MAX_PCM_BYTES:
                break
        for q in conversor.resample(None):
            saida += q.to_ndarray().tobytes()
    return bytes(saida[:MAX_PCM_BYTES])


def guardar_audio(pcm: bytes) -> Path:
    pasta = protocolo.pasta_audio()
    pasta.mkdir(mode=0o700, exist_ok=True)
    caminho = pasta / f"{uuid.uuid4().hex}.pcm"
    fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pcm)
    return caminho


def criar_app(cfg: config.Config):
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, PlainTextResponse
    from starlette.routing import Route, WebSocketRoute
    from starlette.websockets import WebSocket, WebSocketDisconnect

    chave = ler_chave(Path(cfg.remoto.chave))
    socket_ponte = protocolo.caminho_socket(cfg.ponte.socket)

    async def pagina(_):
        # Sem chave aqui de propósito: a página não tem nada; a chave vale no
        # WebSocket. Sem cache, para o celular pegar a versão nova.
        return HTMLResponse(PAGINA.read_text(encoding="utf-8"),
                            headers={"Cache-Control": "no-store"})

    async def saude(_):
        return PlainTextResponse("ok")

    async def conexao(ws: WebSocket) -> None:
        await ws.accept()
        try:
            primeira = json.loads(await asyncio.wait_for(ws.receive_text(), 15))
        except (asyncio.TimeoutError, ValueError, KeyError, WebSocketDisconnect, RuntimeError):
            await ws.close(code=4400)
            return
        if not isinstance(primeira, dict) or not secrets.compare_digest(
                str(primeira.get("chave", "")).encode(), chave.encode()):
            await ws.send_text(json.dumps({"ev": "erro", "motivo": "chave errada"}))
            await ws.close(code=4401)
            return
        try:
            leitor, escritor = await asyncio.open_unix_connection(
                str(socket_ponte), limit=LIMITE_LINHA_PONTE)
        except OSError:
            await ws.send_text(json.dumps({"ev": "erro", "motivo": "o Jarvis está desligado"},
                                          ensure_ascii=False))
            await ws.close(code=4503)
            return
        historico = primeira.get("historico", 80)
        if isinstance(historico, bool) or not isinstance(historico, int):
            historico = 80
        escritor.write(protocolo.codificar({
            "pedir": "ola", "quem": str(primeira.get("quem") or "celular")[:40],
            "historico": max(0, min(historico, protocolo.MAX_HISTORICO)), "voz": True}))
        await escritor.drain()

        async def da_ponte() -> None:
            while linha := await leitor.readline():
                await ws.send_text(linha.decode("utf-8").rstrip("\n"))
            await ws.send_text(json.dumps({"ev": "erro", "motivo": "o Jarvis desligou"},
                                          ensure_ascii=False))

        async def do_celular() -> None:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    return
                if msg.get("bytes") is not None:
                    dados = msg["bytes"]
                    if len(dados) > MAX_AUDIO_BYTES:
                        await ws.send_text(json.dumps({"ev": "erro", "motivo": "áudio grande demais"},
                                                      ensure_ascii=False))
                        continue
                    try:
                        pcm = await asyncio.to_thread(para_pcm16k, dados)
                    except Exception as e:  # formato que o PyAV não abre
                        await ws.send_text(json.dumps(
                            {"ev": "erro", "motivo": f"não consegui ler o áudio ({e.__class__.__name__})"},
                            ensure_ascii=False))
                        continue
                    caminho = guardar_audio(pcm)
                    escritor.write(protocolo.codificar({"pedir": "ouvir", "arquivo": str(caminho)}))
                elif msg.get("text") is not None:
                    try:
                        pedido = json.loads(msg["text"])
                    except ValueError:
                        continue
                    # Só o que um celular pode pedir; o "ola" quem faz é a porta.
                    if not isinstance(pedido, dict) or pedido.get("pedir") not in PEDIDOS_DO_CELULAR:
                        continue
                    escritor.write(protocolo.codificar(pedido))
                await escritor.drain()

        tarefas = [asyncio.create_task(da_ponte()), asyncio.create_task(do_celular())]
        try:
            await asyncio.wait(tarefas, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tarefas:
                t.cancel()
            await asyncio.gather(*tarefas, return_exceptions=True)
            escritor.close()
            try:
                await ws.close()
            except (RuntimeError, WebSocketDisconnect):
                pass  # já fechado pelo celular

    return Starlette(routes=[Route("/", pagina), Route("/saude", saude),
                             WebSocketRoute("/ws", conexao)])


def endereco_tailscale() -> str | None:
    """O nome do PC na rede do Tailscale (ex.: pc-do-leo.tail1234.ts.net)."""
    if not shutil.which("tailscale"):
        return None
    try:
        r = subprocess.run(["tailscale", "status", "--json"], capture_output=True,
                           text=True, timeout=5)
        nome = json.loads(r.stdout).get("Self", {}).get("DNSName", "").rstrip(".")
        return nome or None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--endereco", action="store_true",
                   help="mostra o link (com a chave) para abrir no celular")
    a = p.parse_args()
    cfg = config.carregar()
    if a.endereco:
        chave = ler_chave(Path(cfg.remoto.chave))
        # A chave vai depois do "#": o navegador não a manda em pedido nenhum.
        print(f"neste PC:  http://127.0.0.1:{cfg.remoto.porta}/#chave={chave}")
        nome = endereco_tailscale()
        if nome:
            print(f"celular:   https://{nome}/#chave={chave}")
        else:
            print("celular:   (falta o Tailscale: instalar, entrar na conta e rodar "
                  f"`tailscale serve --bg {cfg.remoto.porta}`)")
        return 0
    if not cfg.remoto.ligada:
        print("porta remota desligada no config.toml ([remoto] ligada = false)")
        return 0
    import uvicorn

    uvicorn.run(criar_app(cfg), host="127.0.0.1", port=cfg.remoto.porta,
                log_level="warning", ws_max_size=MAX_AUDIO_BYTES + 1024)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
