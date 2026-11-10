import os
import sys
import tempfile


def main(a: list[str]) -> int:
    # "retrato-exemplo": dados inventados numa pasta temporária (antes de importar o resto).
    if a[:1] == ["retrato-exemplo"]:
        os.environ["JARVIS_DADOS"] = tempfile.mkdtemp(prefix="painel-exemplo-")
    from jarvis import youtube as canal
    from jarvis.youtube import conta, dados
    try:
        if a[:1] == ["conectar"]:
            print(conta.conectar())
            print(dados.sincronizar())
        elif a[:1] == ["sincronizar"]:
            if not conta.conectado():
                return 0  # o timer roda antes de o Léo conectar: quieto
            print(dados.sincronizar())
        elif a[:1] == ["resumo"]:
            print(dados.resumo())
        elif a[:1] == ["video"] and len(a) > 1:
            print(dados.sobre_video(" ".join(a[1:])))
        elif a[:1] == ["janela"]:
            from jarvis.youtube import janela
            return janela.abrir()
        elif a[:1] in (["retrato"], ["retrato-exemplo"]) and len(a) > 1:
            from pathlib import Path
            from jarvis.youtube import janela
            if a[0] == "retrato-exemplo":
                from jarvis.youtube import exemplo
                fonte = next((Path(janela.FONTES).glob("Inter*.ttf")), None)
                exemplo.criar(fonte)
            return janela.abrir(retrato=a[1], aba=a[2] if len(a) > 2 else "inicio", ficha=a[3] if len(a) > 3 else "")
        else:
            from jarvis.youtube import comandos, editar
            try:
                saida = comandos.rodar(a)
            except (editar.Recusado, ValueError) as e:
                print(f"Não deu: {e}.")
                return 1
            if saida is None:
                print(canal.__doc__)
                print(comandos.__doc__)
                return 1
            print(saida)
    except conta.SemConexao as e:
        print(f"Painel do Canal: {e}")
        return 1
    return 0


raise SystemExit(main(sys.argv[1:]))
