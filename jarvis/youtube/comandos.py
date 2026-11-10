"""O que o Jarvis e a Friday fazem no canal pela voz (Painel do Canal, etapa 6).

Cada comando devolve um texto curto para eles falarem. Tudo o que MUDA algo
no YouTube (editar, agendar, responder) só roda depois do "pode" do Léo: a
regra está no CLAUDE.md da casa.

    python -m jarvis.youtube comentarios [novos|perguntas|todos]
    python -m jarvis.youtube responder <id do comentário> <texto>
    python -m jarvis.youtube lido <id do comentário|todos>
    python -m jarvis.youtube agendar <vídeo> <dd/mm/aaaa> <HH:MM>
    python -m jarvis.youtube desagendar <vídeo>
    python -m jarvis.youtube titulo <vídeo> <novo título>
    python -m jarvis.youtube descricao <vídeo> <nova descrição>
    python -m jarvis.youtube visibilidade <vídeo> <publico|nao-listado|privado>
    python -m jarvis.youtube cards
    python -m jarvis.youtube ideia <título> [jogo=Doors] [data=14/11/2026]
    python -m jarvis.youtube mover <card> <ideia|gravando|editando|pronto|agendado|postado>
    python -m jarvis.youtube analises

<vídeo> = o id do YouTube ou parte do título; <card> = o número ou parte do título.
"""

from __future__ import annotations

import json
import re
import unicodedata

from jarvis.youtube import analises, comentarios, dados, editar, producao


class Ambiguo(ValueError):
    pass


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def achar(falado: str) -> dict:
    """O vídeo pelo id ou pelo nome. Nenhum ou vários: erro explicando."""
    con = dados.abrir()
    v = con.execute("SELECT * FROM videos WHERE id = ?", (falado.strip(),)).fetchone()
    con.close()
    if v:
        return dict(v)
    achados = dados.achar_video(falado)
    if not achados:
        raise ValueError(f"não achei vídeo com \"{falado}\" no nome")
    if len(achados) > 1:
        nomes = "; ".join(f"{a['titulo']} (id {a['id']})" for a in achados[:5])
        raise Ambiguo(f"tem {len(achados)} vídeos parecidos: {nomes}. Qual?")
    return achados[0]


def achar_card(falado: str) -> dict:
    cards = producao.listar()
    if falado.strip().isdigit():
        for c in cards:
            if c["id"] == int(falado):
                return c
    palavras = [p for p in re.findall(r"\w+", _sem_acento(falado)) if len(p) > 2]
    notas = [(sum(p in _sem_acento(c["titulo"]) for p in palavras), c) for c in cards]
    melhor = max((n for n, _ in notas), default=0)
    achados = [c for n, c in notas if n == melhor and n > 0]
    if not achados:
        raise ValueError(f"não achei card com \"{falado}\"")
    if len(achados) > 1:
        raise Ambiguo("tem mais de um card parecido: " + "; ".join(f"{c['titulo']} (nº {c['id']})" for c in achados[:5]))
    return achados[0]


def lista_comentarios(qual: str = "novos") -> str:
    todos = comentarios.listar(300)
    if qual == "novos":
        lista = [c for c in todos if not c["lido"]]
    elif qual == "perguntas":
        lista = [c for c in todos if c["pergunta"] and not c["respondido"]]
    else:
        lista = todos[:15]
    if not lista:
        return {"novos": "Nenhum comentário novo.", "perguntas": "Nenhuma pergunta sem resposta."}.get(qual, "Nenhum comentário.")
    linhas = [f"{len(lista)} comentário(s):"]
    for c in lista[:15]:
        linhas.append(f"- [{c['id']}] {c['autor']} em \"{c['video_titulo'] or c['video']}\": {c['texto'][:300]}"
                      + (" (pergunta)" if c["pergunta"] else "") + (" (já respondido)" if c["respondido"] else ""))
    if len(lista) > 15:
        linhas.append(f"... e mais {len(lista) - 15} (estão no painel).")
    return "\n".join(linhas)


def editar_campo(falado: str, campo: str, valor: str) -> str:
    v = achar(falado)
    titulo, descricao = v["titulo"], v["descricao"]
    tags, visib = json.loads(v["tags"] or "[]"), v["visibilidade"]
    if campo == "titulo":
        titulo = valor
    elif campo == "descricao":
        descricao = valor
    elif campo == "visibilidade":
        visib = {"publico": "public", "público": "public", "nao-listado": "unlisted", "não-listado": "unlisted",
                 "privado": "private"}.get(valor.lower(), valor)
    editar.salvar_video(v["id"], titulo, descricao, tags, visib)
    return f"Feito: \"{v['titulo']}\" atualizado no YouTube."


def agendar(falado: str, data: str, hora: str) -> str:
    v = achar(falado)
    quando = editar.quando_de(data, hora)
    editar.agendar(v["id"], quando)
    return f"Agendado: \"{v['titulo']}\" sai {quando:%d/%m} às {quando:%H:%M}."


