"""A etapa 3 do tchan (11/11/2026): o modo code refeito. O Desfazer (a foto
dos arquivos antes de cada resposta, o cartão e o voltar), o "Desfazer
arquivo" contra o commit, o botão "quanto ele faz sozinho" (as travas de cada
modo), as frases faladas, o Terminal e o Plano. Sem Claude e sem microfone.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from jarvis.agente import agente as ag, desfazer  # noqa: E402
from jarvis.agente.reflexos import comando_code_extra  # noqa: E402
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


def lp(d):
    return ler_pedido(json.dumps(d).encode())


def main() -> int:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        proj, pasta = tmp / "Loft", tmp / "desfazer"
        proj.mkdir()
        (proj / "login.js").write_text("a\nb\nc\n")
        (proj / "velho.txt").write_text("fica\n")

        print("-- o Desfazer --")
        turno = desfazer.Turno(proj, pasta)
        turno.guardar(str(proj / "login.js"))
        turno.guardar(str(proj / "novo.js"))
        turno.guardar("velho.txt")                 # relativo também vale
        turno.guardar("/etc/hostname")             # fora do projeto: ignora
        (proj / "login.js").write_text("a\nB\nc\nd\n")
        turno.guardar(str(proj / "login.js"))      # a 2ª mexida não troca o "antes"
        (proj / "login.js").write_text("a\nB\nc\nd\ne\n")
        (proj / "novo.js").write_text("1\n2\n")
        r = turno.fechar("sessao-1")
        arqs = {a["arquivo"]: a for a in r["arquivos"]}
        checa("só o que mudou de verdade entra no cartão", sorted(arqs) == ["login.js", "novo.js"], arqs)
        checa("+/− de cada arquivo", (arqs["login.js"]["mais"], arqs["login.js"]["menos"]) == (3, 1)
              and arqs["novo.js"]["estado"] == "novo" and arqs["novo.js"]["mais"] == 2, arqs)
        checa("o total do cartão", (r["mais"], r["menos"]) == (5, 1), r)
        checa("o turno começa limpo depois", turno.fechar() is None)
        checa("a última mudança do projeto", desfazer.ultima(proj, pasta)["id"] == r["id"])

        (proj / "outro.txt").write_text("não é desta resposta\n")
        lixo = []
        desfazer._lixeira, antes_lixeira = (lambda c: (lixo.append(c), c.unlink())), desfazer._lixeira
        try:
            d = desfazer.desfazer(r["id"], "login.js", pasta)
            checa("desfazer um arquivo só", (proj / "login.js").read_text() == "a\nb\nc\n"
                  and (proj / "novo.js").exists() and d["desfeito"] == ["login.js"], d)
            d = desfazer.desfazer(r["id"], "", pasta)
            checa("desfazer o resto: o arquivo novo vai pra lixeira", not (proj / "novo.js").exists()
                  and lixo == [proj / "novo.js"] and sorted(d["desfeito"]) == ["login.js", "novo.js"], d)
            checa("o resto do projeto não muda", (proj / "outro.txt").exists() and (proj / "velho.txt").read_text() == "fica\n")
            try:
                desfazer.desfazer(r["id"], "", pasta)
                checa("desfazer de novo avisa", False)
            except ValueError as e:
                checa("desfazer de novo avisa", "já estava" in str(e))
            checa("sem mudança pendente: nenhuma 'última'", desfazer.ultima(proj, pasta) is None)
            checa("id esquisito não abre arquivo", desfazer.abrir("../x", pasta) is None)

            print("-- o Desfazer arquivo (contra o commit) --")
            g = lambda *a: subprocess.run(["git", "-C", str(proj), *a], capture_output=True, check=True)
            g("init", "-q"); g("add", "-A"); g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x")
            (proj / "login.js").write_text("mexido\n")
            (proj / "solto.js").write_text("sem commit\n")
            copia = desfazer.desfazer_git(proj, "login.js", pasta)
            checa("volta ao último commit e guarda a cópia", (proj / "login.js").read_text() == "a\nb\nc\n"
                  and Path(copia).read_text() == "mexido\n")
            desfazer.desfazer_git(proj, "solto.js", pasta)
            checa("arquivo sem commit vai pra lixeira", not (proj / "solto.js").exists() and lixo[-1] == proj / "solto.js")
            try:
                desfazer.desfazer_git(proj, "../fora.txt", pasta)
                checa("recusa arquivo fora do projeto", False)
            except ValueError:
                checa("recusa arquivo fora do projeto", True)
        finally:
            desfazer._lixeira = antes_lixeira

        print("-- quanto ele faz sozinho --")
        a = ag.Agente.__new__(ag.Agente)
        a.code = types.SimpleNamespace(caminho=proj, nome="Loft")
        a._turno, a._plano_ok, a.saidas = None, False, __import__("queue").Queue()
        perguntas = []

        async def perguntar(texto, opcoes):
            perguntas.append(texto)
            return resposta[0]
        a._perguntar = perguntar
        resposta = ["pode"]
        modo = ["auto"]
        ag.permissao_code, antes_perm = (lambda: modo[0]), ag.permissao_code
        try:
            regra = lambda n, e: asyncio.run(a._regra_code(n, e))
            nega = lambda r: r.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
            edit = {"file_path": str(proj / "login.js")}
            checa("Automático: deixa mexer e guarda o antes", regra("Edit", edit) == {} and "login.js" in a._turno.antes)
            modo[0] = "olhar"
            checa("Só olhar: barra Edit", nega(regra("Edit", edit)))
            checa("Só olhar: barra comando que muda", nega(regra("Bash", {"command": "npm install"}))
                  and nega(regra("Bash", {"command": "cat a > b"})) and nega(regra("Bash", {"command": "rm x"})))
            checa("Só olhar: deixa comando que só lê", regra("Bash", {"command": "cd /x && git status && ls | head"}) == {}
                  and regra("Read", edit) == {})
            modo[0] = "plano"
            checa("Plano primeiro: barra antes do pode", nega(regra("Write", edit)))
            a._plano_ok = True
            checa("Plano primeiro: deixa depois do pode", regra("Write", edit) == {})
            modo[0] = "perguntar"
            checa("Perguntar antes: pergunta pelo nome do arquivo", regra("Edit", edit) == {} and perguntas[-1] == "Posso mudar o login.js?")
            resposta[0] = "não"
            checa("Perguntar antes: o não barra", nega(regra("Edit", edit)))
            checa("Perguntar antes: comando não pergunta", regra("Bash", {"command": "npm test"}) == {} and len(perguntas) == 2)
        finally:
            ag.permissao_code = antes_perm

        print("-- Terminal e Plano --")
        Bloco = lambda nome, ent, i="t1": types.SimpleNamespace(name=nome, input=ent, id=i)
        a._bash, a._tarefas = {}, []
        a._painel_code(Bloco("Bash", {"command": "npm test"}))
        s = a.saidas.get_nowait()
        checa("o comando vai pro Terminal", s.tipo == "terminal" and json.loads(s.texto)["cmd"] == "npm test" and a._bash == {"t1": "npm test"})
        a._painel_code(Bloco("TodoWrite", {"todos": [{"content": "Criar a tela", "status": "completed"},
                                                     {"content": "Testes", "status": "in_progress"}]}))
        s = a.saidas.get_nowait()
        checa("o TodoWrite vira o Plano", s.tipo == "plano" and json.loads(s.texto) ==
              [{"texto": "Criar a tela", "estado": "completed"}, {"texto": "Testes", "estado": "in_progress"}])
        a._tarefas = []
        a._painel_code(Bloco("TaskCreate", {"subject": "Validar"}))
        a._tarefas[-1]["id"] = "1"
        a._painel_code(Bloco("TaskUpdate", {"taskId": "1", "status": "completed"}))
        while not a.saidas.empty():
            s = a.saidas.get_nowait()
        checa("TaskCreate/TaskUpdate também", json.loads(s.texto)[0]["estado"] == "completed")

    print("-- as frases --")
    casos = [("Desfaz isso.", ("desfazer", "")), ("Jarvis, desfaz o que você fez", ("desfazer", "")),
             ("Modo plano", ("permissao", "plano")), ("Me pergunta antes.", ("permissao", "perguntar")),
             ("Pode fazer sozinho", ("permissao", "auto")), ("Friday, só olhar.", ("permissao", "olhar")),
             ("desfaz a cama", None), ("qual o plano?", None)]
    for frase, esperado in casos:
        checa(repr(frase), comando_code_extra(frase) == esperado, comando_code_extra(frase))

    print("-- o protocolo --")
    checa("desfazer", lp({"pedir": "desfazer", "id": "abc123"}) == ("desfazer", {"id": "abc123", "arquivo": ""}))
    checa("desfazer_git", lp({"pedir": "desfazer_git", "caminho": "/x", "arquivo": "a.js"})[1] == {"caminho": "/x", "arquivo": "a.js"})
    checa("permissão nos ajustes", lp({"pedir": "ajustes", "code_permissao": "plano"})[1] == {"code_permissao": "plano"})
    checa("quem atende quando liga, nos ajustes", lp({"pedir": "ajustes", "persona_inicial": "friday"})[1] == {"persona_inicial": "friday"})
    import porta_remota
    checa("o celular pode mudar quem atende quando liga", "persona_inicial" in Path(porta_remota.__file__).read_text())
    for ruim in ({"pedir": "desfazer", "id": "../x"}, {"pedir": "desfazer_git", "caminho": "/x"},
                 {"pedir": "ajustes", "code_permissao": "tudo"}, {"pedir": "ajustes", "persona_inicial": "lucas"}):
        try:
            lp(ruim)
            checa(f"recusa {ruim}", False)
        except ErroDeProtocolo:
            checa(f"recusa {ruim}", True)

    print(f"\n{ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
