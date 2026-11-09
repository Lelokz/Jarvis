"""Vários grupos do WhatsApp (09/11/2026): marcar/desmarcar, cada grupo com a
própria leitura e limite (50 por hora), e o pedido aprovado volta pro grupo
certo. Sem WhatsApp nem Claude de verdade: ajustes e aprovações em pasta temporária.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from jarvis import ajustes  # noqa: E402
from jarvis.grupo import familia  # noqa: E402
from jarvis.nucleo import aprovacoes  # noqa: E402

ok = falhou = 0
A, B, C = "111@g.us", "222@g.us", "333@g.us"


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
        self.msgs: dict[str, list[tuple[str, int, str, dt.datetime]]] = {}

    def nome_de(self, jid):
        return {A: "Família", B: "Amigos", C: "Escola"}.get(jid, "?")

    def meu_jid(self):
        return "5500@s.whatsapp.net"

    def enviar(self, jid, texto, arquivo=None):
        self.mandadas.append((jid, texto))
        return True, ""

    def eu_mandei_desde(self, jid, desde):
        return []

    def _quando(self, t):
        return t

    def _consultar(self, _sql, args):
        jid, quantas = args
        return list(reversed(self.msgs.get(jid, [])))[:quantas]

    def chega(self, jid, quem, texto):
        self.msgs.setdefault(jid, []).append((quem, 0, texto, dt.datetime.now()))


def main() -> int:
    pasta = Path(tempfile.mkdtemp(prefix="jarvis-grupos-"))
    ajustes.ARQUIVO = pasta / "ajustes.json"
    aprovacoes.ARQUIVO = pasta / "aprovacoes.json"

    print("-- V1. o arquivo antigo (um grupo só) vira lista --")
    ajustes.ARQUIVO.write_text(json.dumps({"grupo_jid": A, "grupo_ligado": True}))
    checa("o grupo antigo entra na lista", ajustes.ler()["grupos"] == [A], ajustes.ler())
    checa("e continua ligado", ajustes.grupos_ativos() == [A])

    print("-- V2. marcar e desmarcar pelo Conectar --")
    from jarvis import conectar
    import sqlite3
    banco = pasta / "messages.db"
    con = sqlite3.connect(banco)
    con.execute("CREATE TABLE chats (jid TEXT, name TEXT, last_message_time TEXT)")
    con.executemany("INSERT INTO chats VALUES (?,?,?)", [(A, "Família", "3"), (B, "Amigos", "2"), (C, "Escola", "1")])
    con.commit(); con.close()

    class Cfg:
        class whatsapp:
            pass
    Cfg.whatsapp.banco = str(banco)
    r = conectar._grupo(Cfg, "escolher", B, None)
    checa("marcar o segundo não desmarca o primeiro", r["escolhidos"] == [A, B], r)
    r = conectar._grupo(Cfg, "escolher", C, None)
    checa("três marcados", r["escolhidos"] == [A, B, C] and r["estado"] == "conectado", r)
    r = conectar._grupo(Cfg, "escolher", B, None)
    checa("tocar de novo desmarca só aquele", r["escolhidos"] == [A, C], r)
    checa("o app antigo ainda recebe um 'escolhido'", r["escolhido"] == A, r)
    conectar._grupo(Cfg, "escolher", A, None)
    r = conectar._grupo(Cfg, "escolher", C, None)
    checa("sem nenhum, desliga", r["escolhidos"] == [] and r["ligado"] is False, r)
    r = conectar._grupo(Cfg, "escolher", B, None)
    checa("o primeiro marcado liga sozinho", r["escolhidos"] == [B] and r["ligado"] is True, r)
    conectar._grupo(Cfg, "escolher", A, None)

    print("-- V3. o Jarvis atende cada grupo separado --")
    w = WhatsAppFalso()
    g = familia.GrupoFamilia(w, "claude", "sonnet", app_desde=lambda: None)
    atendidos: list[tuple[str, list]] = []

    async def atender_falso(jid, chamadas, aberta=False, recados_da_hora=None):
        atendidos.append((jid, [t for _, t, _ in chamadas]))
    g._atender = atender_falso
    w.chega(A, "Tia", "Jarvis, mensagem velha")
    g._uma_volta()  # primeira volta: marca onde começa, não responde o velho
    checa("não responde mensagem de antes", atendidos == [], atendidos)
    w.chega(A, "Chris", "Jarvis, que horas são?")
    w.chega(B, "Pedro", "jarvis conta uma piada")
    w.chega(B, "Pedro", "conversa sem chamar")
    g._uma_volta()
    checa("respondeu nos dois grupos, cada um com a sua mensagem",
          sorted(atendidos) == [(A, ["Jarvis, que horas são?"]), (B, ["jarvis conta uma piada"])], atendidos)

    print("-- V4. limite de 50 por hora em CADA grupo --")
    atendidos.clear()
    g._chamadas[A] = familia.deque([familia.time.time()] * 50)
    w.chega(A, "Chris", "Jarvis, de novo")
    w.chega(B, "Pedro", "Jarvis, e aí")
    g._uma_volta()
    checa("o grupo cheio não chama o Claude", all(j != A for j, _ in atendidos), atendidos)
    checa("e avisa lá que volta depois", any(j == A and "daqui a pouco" in t for j, t in w.mandadas), w.mandadas)
    checa("o outro grupo continua respondendo", [j for j, _ in atendidos] == [B], atendidos)
    checa("o limite é 50", familia.MAX_POR_HORA == 50)

    print("-- V5. pedido aprovado volta pro grupo de onde veio --")
    a = aprovacoes.criar("Pedro", "abre o Spotify", jid=B)
    aprovacoes.responder(a["id"], False)
    w.mandadas.clear()
    g._uma_volta()
    checa("o 'não liberou' vai pro grupo dos Amigos",
          len(w.mandadas) == 1 and w.mandadas[0][0] == B and "não liberou" in w.mandadas[0][1], w.mandadas)
    a = aprovacoes.criar("Tia", "toca música", jid=A)
    aprovacoes.responder(a["id"], True)
    g._uma_volta()
    saida = g.pegar()
    checa("o aprovado manda responder no grupo certo, com o nome dele",
          saida and saida[0] == "executar" and A in saida[1] and "Família" in saida[1], saida)

    print("-- V6. grupo desmarcado para de ser lido --")
    atendidos.clear()
    conectar._grupo(Cfg, "escolher", B, None)
    w.chega(B, "Pedro", "Jarvis, ainda tá aí?")
    g._uma_volta()
    checa("não responde no grupo desmarcado", all(j != B for j, _ in atendidos), atendidos)

    print(f"\n  {ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
