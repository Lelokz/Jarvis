"""O modo code (10/11/2026): programar com o Jarvis pela voz, dentro de um
projeto. As frases de entrar/trocar/sair, achar o projeto pelo nome falado,
a conversa de cada projeto, as instruções, a trava do projeto da NOVA, a
janela maior e o filtro "só a voz do Léo". Sem Claude e sem microfone.
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import types
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import assistente  # noqa: E402
from jarvis.agente import agente as ag, projetos  # noqa: E402
from jarvis.agente.reflexos import comando_code  # noqa: E402

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
    print("-- as frases --")
    casos = [("Jarvis, modo code no Loft.", False, ("entrar", "loft")),
             ("Entra no modo código do Rocket League", False, ("entrar", "rocket league")),
             ("Abre o modo code pro projeto terror", False, ("entrar", "terror")),
             ("Modo cold no Loft", False, ("entrar", "loft")),
             ("Sai do modo code.", True, ("sair", "")),
             ("Fecha o modo código.", True, ("sair", "")),
             ("Troca pro City Empire", True, ("trocar", "city empire")),
             ("Troca pro City Empire", False, None),
             ("o que é modo code?", False, None),
             ("abre o VS Code", False, None)]
    for frase, em_code, esperado in casos:
        checa(f"{frase!r} (em code: {em_code})", comando_code(frase, em_code) == esperado, comando_code(frase, em_code))

    print("-- os projetos --")
    nomes = [p.nome for p in projetos.listar()]
    checa("o projeto da NOVA fica fora da lista", "Jarvis" not in nomes, nomes)
    checa("acha Loft, Rocket League e Terror pelo nome falado",
          [p.nome for p in projetos.achar("loft")] == ["Loft"]
          and [p.nome for p in projetos.achar("rocket league")] == ["Projeto Rocket League"]
          and [p.nome for p in projetos.achar("o terror")] == ["Projeto Terror"])
    checa("\"city empire\" é o City Empire, não o Unity", [p.nome for p in projetos.achar("city empire")] == ["City Empire"])
    checa("\"jarvis\" e \"nova\" são o da NOVA", projetos.eh_o_da_nova("o jarvis") and projetos.eh_o_da_nova("a nova"))
    checa("nome que não existe", projetos.achar("culinária") == [])

    tmp = Path(tempfile.mkdtemp(prefix="modo-code-"))
    (tmp / "src").mkdir()
    for n in ("PainelCanal.qml", "producao.py", "loft.spec.ts", "__init__.py"):
        (tmp / "src" / n).write_text("x")
    (tmp / "node_modules").mkdir()
    (tmp / "node_modules" / "lixo.js").write_text("x")
    voc = projetos.vocabulario(projetos.Projeto("Teste", tmp))
    checa("vocabulário: nome do projeto e arquivos de código", voc[0] == "Teste" and {"PainelCanal", "producao"} <= set(voc), voc)
    checa("vocabulário sem gerado, teste nem node_modules", not {"loft.spec", "__init__", "lixo"} & set(voc), voc)

    print("-- o agente --")
    a = ag.Agente.__new__(ag.Agente)
    a.casa = tmp / "casa"
    a.casa.mkdir()
    a.code = None
    a.narracao = "normal"
    a.sessao = "voz-1"
    a._sessao_voz = None
    a._arquivo_code = tmp / "code-sessoes.json"
    a.saidas = __import__("queue").Queue()
    a._trava = None
    abertas = []

    async def desconectar():
        pass

    async def conectar(retomar=None):
        a.sessao = retomar or f"nova-{len(abertas)}"
        abertas.append((a.code.nome if a.code else None, retomar))
    a._desconectar, a._conectar = desconectar, conectar
    a._falhou = lambda e: (_ for _ in ()).throw(e)
    loft = projetos.Projeto("Loft", tmp / "loft")
    rl = projetos.Projeto("Projeto Rocket League", tmp / "rl")
    asyncio.run(a._trocar_code(loft))
    checa("entrou no Loft com conversa nova", a.code == loft and abertas[-1] == ("Loft", None))
    checa("guardou a conversa de voz pra voltar", a._sessao_voz == "voz-1")
    asyncio.run(a._trocar_code(rl))
    asyncio.run(a._trocar_code(loft))
    checa("voltar pro Loft retoma a MESMA conversa dele", abertas[-1] == ("Loft", "nova-0"), abertas)
    asyncio.run(a._trocar_code(None))
    checa("sair volta pra conversa de voz", a.code is None and abertas[-1] == (None, "voz-1"), abertas)
    checa("as conversas por projeto ficam guardadas", json.loads(a._arquivo_code.read_text())[str(loft.caminho)] == "nova-0")
    try:
        a.entrar_code(projetos.Projeto("Jarvis", projetos.PROIBIDO))
        checa("recusa entrar no projeto da NOVA", False)
    except ValueError:
        checa("recusa entrar no projeto da NOVA", True)

    a.code = loft
    instr = a._instrucoes_code()
    checa("instruções falam do projeto e da voz", "MODO CODE" in instr and "**Loft**" in instr
          and "NUNCA leia código" in instr and "Plano + OK" in instr and "{" not in instr.replace("```", ""))
    a.narracao = "pouca"
    checa("a narração escolhida entra", "pouca narração" in a._instrucoes_code())
    jarvis = str(projetos.PROIBIDO)
    checa("trava: editar arquivo da NOVA", a._mexe_na_nova("Edit", {"file_path": f"{jarvis}/assistente.py"}))
    checa("trava: escrever arquivo da NOVA", a._mexe_na_nova("Write", {"file_path": f"{jarvis}/x.md"}))
    checa("trava: rm no projeto da NOVA", a._mexe_na_nova("Bash", {"command": "rm -rf ~/Projetos/Jarvis/jarvis"}))
    checa("trava: git commit na NOVA", a._mexe_na_nova("Bash", {"command": "cd ~/Projetos/Jarvis && git commit -m x"}))
    checa("pode: tirar print pela NOVA (só lê)", not a._mexe_na_nova(
        "Bash", {"command": "cd ~/Projetos/Jarvis && .venv/bin/python -m jarvis.nucleo.olhar"}))
    checa("pode: editar o próprio projeto", not a._mexe_na_nova("Edit", {"file_path": str(tmp / "loft" / "a.py")}))
    a.code = None
    checa("fora do modo code a trava nova não age", a._instrucoes_code() == "")

    print("-- o ciclo de voz --")
    c = assistente.Ciclo.__new__(assistente.Ciclo)
    falas, renovou, registros = [], [], []
    c._falar = lambda texto, **kw: falas.append(texto)
    c._renovar = lambda rotulo: renovou.append(rotulo)
    c._mudar_estado = lambda e: None
    c.registrador = types.SimpleNamespace(registrar_estado=lambda *a, **kw: registros.append(a[0]))
    c.cfg = types.SimpleNamespace(raiz=RAIZ, ciclo=types.SimpleNamespace(janela_s=30.0))
    vocab = []
    c.transcritor = types.SimpleNamespace(usar_vocabulario=lambda n: vocab.append(list(n)))
    entrou = []
    c.agente = types.SimpleNamespace(code=None, ocupado=False, entrar_code=lambda p: entrou.append(p))
    checa("janela normal fora do modo code", c._janela_s() == 30.0)
    checa("entra pelo nome falado", c._modo_code(("entrar", "rocket league"), "x") and entrou[-1].nome == "Projeto Rocket League"
          and falas[-1] == "Modo code no Rocket League. Pode falar.", falas)
    checa("o Whisper ganha os nomes do projeto", "Projeto Rocket League" in vocab[-1] and "modo code" in vocab[-1])
    c.agente.code = entrou[-1]
    checa("janela maior no modo code (2 min)", c._janela_s() == 120.0)
    checa("\"troca a música\" não é projeto: segue pro Claude", c._modo_code(("trocar", "musica"), "troca a música") is False)
    n = len(entrou)
    c._modo_code(("entrar", "jarvis"), "x")
    checa("recusa o projeto da NOVA falando o porquê", len(entrou) == n and "NOVA eu não mexo" in falas[-1])
    c._modo_code(("entrar", "culinaria"), "x")
    checa("projeto que não existe: diz os que tem", falas[-1].startswith("Não achei esse projeto. Tenho:") and "Loft" in falas[-1])
    c.agente.ocupado = True
    c._modo_code(("sair", ""), "x")
    checa("no meio de uma tarefa não troca", "meio de uma coisa" in falas[-1])
    c.agente.ocupado = False
    c._modo_code(("sair", ""), "x")
    checa("sair", entrou[-1] is None and falas[-1] == "Saí do modo code.")

    print("-- só a voz do Léo no modo code --")
    from jarvis.quem_fala import Voz
    c.agente = types.SimpleNamespace(code=loft, ocupado=False)
    c.emissor = types.SimpleNamespace(emitir=lambda *a, **k: None)
    pedidos = []
    c.agente.pedir = lambda *a, **k: pedidos.append(a)
    c._pergunta = None
    c._responder("apaga o arquivo de login", origem="voz", voz=Voz("outra", 0.2, 3.0))
    checa("outra voz é ignorada (nem chega ao Claude)", pedidos == [] and registros[-1] == "code_outra_voz_ignorada", registros[-3:])

    print("-- a janela: protocolo, ajustes e as mudanças --")
    from jarvis import ajustes
    from jarvis.agente import git_code
    from jarvis.ponte import protocolo
    import subprocess
    lp = lambda o: protocolo.ler_pedido(json.dumps(o).encode())  # noqa: E731
    checa("pedir a lista de projetos", lp({"pedir": "projetos"}) == ("projetos", {}))
    checa("entrar e sair pelo caminho", lp({"pedir": "code", "caminho": "/x/Loft"}) == ("code", {"caminho": "/x/Loft"})
          and lp({"pedir": "code", "caminho": ""}) == ("code", {"caminho": ""}))
    checa("botões commit e push", lp({"pedir": "git", "acao": "push"}) == ("git", {"acao": "push"}))
    for nome, o in (("git com ação errada", {"pedir": "git", "acao": "reset"}),
                    ("mudanças sem caminho", {"pedir": "mudancas"}),
                    ("narração inválida", {"pedir": "ajustes", "code_narracao": "gritando"}),
                    ("microfone de 7 s", {"pedir": "ajustes", "code_janela_s": 7})):
        try:
            lp(o)
            checa(f"recusa {nome}", False)
        except protocolo.ErroDeProtocolo:
            checa(f"recusa {nome}", True)
    checa("ajustes do modo code passam", lp({"pedir": "ajustes", "code_narracao": "pouca", "code_janela_s": 180,
                                              "code_persona": "friday"})[1] == {"code_narracao": "pouca", "code_janela_s": 180,
                                                                                 "code_persona": "friday"})
    ajustes.ARQUIVO = tmp / "ajustes.json"
    checa("padrões: normal, 2 min, quem estiver", (ajustes.ler()["code_narracao"], ajustes.ler()["code_janela_s"],
                                                     ajustes.ler()["code_persona"]) == ("normal", 120, "atual"))
    ajustes.mudar(code_janela_s=300, code_narracao="muita")
    checa("guarda a escolha", ajustes.ler()["code_janela_s"] == 300 and ajustes.ler()["code_narracao"] == "muita")
    c.agente = types.SimpleNamespace(code=loft)
    assistente.ajustes.ARQUIVO = ajustes.ARQUIVO
    checa("o microfone aberto segue o ajuste (5 min)", c._janela_s() == 300.0)

    repo = tmp / "repo"
    repo.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True)  # noqa: E731
    g("init", "-q"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
    (repo / "a.py").write_text("um\ndois\n")
    g("add", "."); g("commit", "-qm", "x")
    (repo / "a.py").write_text("um\nDOIS\ntres\n")
    (repo / "novo.py").write_text("oi\n")
    m = git_code.mudancas(repo)
    arq = {x["arquivo"]: x for x in m["arquivos"]}
    checa("mudanças: o arquivo mexido com + e −", arq.get("a.py", {}).get("mais") == 2 and arq["a.py"]["menos"] == 1, m["arquivos"])
    checa("mudanças: o arquivo novo", arq.get("novo.py", {}).get("estado") == "novo" and arq["novo.py"]["mais"] == 1)
    checa("o diff tem os dois", "-dois" in m["diff"] and "+DOIS" in m["diff"] and "+oi" in m["diff"])
    checa("sem remoto, sem push", m["remoto"] is False and m["a_frente"] == 0)
    checa("pasta sem git", git_code.mudancas(tmp / "casa")["git"] is False)
    d = git_code.diff_da_ferramenta("Edit", {"old_string": "a\nb", "new_string": "c"})
    checa("antes/depois do Edit em ```diff", d == "```diff\n-a\n-b\n+c\n```", d)
    checa("ferramenta que não edita não mostra diff", git_code.diff_da_ferramenta("Read", {}) is None)

    print("-- projeto novo --")
    checa("frase: cria um projeto novo chamado X", comando_code("Jarvis, cria um projeto novo chamado Jogo da Cobrinha.", False)
          == ("novo", "Jogo da Cobrinha"))
    checa("frase: modo code num projeto novo", comando_code("Friday, modo code num projeto novo chamado Pressure", True)
          == ("novo", "Pressure"))
    checa("frase sem nome", comando_code("cria um projeto novo", False) == ("novo", ""))
    checa("nome vira pasta limpa", projetos.limpar_nome("  ônibus   sc!!/../ ") == "Ônibus sc")
    hd_antes, novos_antes = projetos.HD, projetos.NOVOS
    projetos.HD, projetos.NOVOS = tmp, tmp / "Projetos"
    try:
        novo = projetos.criar("calculadora de notas")
        checa("cria a pasta em Projetos do HD, com git", novo.caminho == tmp / "Projetos" / "Calculadora de notas"
              and (novo.caminho / ".git").is_dir())
        checa("e ela entra na lista do modo code", "Calculadora de notas" in [p.nome for p in projetos.listar()])
        for nome, n in (("repetido", "Calculadora de Notas"), ("vazio", "!!!"), ("da NOVA", "Nova")):
            try:
                projetos.criar(n)
                checa(f"recusa nome {nome}", False)
            except projetos.NomeRuim:
                checa(f"recusa nome {nome}", True)
        falas.clear()
        c.agente = types.SimpleNamespace(code=None, ocupado=False, entrar_code=lambda p: entrou.append(p))
        c._modo_code(("novo", "Jogo da Cobrinha"), "x")
        checa("pela voz: cria, entra e pergunta do que é", entrou[-1].nome == "Jogo da Cobrinha"
              and falas[-1] == "Criei o projeto Jogo da Cobrinha no HD e entrei no modo code. Do que vai ser?", falas)
        c._modo_code(("novo", ""), "x")
        checa("sem nome: pede o nome", falas[-1].startswith("Qual o nome?"))
        c._modo_code(("novo", "Outro"), "x", Voz("outra", 0.1, 3.0))
        checa("outra voz não cria projeto", falas[-1] == "Projeto novo só o dono pede." and not (tmp / "Projetos" / "Outro").exists())
        checa("pela janela: não fala, devolve o motivo se não deu", c.criar_projeto("Jogo da Cobrinha", falar=False).startswith("já existe"))
    finally:
        projetos.HD, projetos.NOVOS = hd_antes, novos_antes
    checa("pedido da janela", lp({"pedir": "novo_projeto", "nome": " Pressure "}) == ("novo_projeto", {"nome": "Pressure"}))

    print(f"\n{ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
