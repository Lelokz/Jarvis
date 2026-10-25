"""O pedido ao dono pelo WhatsApp quando o app não funciona (25/10/2026).

Sem WhatsApp nem Claude de verdade: um WhatsApp falso anota o que foi
mandado e devolve as respostas do roteiro; as aprovações vão para um arquivo
temporário.
"""
from __future__ import annotations

import datetime as dt
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from jarvis.grupo import familia  # noqa: E402
from jarvis.nucleo import aprovacoes  # noqa: E402

ok = falhou = 0


def checa(nome, cond, detalhe=""):
    global ok, falhou
    if cond:
        ok += 1
        print(f"  PASSOU  {nome}", flush=True)
    else:
        falhou += 1
        print(f"  FALHOU  {nome}  {detalhe}", flush=True)


class WhatsAppFalso:
    def __init__(self):
        self.mandadas: list[tuple[str, str]] = []
        self.respostas: list[tuple[dt.datetime, str]] = []  # o que "ele" escreveu

    def meu_jid(self):
        return "5500000000000@s.whatsapp.net"

    def enviar(self, jid, texto, arquivo=None):
        self.mandadas.append((jid, texto))
        return True, ""

    def eu_mandei_desde(self, jid, desde):
        return [(q, t) for q, t in reversed(self.respostas) if q > desde]


def novo_pedido(quem, pedido, ha_s):
    a = aprovacoes.criar(quem, pedido)
    lista = aprovacoes._ler()
    for x in lista:
        if x["id"] == a["id"]:
            x["criado"] -= ha_s
    aprovacoes._gravar(lista)
    return a


def main() -> int:
    aprovacoes.ARQUIVO = Path(tempfile.mkdtemp(prefix="jarvis-aprov-")) / "aprovacoes.json"

    print("-- G1. app conectado desde antes do pedido: fica só no app --")
    w = WhatsAppFalso()
    g = familia.GrupoFamilia(w, "claude", "sonnet", app_desde=lambda: time.time() - 600)
    novo_pedido("Chris", "abre a pasta de fotos", ha_s=60)
    g._aprovacoes_pelo_whatsapp()
    checa("nada vai para o WhatsApp", w.mandadas == [], w.mandadas)

    print("-- G2. app fora: depois de 45 s vai para o WhatsApp dele --")
    aprovacoes._gravar([])
    w = WhatsAppFalso()
    g = familia.GrupoFamilia(w, "claude", "sonnet", app_desde=lambda: None)
    novo_pedido("Chris", "toca música no PC", ha_s=10)
    g._aprovacoes_pelo_whatsapp()
    checa("antes dos 45 s, espera o app", w.mandadas == [], w.mandadas)
    a = novo_pedido("Chris", "abre o Spotify", ha_s=60)
    g._aprovacoes_pelo_whatsapp()
    checa("depois, manda para o chat dele mesmo, com quem pediu e o pedido",
          len(w.mandadas) == 1 and w.mandadas[0][0] == w.meu_jid()
          and "Chris" in w.mandadas[0][1] and "abre o Spotify" in w.mandadas[0][1], w.mandadas)
    g._aprovacoes_pelo_whatsapp()
    checa("e só uma vez", len(w.mandadas) == 1, w.mandadas)

    print("-- G3. ele responde 'sim' lá: o pedido é liberado --")
    w.respostas.append((dt.datetime.now() - dt.timedelta(minutes=5), "sim"))  # antes do pedido: não vale
    w.respostas.append((dt.datetime.now() + dt.timedelta(seconds=1), "anotar: comprar pão amanhã cedo"))
    g._aprovacoes_pelo_whatsapp()
    checa("resposta antiga ou texto comprido não contam",
          [x["estado"] for x in aprovacoes._ler() if x["id"] == a["id"]] == ["esperando"])
    w.respostas.append((dt.datetime.now() + dt.timedelta(seconds=2), "Sim!"))
    g._aprovacoes_pelo_whatsapp()
    checa("o 'sim' libera", [x["estado"] for x in aprovacoes._ler() if x["id"] == a["id"]] == ["aprovado"])
    checa("e ele recebe a confirmação", "Liberado" in w.mandadas[-1][1], w.mandadas[-1:])

    print("-- G4. um 'sim' vale um pedido só --")
    aprovacoes._gravar([])
    w = WhatsAppFalso()
    g = familia.GrupoFamilia(w, "claude", "sonnet", app_desde=lambda: None)
    b1 = novo_pedido("Karyn", "abre o e-mail", ha_s=90)
    g._aprovacoes_pelo_whatsapp()
    time.sleep(0.01)
    b2 = novo_pedido("Chris", "manda foto pro tio", ha_s=60)
    g._aprovacoes_pelo_whatsapp()
    w.respostas.append((dt.datetime.now() + dt.timedelta(seconds=1), "não"))
    g._aprovacoes_pelo_whatsapp()
    g._aprovacoes_pelo_whatsapp()
    estados = {x["id"]: x["estado"] for x in aprovacoes._ler()}
    checa("o 'não' vai para o pedido mais recente, e o outro continua esperando",
          estados[b2["id"]] == "recusado" and estados[b1["id"]] == "esperando", estados)

    print("-- G5. app que conectou DEPOIS do pedido não conta --")
    aprovacoes._gravar([])
    w = WhatsAppFalso()
    g = familia.GrupoFamilia(w, "claude", "sonnet", app_desde=lambda: time.time() - 5)
    novo_pedido("Chris", "abre o Steam", ha_s=60)
    g._aprovacoes_pelo_whatsapp()
    checa("o pedido vai para o WhatsApp (o app não estava lá quando ele chegou)", len(w.mandadas) == 1,
          w.mandadas)

    print(f"\n  {ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
