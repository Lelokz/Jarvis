"""A faxina do SSD (08/11/2026).

    python -m jarvis.monitor.faxina                  mostra o que daria para limpar (não apaga nada)
    python -m jarvis.monitor.faxina --limpar         limpa (o que o timer roda de domingo pra segunda)
    python -m jarvis.monitor.faxina --remover-app ID [ID…]
                                                     desinstala flatpaks e tudo deles (dados, peças sem uso)
    python -m jarvis.monitor.faxina --relatorio      o resultado da última faxina, para o "bom dia"
    python -m jarvis.monitor.faxina --contado        marca o relatório como já contado

Quem roda o --limpar toda semana é o timer do systemd do usuário
(~/.config/systemd/user/jarvis-faxina.{service,timer}: segunda 00h + até 2 h,
Persistent=true). O "bom dia" do Jarvis conta o resultado (casa/CLAUDE.md).

O que ela limpa sozinha é só o que se recria sozinho (combinado com o Léo):
caches de programação, miniaturas, caches velhos de navegador que ele não usa,
e o que está na lixeira há mais de 30 dias. Apaga de vez: a lixeira fica no
próprio SSD, mandar para lá não liberaria nada (a regra da lixeira é do Jarvis
por voz, não daqui).

Nunca toca: coisas do Jarvis, Brave (cuida do próprio cache), os navegadores
do Playwright, Steam, Gradle (o build do app baixaria tudo de novo), projetos
e arquivos do Léo. Os Downloads grandes e velhos só entram numa lista.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CASA = Path.home()
RELATORIO = CASA / ".local/share/jarvis/faxina.json"
LIXEIRA = CASA / ".local/share/Trash"
DIAS_NA_LIXEIRA = 30
DOWNLOAD_GRANDE = 100 * 1024 ** 2    # bytes
DOWNLOAD_VELHO = 30                  # dias

# nome que aparece → pasta (o conteúdo vai embora; a pasta fica)
CACHES = {
    "cache do npm": CASA / ".npm/_cacache",
    "cache do Go": CASA / ".cache/go-build",
    "cache do pip": CASA / ".cache/pip",
    "miniaturas de imagens": CASA / ".cache/thumbnails",
    "cache do Firefox": CASA / ".cache/mozilla",
}


def _tamanho(caminho: Path) -> int:
    if caminho.is_symlink() or caminho.is_file():
        try:
            return caminho.lstat().st_size
        except OSError:
            return 0
    total = 0
    for raiz, pastas, arquivos in os.walk(caminho, onerror=lambda e: None):
        for a in arquivos:
            try:
                total += os.lstat(os.path.join(raiz, a)).st_size
            except OSError:
                pass
    return total


def _apagar(caminho: Path) -> None:
    if caminho.is_symlink() or caminho.is_file():
        caminho.unlink(missing_ok=True)
    else:
        shutil.rmtree(caminho, ignore_errors=True)


def _esvaziar(pasta: Path) -> None:
    """Apaga o conteúdo e deixa a pasta (o programa espera que ela exista)."""
    if not pasta.is_dir():
        return
    for item in pasta.iterdir():
        _apagar(item)


def _lixeira_velha() -> list[tuple[Path, Path]]:
    """(arquivo, .trashinfo) do que foi para a lixeira há mais de 30 dias."""
    limite = dt.datetime.now() - dt.timedelta(days=DIAS_NA_LIXEIRA)
    saida = []
    for info in (LIXEIRA / "info").glob("*.trashinfo"):
        try:
            for linha in info.read_text(errors="ignore").splitlines():
                if linha.startswith("DeletionDate="):
                    quando = dt.datetime.fromisoformat(linha.split("=", 1)[1].strip())
                    if quando < limite:
                        saida.append((LIXEIRA / "files" / info.name[:-len(".trashinfo")], info))
                    break
        except (OSError, ValueError):
            continue
    return saida


def downloads_velhos() -> list[dict]:
    limite = time.time() - DOWNLOAD_VELHO * 86400
    saida = []
    pasta = CASA / "Downloads"
    if not pasta.is_dir():
        return saida
    for item in pasta.iterdir():
        try:
            st = item.stat()
        except OSError:
            continue
        if st.st_mtime > limite:
            continue
        tamanho = _tamanho(item)
        if tamanho >= DOWNLOAD_GRANDE:
            saida.append({"nome": item.name, "mb": round(tamanho / 1e6),
                          "dias": int((time.time() - st.st_mtime) // 86400)})
    return sorted(saida, key=lambda d: -d["mb"])


def medir() -> list[dict]:
    """O que daria para limpar agora: [{nome, bytes}]."""
    itens = [{"nome": nome, "bytes": _tamanho(pasta)} for nome, pasta in CACHES.items() if pasta.is_dir()]
    velha = _lixeira_velha()
    if velha:
        itens.append({"nome": f"lixeira com mais de {DIAS_NA_LIXEIRA} dias ({len(velha)} itens)",
                      "bytes": sum(_tamanho(a) for a, _ in velha)})
    return [i for i in itens if i["bytes"] > 0]


def _livre() -> int:
    st = os.statvfs("/")
    return st.f_bavail * st.f_frsize


def _flatpak_sem_uso() -> None:
    """Peças de flatpak que nenhum app usa mais (sem senha para quem é do grupo sudo)."""
    if shutil.which("flatpak"):
        subprocess.run(["flatpak", "uninstall", "--unused", "-y", "--noninteractive"],
                       capture_output=True, timeout=600)


def limpar() -> dict:
    antes = _livre()
    itens = medir()
    for pasta in CACHES.values():
        _esvaziar(pasta)
    for arquivo, info in _lixeira_velha():
        _apagar(arquivo)
        info.unlink(missing_ok=True)
    _flatpak_sem_uso()
    resultado = {
        "quando": dt.datetime.now().isoformat(timespec="minutes"),
        "liberado_gb": round(max(0, _livre() - antes) / 1024 ** 3, 2),
        "itens": [{"nome": i["nome"], "mb": round(i["bytes"] / 1e6)} for i in itens],
        "downloads_velhos": downloads_velhos(),
        "livre_gb": round(_livre() / 1024 ** 3, 1),
        "contado": False,
    }
    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    RELATORIO.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    return resultado


def remover_app(ids: list[str]) -> dict:
    """Desinstala os flatpaks com os dados deles (~/.var/app) e as peças que sobrarem sem uso."""
    antes = _livre()
    feitos, falhas = [], []
    for app in ids:
        r = subprocess.run(["flatpak", "uninstall", "-y", "--noninteractive", "--delete-data", app],
                           capture_output=True, text=True, timeout=600)
        (feitos if r.returncode == 0 else falhas).append(app if r.returncode == 0
                                                         else f"{app}: {r.stderr.strip()[-200:]}")
        dados = CASA / ".var/app" / app
        if r.returncode == 0 and dados.exists():
            _apagar(dados)
    _flatpak_sem_uso()
    return {"removidos": feitos, "falhas": falhas,
            "liberado_gb": round(max(0, _livre() - antes) / 1024 ** 3, 2)}


def relatorio() -> str:
    try:
        r = json.loads(RELATORIO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "Nenhuma faxina feita ainda."
    linhas = [f'Faxina de {r["quando"]}: liberou {r["liberado_gb"]:.1f} GB '
              f'(SSD com {r["livre_gb"]:.0f} GB livres). Já contado ao Léo: {"sim" if r["contado"] else "não"}.']
    linhas += [f'- {i["nome"]}: {i["mb"]} MB' for i in r["itens"]]
    if r["downloads_velhos"]:
        linhas.append("Downloads grandes e velhos (NÃO apagados, só mostrar se ele quiser):")
        linhas += [f'- {d["nome"]}: {d["mb"]} MB, {d["dias"]} dias' for d in r["downloads_velhos"]]
    return "\n".join(linhas)


def marcar_contado() -> None:
    try:
        r = json.loads(RELATORIO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    r["contado"] = True
    RELATORIO.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


def main(args: list[str]) -> int:
    if args[:1] == ["--limpar"]:
        r = limpar()
        print(f'liberou {r["liberado_gb"]} GB; SSD com {r["livre_gb"]} GB livres')
    elif args[:1] == ["--remover-app"] and args[1:]:
        print(json.dumps(remover_app(args[1:]), ensure_ascii=False))
    elif args[:1] == ["--relatorio"]:
        print(relatorio())
    elif args[:1] == ["--contado"]:
        marcar_contado()
    else:
        itens = medir()
        for i in itens:
            print(f'{i["nome"]}: {i["bytes"] / 1e6:.0f} MB')
        print(f'total: {sum(i["bytes"] for i in itens) / 1e9:.1f} GB')
        for d in downloads_velhos():
            print(f'(download velho, não apaga) {d["nome"]}: {d["mb"]} MB, {d["dias"]} dias')
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
