"""O backup mensal (09/11/2026): tranca com a chave pública, só abre com a
senha, junta as coisas certas (e deixa de fora as vozes), e restaura igual.
O relatório e o Drive são de mentira: nada sai do PC, nada gasta o Claude.
Tudo o que é juntado fica numa pasta temporária no HD e é apagado no fim.
"""
from __future__ import annotations

import datetime as dt
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from jarvis.monitor import backup  # noqa: E402

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
    hd = Path("/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/Arquivo/tmp-render")
    tmp = Path(tempfile.mkdtemp(prefix="testar-backup-", dir=hd if hd.is_dir() else None))
    try:
        print("-- trancar e abrir --")
        backup.criar_chaves("senha-de-teste", tmp / "chaves")
        pub = (tmp / "chaves/publica.key").read_bytes()
        trancada = (tmp / "chaves/chave-trancada.key").read_bytes()
        caixa = backup.trancar(b"o que o Jarvis sabe", pub)
        checa("o trancado não mostra o conteúdo", b"Jarvis" not in caixa)
        checa("abre com a senha certa", backup.abrir(caixa, trancada, "senha-de-teste") == b"o que o Jarvis sabe")
        for nome, args in (("senha errada não abre", (caixa, trancada, "outra")),
                           ("arquivo mexido não abre", (caixa[:-1] + bytes([caixa[-1] ^ 1]), trancada, "senha-de-teste"))):
            try:
                backup.abrir(*args)
                checa(nome, False)
            except ValueError:
                checa(nome, True)
        checa("a chave pública sozinha não tem a privada", len(pub) == 32)

        print("-- o que vai junto (as coisas de verdade, numa pasta temporária) --")
        destino = tmp / "junto"
        faltou = backup.juntar(destino)
        tem = lambda rel: (destino / rel).exists()  # noqa: E731
        checa("caderno do Jarvis", tem("NOVA/jarvis/casa/CLAUDE.md"))
        checa("memórias e memória viva", tem("NOVA/jarvis/memorias") and tem("NOVA/jarvis/memoria_viva.db"))
        checa("sessão do WhatsApp", tem("NOVA/whatsapp-ponte-store/whatsapp.db"))
        checa("senhas e chaves junto", tem("NOVA/jarvis/venice.env") and tem("Mint/casa/.ssh"))
        checa("as memórias do Claude Code", tem("Claude Code/memorias") and tem("Claude Code/.credentials.json"))
        checa("Cinnamon e lista de programas", (destino / "Mint/cinnamon-dconf.ini").stat().st_size > 1000
              and (destino / "Mint/programas-apt.txt").stat().st_size > 0)
        checa("as vozes treinadas ficam de fora", not tem("NOVA/jarvis/voz-jarvis") and not tem("NOVA/jarvis/voz-friday"))
        checa("sem os arquivos -wal soltos", not list(destino.rglob("*-wal")))
        tamanho = sum(f.stat().st_size for f in destino.rglob("*") if f.is_file())
        print(f"  (junto: {tamanho / 1024 ** 2:.0f} MB; faltou: {faltou or 'nada'})")
        checa("tamanho de backup (menos de 400 MB)", tamanho < 400 * 1024 ** 2, tamanho)

        print("-- o backup inteiro, sem Drive e sem Claude --")
        backup.PASTA, backup.PUBLICA = tmp / "chaves", tmp / "chaves/publica.key"
        backup.CHAVE_TRANCADA, backup.ESTADO = tmp / "chaves/chave-trancada.key", tmp / "backup.json"
        backup.escrever_relatorio = lambda mes: f"# Relatório - {mes}\n\nteste\n" + "x" * 600
        r = backup.fazer(mandar=False, hoje=dt.date(2026, 11, 9))
        checa("nome do arquivo", r.get("arquivo") == "Backup 2026-11 (novembro).nova", r)
        checa("deu certo e diz o tamanho", r.get("ok") and r.get("mb", 0) > 0, r)
        saida = backup.restaurar(Path(r["local"]), backup.CHAVE_TRANCADA, tmp / "restaurado", "senha-de-teste")
        pasta = saida / "Backup 2026-11 (novembro)"
        checa("restaura com o relatório e o COMO RESTAURAR",
              (pasta / "Relatório - Novembro 2026.md").exists() and (pasta / "COMO RESTAURAR.md").exists())
        checa("restaura o caderno igualzinho", (pasta / "NOVA/jarvis/casa/CLAUDE.md").read_bytes()
              == (backup.DADOS / "casa/CLAUDE.md").read_bytes())
        checa("bom dia conta", "Novembro 2026" in backup.relatorio())
        backup.marcar_contado()
        checa("e depois não repete", backup.relatorio() == "nada novo")

        print("-- ficam os 3 mais novos, contando o de agora --")
        nomes = [f"Backup 2026-{m:02d} (x).nova" for m in (8, 9, 10, 11)]
        apagados = []

        class R:
            def __init__(self, out=""):
                self.returncode, self.stdout, self.stderr = 0, out, ""

        def rclone(*a):
            if a[0] == "lsf":
                return R("\n".join(nomes + ["chave-trancada.key", "COMO RESTAURAR.md"]))
            if a[0] == "deletefile":
                apagados.append(a[1].split("/")[-1])
            return R()
        backup._rclone = rclone
        backup.enviar(Path(r["local"]))
        checa("apaga só o mais antigo", apagados == ["Backup 2026-08 (x).nova"], apagados)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
