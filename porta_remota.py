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
import time
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from jarvis import config  # noqa: E402
from jarvis.ponte import protocolo, recebidos  # noqa: E402

PAGINA = RAIZ / "jarvis" / "remoto" / "pagina.html"
# O app do celular (celular/compilar.sh): baixado pelo Chrome do celular em
# /jarvis.apk. Sem chave: o APK não leva segredo nenhum (a chave se cola nele).
APK = RAIZ / "celular" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
# Fala gravada maior que isto não é uma frase: 8 MB de webm são vários minutos.
MAX_AUDIO_BYTES = 8 * 1024 * 1024
# Um minuto de PCM 16 kHz: o resto é cortado antes de ir para o Whisper.
MAX_PCM_BYTES = 16000 * 2 * 60
# Os eventos "voz" trazem uma frase inteira em base64 (centenas de KB).
LIMITE_LINHA_PONTE = 32 * 1024 * 1024
# Os da janela nova (beta 0.6) também: conversas, cérebro, Parar.
PEDIDOS_DO_CELULAR = {"falar", "memoria", "conversas", "abrir", "nova", "continuar", "cerebro",
                      "parar", "renomear", "apagar"}
# Foto, vídeo ou arquivo mandado pelo clipe do app. Vídeo de celular passa
# disso fácil; por enquanto é o teto (o WebSocket guarda tudo na memória).
MAX_ANEXO_BYTES = 64 * 1024 * 1024



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
    from starlette.responses import FileResponse, HTMLResponse, PlainTextResponse
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

    async def apk(_):
        if not APK.is_file():
            return PlainTextResponse("o app ainda não foi compilado (celular/compilar.sh)", status_code=404)
        return FileResponse(APK, media_type="application/vnd.android.package-archive",
                            filename="jarvis.apk", headers={"Cache-Control": "no-store"})

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
            "historico": max(0, min(historico, protocolo.MAX_HISTORICO)), "voz": True,
            # O app do celular mostra a janela nova; o relógio não.
            "janela": primeira.get("janela") is True}))
        await escritor.drain()

        quem = str(primeira.get("quem") or "celular")[:40]
        # Medição da demora (o Léo: no celular 3-4 s, no PC 1-3 s): do pedido
        # chegar aqui até o texto e a 1ª voz da resposta saírem para ele.
        relogio: dict = {}
        print(f"{time.strftime('%H:%M:%S')} conectou: {quem}", flush=True)

        async def da_ponte() -> None:
            while linha := await leitor.readline():
                if relogio.get("pedido") and linha.startswith((b'{"ev":"jarvis_disse"', b'{"ev":"voz"')):
                    marca = "texto" if linha.startswith(b'{"ev":"jarvis_disse"') else "voz"
                    if marca not in relogio:
                        relogio[marca] = time.monotonic() - relogio["pedido"]
                    if "texto" in relogio and "voz" in relogio:
                        print(f"{time.strftime('%H:%M:%S')} demora ({relogio['tipo']}): "
                              f"texto em {relogio['texto']:.2f}s, 1ª voz em {relogio['voz']:.2f}s",
                              flush=True)
                        relogio.clear()
                if linha.startswith(b'{"ev":"voz"'):
                    print(f"{time.strftime('%H:%M:%S')} voz -> {quem}: {len(linha) // 1024} KB",
                          flush=True)
                await ws.send_text(linha.decode("utf-8").rstrip("\n"))
            await ws.send_text(json.dumps({"ev": "erro", "motivo": "o Jarvis desligou"},
                                          ensure_ascii=False))

        # O clipe do app: {"pedir":"anexo","nome":...} e, logo depois, o
        # arquivo em binário. Fica guardado até o próximo pedido (texto ou
        # fala), que leva os anexos junto.
        anexo_chegando: dict | None = None
        mudo = False  # o botão de mudo do app: vai em todo pedido
        pendentes: dict[int, Path] = {}
        proximo_id = 1

        def com_anexos(pedido: dict) -> dict:
            if mudo:
                pedido["mudo"] = True
            if pendentes:
                pedido["anexos"] = [str(p) for p in pendentes.values()][:protocolo.MAX_ANEXOS]
                pendentes.clear()
            return pedido

        async def do_celular() -> None:
            nonlocal anexo_chegando, proximo_id, mudo
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    return
                if msg.get("bytes") is not None and anexo_chegando is not None:
                    dados, nome = msg["bytes"], anexo_chegando["nome"]
                    anexo_chegando = None
                    if len(dados) > MAX_ANEXO_BYTES:
                        await ws.send_text(json.dumps(
                            {"ev": "anexo_erro", "nome": nome,
                             "motivo": f"maior que {MAX_ANEXO_BYTES // 1024 // 1024} MB"},
                            ensure_ascii=False))
                        continue
                    caminho = await asyncio.to_thread(recebidos.guardar, nome, dados)
                    pendentes[proximo_id] = caminho
                    await ws.send_text(json.dumps({"ev": "anexo_ok", "id": proximo_id, "nome": nome},
                                                  ensure_ascii=False))
                    print(f"{time.strftime('%H:%M:%S')} anexo de {quem}: {caminho.name} "
                          f"({len(dados) // 1024} KB)", flush=True)
                    proximo_id += 1
                    continue
                if msg.get("bytes") is not None:
                    relogio.clear()
                    relogio.update(pedido=time.monotonic(), tipo="fala")
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
                    escritor.write(protocolo.codificar(
                        com_anexos({"pedir": "ouvir", "arquivo": str(caminho)})))
                elif msg.get("text") is not None:
                    try:
                        pedido = json.loads(msg["text"])
                    except ValueError:
                        continue
                    # O relatório da página (o que chegou e tocou): só para o log.
                    if isinstance(pedido, dict) and isinstance(pedido.get("diag"), dict):
                        print(f"{time.strftime('%H:%M:%S')} diag {quem}: "
                              f"{json.dumps(pedido['diag'], ensure_ascii=False)[:300]}", flush=True)
                        continue
                    if isinstance(pedido, dict) and pedido.get("pedir") == "anexo":
                        anexo_chegando = {"nome": str(pedido.get("nome") or "anexo")}
                        continue
                    if isinstance(pedido, dict) and pedido.get("pedir") == "mudo":
                        mudo = pedido.get("mudo") is True
                        continue
                    if isinstance(pedido, dict) and pedido.get("pedir") == "anexo_cancelar":
                        caminho = pendentes.pop(pedido.get("id"), None)
                        if caminho is not None:
                            caminho.unlink(missing_ok=True)
                        continue
                    # Só o que um celular pode pedir; o "ola" quem faz é a porta.
                    if not isinstance(pedido, dict) or pedido.get("pedir") not in PEDIDOS_DO_CELULAR:
                        continue
                    if pedido.get("pedir") == "falar":
                        relogio.clear()
                        relogio.update(pedido=time.monotonic(), tipo="texto")
                        # Os anexos quem põe é a porta (o celular não sabe os caminhos).
                        pedido = com_anexos({"pedir": "falar", "texto": pedido.get("texto")})
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

    return Starlette(routes=[Route("/", pagina), Route("/saude", saude), Route("/jarvis.apk", apk),
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

    apagados = recebidos.limpar()
    if apagados:
        print(f"{time.strftime('%H:%M:%S')} recebidos: {apagados} com mais de "
              f"{recebidos.DIAS} dias apagados", flush=True)
    uvicorn.run(criar_app(cfg), host="127.0.0.1", port=cfg.remoto.porta,
                log_level="warning", ws_max_size=MAX_ANEXO_BYTES + 1024)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
