"""A etapa 5 do tchan (11/11/2026): a lateral nova. Os recados que repetem
(listar, tocar uma vez por vez, apagar), a galeria Feitos (o que conta, o que
fica de fora, o arquivo gerado por comando, a porta só entrega o que está na
galeria), as rotinas e o protocolo. Sem Claude e sem microfone.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from jarvis.nucleo import feitos, recados  # noqa: E402
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
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        print("-- os recados que repetem --")
        a = tmp / "recados.md"
        a.write_text("# notas soltas\n- 2026-11-11 18:00 | tirar a roupa\n- todo dia 07:00 | falar a agenda\n"
                     "- toda seg 07:30 | lembrar a Karyn\n- toda seg qua sex 18:00 | academia\n")
        quarta = dt.datetime(2026, 11, 11, 7, 30)
        lista = recados.listar(a, quarta)
        checa("lista em ordem, com quando e repetição", [(x["texto"], x["repete"]) for x in lista] == [
            ("tirar a roupa", ""), ("academia", "toda seg, qua, sex"), ("falar a agenda", "todo dia"),
            ("lembrar a Karyn", "toda segunda")], lista)
        checa("a próxima da segunda é a semana que vem",
              dt.datetime.fromtimestamp(lista[3]["quando"]) == dt.datetime(2026, 11, 16, 7, 30))
        checa("o de todo dia toca (30 min depois)", recados.vencidos(a, quarta) == ["11/11 07:00 — falar a agenda"])
        checa("e não toca de novo", recados.vencidos(a, quarta + dt.timedelta(minutes=5)) == [])
        checa("o que repete continua no arquivo", "todo dia 07:00" in a.read_text())
        checa("às 18h: o de uma vez e o da quarta", recados.vencidos(a, dt.datetime(2026, 11, 11, 18, 1)) ==
              ["11/11 18:00 — tirar a roupa", "11/11 18:00 — academia"])
        checa("o de uma vez sai do arquivo", "tirar a roupa" not in a.read_text())
        checa("NOVA desligada 3 h depois da hora: não toca atrasado demais",
              recados.vencidos(a, dt.datetime(2026, 11, 12, 10, 30)) == [])
        checa("no dia seguinte toca de novo", recados.vencidos(a, dt.datetime(2026, 11, 13, 7, 1)) == ["13/11 07:00 — falar a agenda"])
        alvo = next(x for x in recados.listar(a, quarta) if x["texto"] == "academia")
        checa("a lixeira apaga só ele", recados.apagar(a, alvo["id"]) and "academia" not in a.read_text()
              and "# notas soltas" in a.read_text())
        checa("apagar de novo: não achou", not recados.apagar(a, alvo["id"]))
        checa("as instruções ensinam a repetir", "todo dia 07:00" in recados.como_usar())

        print("-- os Feitos --")
        arq = tmp / "feitos.jsonl"
        trab = tmp / "trabalho"; trab.mkdir()
        (trab / "foto.png").write_bytes(b"\x89PNG")
        (trab / "codigo.py").write_text("def ola():\n\treturn 1\n")
        (trab / "notas.xyz").write_text("x")
        antes_fora = feitos._FORA
        feitos._FORA = [f for f in antes_fora if not tmp.resolve().is_relative_to(f)]
        checa("imagem conta", feitos.registrar(trab / "foto.png", "s1", arquivo=arq))
        checa("código conta", feitos.registrar(trab / "codigo.py", "s1", arquivo=arq))
        checa("tipo desconhecido não", not feitos.registrar(trab / "notas.xyz", arquivo=arq))
        checa("arquivo que não existe não", not feitos.registrar(trab / "nada.png", arquivo=arq))
        checa("coisa da própria NOVA não", not feitos.registrar(Path.home() / ".local/share/jarvis/ajustes.json", arquivo=arq))
        feitos.registrar(trab / "foto.png", "s2", "mandou", arquivo=arq)
        lista = feitos.listar(arq)
        checa("sem repetir, o mais novo primeiro", [f["nome"] for f in lista] == ["foto.png", "codigo.py"]
              and lista[0]["como"] == "mandou", lista)
        checa("a prévia do código, sem tabulação", lista[1]["previa"].startswith("def ola():\n  return 1"), lista[1]["previa"])
        checa("a imagem é a própria miniatura", lista[0]["miniatura"] == str((trab / "foto.png").resolve()))
        inicio = time.time()
        (trab / "render.mp4").write_bytes(b"0")
        achados = feitos.do_comando(f'ffmpeg -i entrada.mov -c:v libx264 "{trab}/render.mp4" && echo ok', trab, inicio)
        checa("o comando que gerou o vídeo", achados == [trab / "render.mp4"], achados)
        velho = trab / "velho.pdf"; velho.write_text("x"); os.utime(velho, (inicio - 600, inicio - 600))
        checa("arquivo citado mas não mudado não conta", feitos.do_comando(f"cat {velho}", trab, inicio) == [])
        checa("relativo à pasta de trabalho", feitos.do_comando("pandoc a.md -o render.mp4", trab, inicio) == [trab / "render.mp4"])
        ident = lista[0]["id"]
        checa("a porta entrega o que está na galeria", feitos.caminho_de(ident, arq) == (trab / "foto.png").resolve())
        checa("e nada fora dela", feitos.caminho_de("0123456789ab", arq) is None and feitos.caminho_de("../x", arq) is None)
        feitos._FORA = antes_fora

    print("-- rotinas e protocolo --")
    r = feitos.rotinas()
    checa("as rotinas vêm com nome e estado", all({"nome", "estado", "quando"} <= set(x) for x in r))
    lp = lambda d: ler_pedido(json.dumps(d).encode())
    checa("agendados / feitos", lp({"pedir": "agendados"}) == ("agendados", {}) and lp({"pedir": "feitos"}) == ("feitos", {}))
    checa("apagar_recado", lp({"pedir": "apagar_recado", "id": "0123456789"}) == ("apagar_recado", {"id": "0123456789"}))
    checa("novo_agendado", lp({"pedir": "novo_agendado", "texto": " toda sexta  18h lixo "})[1] == {"texto": "toda sexta 18h lixo"})
    for ruim in ({"pedir": "apagar_recado", "id": "../etc"}, {"pedir": "novo_agendado", "texto": ""}):
        try:
            lp(ruim)
            checa(f"recusa {ruim}", False)
        except ErroDeProtocolo:
            checa(f"recusa {ruim}", True)
    import porta_remota
    checa("o celular pode pedir", {"agendados", "apagar_recado", "novo_agendado", "feitos"} <= porta_remota.PEDIDOS_DO_CELULAR)

    print(f"\n{ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
