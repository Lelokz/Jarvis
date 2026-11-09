import sys

from jarvis import canal
from jarvis.canal import conta, dados


def main(a: list[str]) -> int:
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
        else:
            print(canal.__doc__)
            return 1
    except conta.SemConexao as e:
        print(f"Painel do Canal: {e}")
        return 1
    return 0


raise SystemExit(main(sys.argv[1:]))
