"""A etapa 4 do tchan (11/11/2026): as contas de Ajustes → Uso (gasto por
dia, ritmo, o que mais gastou), o tempo conversando tirado dos registros, o
Modo foco (frases, ajuste, o WhatsApp guardado e o resumo no fim) e o
protocolo. Sem Claude e sem microfone.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import time
import types
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from jarvis import ajustes  # noqa: E402
from jarvis.agente.reflexos import comando_foco  # noqa: E402
from jarvis.nucleo import estatisticas as est  # noqa: E402
from jarvis.ponte.protocolo import ErroDeProtocolo, ler_pedido  # noqa: E402

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
    agora = dt.datetime(2026, 11, 11, 20, 0).timestamp()
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        arq = tmp / "uso.jsonl"
        volta = agora + 2 * 86400
        print("-- o uso por dia e o ritmo --")
        # ontem: 10% com o Sonnet; hoje: 0.30 -> 0.50 com o Opus no modo code, depois +0.05 Sonnet
        pontos = [(agora - 30 * 3600, 0.20, "claude-sonnet-5-5", ""), (agora - 28 * 3600, 0.30, "claude-opus-5-5", "Loft"),
                  (agora - 10 * 3600, 0.50, "claude-sonnet-5-5", ""), (agora - 1 * 3600, 0.55, "claude-sonnet-5-5", "")]
        for tt, u, m, c in pontos:
            est.registrar({"semana": {"uso": u, "volta_em": volta}, "cinco_horas": {"uso": 0.1}}, m, c, arq, agora=tt)
        r = est.uso(arq, agora)
        por_dia = {d["dia"]: d["pct"] for d in r["dias"]}
        checa("gasto de ontem e de hoje", por_dia["2026-11-10"] == 10.0 and por_dia["2026-11-11"] == 25.0, por_dia)
        checa("sete dias no gráfico", len(r["dias"]) == 7 and r["dias"][-1]["dia"] == "2026-11-11")
        checa("o cérebro que mais gastou hoje: o Opus (80%)", r["cerebro"] == {"nome": "Opus", "pct": 80}, r["cerebro"])
        checa("o modo code de hoje", r["code"] == {"nome": "Loft", "pct": 20.0}, r["code"])
        checa("o ritmo: acaba antes de renovar", r["previsao"] and r["previsao"]["antes_de_renovar"]
              and agora < r["previsao"]["acaba_em"] < volta, r["previsao"])
        # semana renovada no meio: a queda não vira gasto negativo
        arq2 = tmp / "uso2.jsonl"
        est.registrar({"semana": {"uso": 0.9, "volta_em": agora - 100}}, "opus", "", arq2, agora=agora - 7200)
        est.registrar({"semana": {"uso": 0.04, "volta_em": agora + 7 * 86400}}, "opus", "", arq2, agora=agora - 60)
        checa("semana que renovou conta só o novo", est.uso(arq2, agora)["dias"][-1]["pct"] == 4.0)
        checa("sem histórico: sem previsão", est.uso(tmp / "nada.jsonl", agora)["previsao"] is None)

        print("-- o tempo conversando --")
        logs = tmp / "logs"; logs.mkdir()
        def ev(h, m, estado, **kw):
            return json.dumps({"tipo": "estado", "momento": dt.datetime(2026, 11, 11, h, m).isoformat(), "estado": estado, **kw})
        (logs / "jarvis-20261111-080000.jsonl").write_text("\n".join([
            ev(8, 0, "acordou"), ev(8, 20, "dormiu"),
            ev(8, 10, "pedido", origem="voz"),                     # dentro do acordado: não soma de novo
            ev(9, 0, "pedido", origem="celular"), ev(9, 1, "resposta"),
            ev(9, 5, "pedido", origem="celular"), ev(9, 6, "resposta"),
        ]) + "\n")
        r = est.tempo_e_pedidos(logs, agora)
        checa("minutos de hoje (20 acordado + 1,5 + 1,5 do celular)", r["dias"][-1]["min"] == 23, r["dias"][-1])
        checa("pedidos por origem", r["pedidos"] == {"voz": 1, "celular": 2}, r["pedidos"])

    print("-- o modo foco --")
    casos = [("Modo foco por uma hora.", 60), ("modo foco", -1), ("modo foco por 30 minutos", 30),
             ("liga o modo foco por duas horas", 120), ("Sai do modo foco.", 0), ("desliga o foco", 0),
             ("modo foco por meia hora", 30), ("qual o foco do vídeo?", None)]
    for frase, esperado in casos:
        checa(repr(frase), comando_foco(frase) == esperado, comando_foco(frase))
    with tempfile.TemporaryDirectory() as t:
        antes = ajustes.ARQUIVO
        ajustes.ARQUIVO = Path(t) / "ajustes.json"
        try:
            checa("começa desligado", not ajustes.em_foco())
            ajustes.mudar(foco_ate=time.time() + 600)
            checa("liga com hora", ajustes.em_foco())
            ajustes.mudar(foco_ate=-1)
            checa("até desligar", ajustes.em_foco())
            ajustes.mudar(foco_ate=time.time() - 5)
            checa("passou da hora: desligado", not ajustes.em_foco())

            import assistente
            c = assistente.Ciclo.__new__(assistente.Ciclo)
            c.registrador = types.SimpleNamespace(registrar_estado=lambda *a, **k: None)
            c.emitir_ajustes = lambda: None
            c.jogo, c.gravando, c.persona = None, False, "friday"
            c._whats_no_jogo = {}
            fala = c.definir_foco(60)
            checa("liga falando até que horas", fala.startswith("Modo foco até as ") and ajustes.em_foco(), fala)
            c._whats_no_jogo = {"Mãe": 2, "Lucas": 1}
            checa("desligar com WhatsApp guardado", c.definir_foco(0) == "Saí do modo foco." and not ajustes.em_foco())
            checa("o resumo vem depois", c.checar_foco() == "Enquanto você tava no foco, chegaram 3 mensagens no WhatsApp: 2 de Mãe e 1 de Lucas.")
            ajustes.mudar(foco_ate=time.time() - 1)
            c._whats_no_jogo = {"Mãe": 1}
            checa("acabou pelo tempo: avisa e resume", c.checar_foco() == "Acabou o modo foco. Enquanto você tava no foco, chegou uma mensagem no WhatsApp, de Mãe."
                  and ajustes.ler()["foco_ate"] == 0)
            checa("depois disso, nada", c.checar_foco() is None)
        finally:
            ajustes.ARQUIVO = antes

    print("-- o protocolo --")
    lp = lambda d: ler_pedido(json.dumps(d).encode())
    checa("estatisticas", lp({"pedir": "estatisticas"}) == ("estatisticas", {}))
    checa("foco", lp({"pedir": "foco", "minutos": 60}) == ("foco", {"minutos": 60}))
    try:
        lp({"pedir": "foco", "minutos": 999})
        checa("recusa foco esquisito", False)
    except ErroDeProtocolo:
        checa("recusa foco esquisito", True)
    import porta_remota
    checa("o celular pode pedir", {"estatisticas", "foco"} <= porta_remota.PEDIDOS_DO_CELULAR)

    print(f"\n{ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
