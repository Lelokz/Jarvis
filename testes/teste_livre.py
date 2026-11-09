"""As coisas novas do Léo (09/11/2026): personas, memória viva, arquivo do
WhatsApp e raspagem. Tudo numa pasta temporária (JARVIS_DADOS), sem internet:
o Ollama de verdade só se estiver ligado (sem ele, a busca é por palavra).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ["JARVIS_DADOS"] = tempfile.mkdtemp(prefix="jarvis-livre-")

from jarvis import personas  # noqa: E402
from jarvis.nucleo import memoria_viva, raspagem, whatsapp_arquivo  # noqa: E402

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
    print("-- personas --")
    checa("as quatro existem", personas.lista() == ["bebado", "friday", "jarvis", "senhor"], personas.lista())
    checa("modos são senhor e bêbado", personas.modos() == ["bebado", "senhor"], personas.modos())
    checa("começa normal", personas.atual() == "normal")
    personas.definir("bêbado")
    checa("liga o bêbado (com acento também)", personas.atual() == "bebado")
    personas.definir("normal")
    checa("volta ao normal", personas.atual() == "normal")
    try:
        personas.definir("nenhuma")
        checa("modo que não existe dá erro", False)
    except FileNotFoundError:
        checa("modo que não existe dá erro", True)
    bloco = personas.para_instrucoes()
    checa("instruções têm Jarvis, Friday e os modos",
          all(x in bloco for x in ("Persona: jarvis", "Persona: friday", "Modo: senhor", "Modo: bebado")))
    checa("o texto aprovado está lá", "zoeira e gracinha de namorada" in bloco
          and "mordomo responsável" in bloco)

    print("-- memória viva --")
    memoria_viva.gravar("teste", "o carro do vizinho é um gol branco", "teste")
    achados = memoria_viva.buscar("gol branco")
    checa("acha o que gravou", any("gol branco" in a["texto"] for a in achados), achados)
    checa("aspas na busca não quebram", isinstance(memoria_viva.buscar('"gol" (branco'), list))
    checa("busca só com símbolo não quebra", isinstance(memoria_viva.buscar("?!"), list))
    vet = memoria_viva._embed("teste")
    print(f"  (Ollama {'respondeu: busca por significado ligada' if vet is not None else 'fora: só por palavra'})")
    if vet is not None:
        achados = memoria_viva.buscar("automóvel do vizinho")
        checa("acha pelo significado (automóvel = carro)", any("gol branco" in a["texto"] for a in achados), achados)

    print("-- arquivo do WhatsApp --")
    whatsapp_arquivo.guardar({"id": "M1", "chat": "c@g.us", "autor": "ana", "ts": 1, "texto": "oi gente"})
    whatsapp_arquivo.guardar({"id": "M2", "chat": "c@g.us", "autor": "pedro", "ts": 2, "texto": "vou apagar"})
    whatsapp_arquivo.apagar("M2")
    conversa = whatsapp_arquivo.conversa("c@g.us")
    checa("a conversa em ordem", [m["texto"] for m in conversa] == ["oi gente", "vou apagar"], conversa)
    checa("a apagada continua lá, marcada", conversa[1]["apagada"] == 1)
    checa("procura", [m["autor"] for m in whatsapp_arquivo.procurar("apagar")] == ["pedro"])

    print("-- raspagem --")
    checa("downloads no HD", str(raspagem.DESTINO).startswith("/mnt/"), raspagem.DESTINO)
    paginas = {"https://archive.ph/newest/https://x.com/a": "<html><body>captcha</body></html>",
               "https://x.com/a": "<html><body><article><p>" + "Texto da matéria inteira. " * 20
                                  + "</p></article></body></html>"}
    raspagem._pagina = lambda url: paginas[url]
    checa("archive vazio: tenta o site direto", "Texto da matéria" in raspagem.sem_paywall("https://x.com/a"))

    print(f"\n{ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
