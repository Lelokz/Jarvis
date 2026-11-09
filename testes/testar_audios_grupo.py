"""Os áudios dos grupos (09/11/2026): baixa pela ponte, transcreve com o
Whisper do Jarvis, apaga o arquivo e guarda o texto. "Jarvis, ..." falado
chama igual ao escrito, e o histórico mostra o que foi dito. Sem WhatsApp nem
Whisper de verdade: banco sqlite temporário, áudio gerado pelo ffmpeg e um
"Whisper" que devolve o texto combinado para cada mensagem.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from jarvis import ajustes, memorias  # noqa: E402
from jarvis.grupo import audios, familia, historico  # noqa: E402
from jarvis.nucleo import aprovacoes  # noqa: E402
from jarvis.nucleo.whatsapp import WhatsApp  # noqa: E402

ok = falhou = 0
A = "111@g.us"


def checa(nome, cond, detalhe=""):
    global ok, falhou
    if cond:
        ok += 1
        print(f"  PASSOU  {nome}", flush=True)
    else:
        falhou += 1
        print(f"  FALHOU  {nome}  {detalhe}", flush=True)


def main() -> int:
    pasta = Path(tempfile.mkdtemp(prefix="jarvis-audios-"))
    memorias.GRUPOS = pasta / "grupos"
    ajustes.ARQUIVO = pasta / "ajustes.json"
    aprovacoes.ARQUIVO = pasta / "aprovacoes.json"
    ajustes.ARQUIVO.write_text(json.dumps({"grupos": [A], "grupo_ligado": True, "nome": "Léo"}))

    caminho_db = pasta / "messages.db"
    con = sqlite3.connect(caminho_db)
    con.execute("CREATE TABLE messages (id TEXT, chat_jid TEXT, sender TEXT, content TEXT, "
                "timestamp TIMESTAMP, is_from_me BOOLEAN, media_type TEXT, PRIMARY KEY (id, chat_jid))")
    con.commit()
    con.close()

    def por(i, sender, texto="", midia="", segundos_atras=0):
        c = sqlite3.connect(caminho_db)
        quando = (dt.datetime.now() - dt.timedelta(seconds=segundos_atras)).astimezone().isoformat(sep=" ")
        c.execute("INSERT INTO messages VALUES (?,?,?,?,?,0,?)", (i, A, sender, texto, quando, midia))
        c.commit()
        c.close()

    w = WhatsApp(caminho_db, "http://ponte/api/send")
    w.nome_de = lambda jid, nome=None: {"ana@lid": "Ana", "pedro@lid": "Pedro"}.get(jid, "alguém")
    w.reagir = lambda *a: reacoes.append(a) or True
    reacoes: list = []

    # A ponte de mentira: gera um ogg de 1 s; "VELHO" não baixa mais.
    baixados: list[Path] = []
    ultimo = {"id": ""}

    def baixar(chat, id_msg):
        ultimo["id"] = id_msg
        if id_msg.startswith("VELHO"):
            return None
        arq = pasta / f"{id_msg}.ogg"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1", "-c:a", "libopus", str(arq)], check=True)
        baixados.append(arq)
        return str(arq)
    w.baixar = baixar

    falado = {"AU1": "Jarvis, que horas são?", "AU2": "bom dia gente", "AU3": "Friday, me ajuda",
              "AU4": "áudio antigo"}
    tamanhos: list[int] = []

    def whisper(audio):
        tamanhos.append(len(audio))
        return falado[ultimo["id"]]

    g = familia.GrupoFamilia(w, "claude", "sonnet", app_desde=lambda: None, transcrever=whisper)
    atendidos: list[tuple[str, list, list]] = []

    async def atender_falso(jid, persona, chamadas, seguidas=None, recados_da_hora=None):
        atendidos.append((persona, [m.texto for m in chamadas], [m.texto for m in seguidas or []]))
    g._atender = atender_falso

    print("-- A1. áudio chamando o Jarvis é atendido --")
    g._uma_volta()  # primeira volta: marca onde começa
    por("AU1", "ana@lid", midia="audio")
    por("AU2", "pedro@lid", midia="audio")
    por("T1", "pedro@lid", "Friday, e tu?")
    g._uma_volta()
    checa("o Jarvis recebeu o áudio da Ana já em texto",
          ("jarvis", ["(áudio) Jarvis, que horas são?"], []) in atendidos, atendidos)
    checa("o áudio do Pedro sem nome não foi pra ninguém",
          all("bom dia" not in str(a) for a in atendidos), atendidos)
    checa("👀 no áudio da Ana", any(r[1] == "AU1" for r in reacoes), reacoes)
    checa("o áudio virou 1 s a 16 kHz", tamanhos and 15000 <= tamanhos[0] <= 17000, tamanhos)
    checa("o arquivo baixado foi apagado", baixados and not any(b.exists() for b in baixados))
    feitos = json.loads((memorias.pasta_do_grupo(A) / audios.ARQUIVO).read_text(encoding="utf-8"))
    checa("guardou os dois", feitos.get("AU1") == "Jarvis, que horas são?" and feitos.get("AU2") == "bom dia gente")

    print("-- A2. já transcrito não baixa de novo --")
    n = len(baixados)
    texto = g._audios.transcrever(A, "AU1")
    checa("devolve o guardado", texto == "Jarvis, que horas são?" and len(baixados) == n)
    msgs = g._mensagens(A, 10)
    checa("a conversa mostra o texto do áudio", any(m.texto == "(áudio) bom dia gente" for m in msgs))

    print("-- A3. áudios antigos: o mais novo primeiro; o que não baixa fica marcado --")
    por("VELHO1", "ana@lid", midia="audio", segundos_atras=99999)
    por("AU4", "pedro@lid", midia="audio", segundos_atras=5000)
    checa("pendentes, o mais novo primeiro", g._audios.pendentes(A) == ["AU4", "VELHO1"], g._audios.pendentes(A))
    for i in g._audios.pendentes(A):
        g._audios.transcrever(A, i)
    checa("nada mais pendente", g._audios.pendentes(A) == [])
    ultimo["id"] = "ninguém"
    g._audios.transcrever(A, "VELHO1")
    checa("o que não baixou não é tentado de novo", ultimo["id"] == "ninguém")

    print("-- A3b. celular sem responder: não marca, tenta depois --")
    por("AU9", "ana@lid", midia="audio", segundos_atras=10)
    def baixar_sem_resposta(chat, id_msg):
        w.erro_do_download = "failed to download media: 403; reenvio: o celular não respondeu"
        return None
    w.baixar, guardado = baixar_sem_resposta, w.baixar
    g._audios.transcrever(A, "AU9")
    checa("não ficou marcado", "AU9" not in g._audios.todas(A))
    checa("sai dos pendentes por enquanto", "AU9" not in g._audios.pendentes(A))
    g._audios._adiados["AU9"] = 0
    w.baixar = guardado
    falado["AU9"] = "voltou"
    checa("depois volta e transcreve", g._audios.pendentes(A) == ["AU9"] and g._audios.transcrever(A, "AU9") == "voltou")

    print("-- A4. o histórico com os áudios --")
    p = g._puxador
    checa("escreveu", p.escrever(A, "Família"))
    linhas = (memorias.pasta_do_grupo(A) / historico.ARQUIVO).read_text(encoding="utf-8")
    checa("áudio transcrito", "Ana: (áudio) Jarvis, que horas são?" in linhas)
    checa("áudio que não baixou", "Ana: (áudio que não deu pra baixar)" in linhas)
    checa("sem mudança não reescreve", not p.escrever(A, "Família"))
    por("AU5", "ana@lid", midia="audio")
    p.escrever(A, "Família")
    falado["AU5"] = "chegou depois"
    g._audios.transcrever(A, "AU5")
    checa("reescreve quando mais um áudio vira texto", p.escrever(A, "Família"))
    checa("e o texto novo está lá", "(áudio) chegou depois" in
          (memorias.pasta_do_grupo(A) / historico.ARQUIVO).read_text(encoding="utf-8"))

    print("-- A5. sem Whisper (transcrever=None) continua como antes --")
    g2 = familia.GrupoFamilia(w, "claude", "sonnet", app_desde=lambda: None)
    checa("áudio aparece só como (áudio)", any(m.texto == "(áudio)" for m in g2._mensagens(A, 10)))

    print(f"\n{ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