def desagendar(falado: str) -> str:
    v = achar(falado)
    editar.desagendar(v["id"])
    return f"\"{v['titulo']}\" saiu do agendamento e continua privado."


def lista_cards() -> str:
    cards = producao.listar()
    if not cards:
        return "A Produção está vazia."
    linhas = []
    for col in producao.COLUNAS:
        doc = [c for c in cards if c["coluna"] == col]
        if doc:
            linhas.append(f"{col.capitalize()}: " + "; ".join(
                f"{c['titulo']} (nº {c['id']}{', ' + c['jogo'] if c['jogo'] else ''}"
                f"{', dia ' + c['data'][8:10] + '/' + c['data'][5:7] if c['data'] else ''})" for c in doc))
    return "\n".join(linhas)


def nova_ideia(args: list[str]) -> str:
    extras = {k: v for k, v in (a.split("=", 1) for a in args if re.match(r"^(jogo|data)=", a))}
    titulo = " ".join(a for a in args if not re.match(r"^(jogo|data)=", a))
    campos = {"titulo": titulo, "jogo": extras.get("jogo", "")}
    if extras.get("data"):
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", extras["data"])
        if not m:
            raise ValueError("data no formato errado (use 14/11/2026)")
        campos["data"] = f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}"
    n = producao.criar(campos)
    return f"Ideia criada na Produção: \"{' '.join(titulo.split())}\" (nº {n})."


def mover(falado: str, coluna: str) -> str:
    coluna = _sem_acento(coluna)
    if coluna not in producao.COLUNAS:
        raise ValueError(f"etapa desconhecida: {coluna} (tem {', '.join(producao.COLUNAS)})")
    c = achar_card(falado)
    producao.mover(c["id"], coluna)
    return f"\"{c['titulo']}\" foi pra {coluna.capitalize()}."


def resumo_analises() -> str:
    a = analises.para_janela()
    if not a:
        return "Ainda não tem análises: falta conectar o YouTube ou a primeira atualização."
    partes = []
    if a.get("origens"):
        tot = sum(x["valor"] for x in a["origens"]) or 1
        partes.append("De onde vem o público: " + ", ".join(f"{x['nome']} {round(100 * x['valor'] / tot)}%" for x in a["origens"][:3]) + ".")
    if a.get("paises"):
        tot = sum(x["valor"] for x in a["paises"]) or 1
        partes.append("Países: " + ", ".join(f"{x['nome']} {round(100 * x['valor'] / tot)}%" for x in a["paises"][:3]) + ".")
    if a.get("idades"):
        top = max(a["idades"], key=lambda x: x["valor"])
        partes.append(f"A idade que mais assiste: {top['nome']} anos ({str(top['valor']).replace('.', ',')}%).")
    if a.get("aparelhos"):
        tot = sum(x["valor"] for x in a["aparelhos"]) or 1
        partes.append("Aparelhos: " + ", ".join(f"{x['nome']} {round(100 * x['valor'] / tot)}%" for x in a["aparelhos"][:3]) + ".")
    if a.get("top"):
        con = dados.abrir()
        nomes = []
        for t in a["top"][:3]:
            v = con.execute("SELECT titulo FROM videos WHERE id = ?", (t["video"],)).fetchone()
            nomes.append(f"\"{v['titulo'] if v else t['video']}\" ({dados._mil(t['views'])} views, +{t['inscritos']} inscritos)")
        con.close()
        partes.append("Os que mais trouxeram views nos 28 dias: " + "; ".join(nomes) + ".")
    return " ".join(partes) + " (Últimos 28 dias.)"


def rodar(a: list[str]) -> str | None:
    """None = não é um comando daqui."""
    c, r = (a[0], a[1:]) if a else ("", [])
    if c == "comentarios":
        return lista_comentarios(r[0] if r else "novos")
    if c == "responder" and len(r) >= 2:
        comentarios.responder(r[0], " ".join(r[1:]))
        return "Resposta publicada no YouTube."
    if c == "lido" and r:
        comentarios.marcar_lido(None if r[0] == "todos" else r)
        return "Marcado como lido."
    if c == "agendar" and len(r) >= 3:
        return agendar(" ".join(r[:-2]), r[-2], r[-1])
    if c == "desagendar" and r:
        return desagendar(" ".join(r))
    if c in ("titulo", "descricao", "visibilidade") and len(r) >= 2:
        # O vídeo é o primeiro argumento (use o id ou ponha o nome entre aspas).
        return editar_campo(r[0], c, " ".join(r[1:]))
    if c == "cards":
        return lista_cards()
    if c == "ideia" and r:
        return nova_ideia(r)
    if c == "mover" and len(r) >= 2:
        return mover(" ".join(r[:-1]), r[-1])
    if c == "analises":
        return resumo_analises()
    return None

