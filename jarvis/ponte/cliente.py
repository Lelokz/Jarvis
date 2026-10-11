"""O cliente da ponte: o lado de quem mostra.

É o que a interface vai usar na passada 3. Enquanto a interface não existe, é
também o jeito de testar a ponte à mão, com o assistente ligado em outro
terminal:

    .venv/bin/python -m jarvis.ponte.cliente           # mostra os eventos
    .venv/bin/python -m jarvis.ponte.cliente --nivel   # e o nível do microfone

Digite uma linha e Enter: vira um pedido de fala. Se o assistente cair, este
cliente fica tentando reconectar a cada segundo — é o comportamento que a
interface precisa ter.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from . import protocolo


class Cliente:
    def __init__(self, caminho: Path, quem: str = "cliente") -> None:
        self.caminho = Path(caminho)
        self.quem = quem
        self._sock: socket.socket | None = None
        self._buffer = bytearray()

    def conectar(self, timeout: float = 2.0, historico: int = 0) -> None:
        """Conecta e se apresenta.

        O pedido de histórico vai JUNTO do `ola`, e não numa segunda ida: entre
        uma e outra, um evento ao vivo podia chegar e aparecer duas vezes.
        """
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(str(self.caminho))
        sock.settimeout(None)
        self._sock = sock
        self._buffer = bytearray()
        self._enviar({"pedir": "ola", "quem": self.quem, "historico": historico})

    def enviar_texto(self, texto: str) -> None:
        self._enviar({"pedir": "falar", "texto": texto})

    def eventos(self) -> Iterator[dict[str, Any]]:
        """Bloqueia lendo. Termina quando o assistente fecha a conexão."""
        while True:
            fim = self._buffer.find(b"\n")
            if fim >= 0:
                linha = bytes(self._buffer[:fim])
                del self._buffer[: fim + 1]
                if linha.strip():
                    yield json.loads(linha)
                continue
            dados = self._sock.recv(65536)
            if not dados:
                return
            self._buffer += dados

    def fechar(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _enviar(self, objeto: dict[str, Any]) -> None:
        self._sock.sendall(protocolo.codificar(objeto))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cliente de teste da ponte do Jarvis.")
    p.add_argument("--socket", default="", help="padrão: $XDG_RUNTIME_DIR/jarvis.sock")
    p.add_argument("--nivel", action="store_true", help="mostra também o nível do microfone")
    p.add_argument("--historico", type=int, default=20,
                   help="quantas falas anteriores pedir ao conectar (0 = nenhuma)")
    args = p.parse_args(argv)
    caminho = protocolo.caminho_socket(args.socket)

    atual: dict[str, Cliente | None] = {"cliente": None}

    def ler_teclado() -> None:
        for linha in sys.stdin:
            texto = linha.strip()
            cliente = atual["cliente"]
            if not texto:
                continue
            if cliente is None:
                print("  (desconectado — não enviado)", flush=True)
                continue
            try:
                cliente.enviar_texto(texto)
            except OSError:
                print("  (a conexão caiu — não enviado)", flush=True)

    threading.Thread(target=ler_teclado, name="teclado", daemon=True).start()

    avisado = False
    try:
        while True:
            cliente = Cliente(caminho, quem="terminal")
            try:
                cliente.conectar(historico=args.historico)
            except OSError:
                if not avisado:
                    print(f"  desconectado — esperando o Jarvis em {caminho}", flush=True)
                    avisado = True
                time.sleep(1.0)
                continue
            avisado = False
            atual["cliente"] = cliente
            print("  conectado", flush=True)
            try:
                for evento in cliente.eventos():
                    if evento.get("ev") == "nivel" and not args.nivel:
                        continue
                    if evento.get("ev") == "historico":
                        falas = evento.get("falas") or []
                        print(f"  --- {len(falas)} falas de antes ---", flush=True)
                        for fala in falas:
                            quem = "você " if fala.get("quem") == "voce" else "jarvis"
                            print(f"    {quem}: {fala.get('texto', '')}", flush=True)
                        print("  --- fim do histórico ---", flush=True)
                        continue
                    print("  " + json.dumps(evento, ensure_ascii=False), flush=True)
            except OSError:
                pass
            atual["cliente"] = None
            cliente.fechar()
            print("  a conexão caiu", flush=True)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
