"""O backup mensal da NOVA (09/11/2026, pedido do Léo).

Guarda no Google Drive só o que é DELE e não está no GitHub: o que o Jarvis
e a Friday sabem dele (caderno, memórias, memória viva, grupos), as minhas
memórias do Claude Code, as configurações do Mint e as senhas e chaves. Nada
de jogo, foto, vídeo, gravação ou o que dá para baixar de novo (as vozes
treinadas já estão no Drive, no "NOVA - Pacote de vozes").

Antes de empacotar, a NOVA escreve o "Relatório - <mês>.md": tudo o que está
anotado sobre o Léo, o PC e a NOVA, escrito para ele E para o Jarvis/Friday
lerem depois de uma formatação.

TRANCADO com uma senha que só o Léo sabe, sem a senha ficar no PC:
- o PC guarda só a chave PÚBLICA (tranca, não abre);
- a chave que abre vai para o Drive trancada com a senha dele (scrypt);
- cada backup: X25519 + AES-256-GCM (a biblioteca `cryptography`).

    python -m jarvis.monitor.backup --criar-senha     uma vez: o Léo escolhe a senha
    python -m jarvis.monitor.backup --agora           faz o backup (o que o timer roda todo dia 1º)
    python -m jarvis.monitor.backup --local           faz tudo menos mandar pro Drive (teste)
    python -m jarvis.monitor.backup --restaurar ARQUIVO.nova CHAVE.key DESTINO
    python -m jarvis.monitor.backup --relatorio | --contado    para o "bom dia"

Pro Drive vai pelo rclone (remoto "drive", pasta "NOVA - Backup"), que só
enxerga o que ele mesmo criou. Ficam os 3 últimos meses.
"""

from __future__ import annotations

import datetime as dt
import getpass
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

CASA = Path.home()
DADOS = CASA / ".local/share/jarvis"
PASTA = DADOS / "backup"
PUBLICA = PASTA / "publica.key"
CHAVE_TRANCADA = PASTA / "chave-trancada.key"
ESTADO = DADOS / "backup.json"
PROJETO = Path(__file__).resolve().parents[2]
COMO_RESTAURAR = PROJETO / "docs" / "COMO RESTAURAR.md"
_HD_TMP = Path("/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/Arquivo/tmp-render")
REMOTO = "drive:NOVA - Backup"
MANTER = 3
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]

MAGICA_BACKUP = b"NOVA-BACKUP-1\n"
MAGICA_CHAVE = b"NOVA-CHAVE-1\n"

# Da pasta do Jarvis, o que NÃO vai (grande e baixável de novo, ou lixo).
FORA_DO_JARVIS = {"voz-jarvis", "voz-friday", "escola-navegador", "recebidos", "whatsapp-mcp",
                  "whatsapp-bridge.log", "backup"}
GRANDE = 20 * 1024 ** 2  # arquivo solto maior que isso nos programas/atalhos: só o nome


# -- trancar e abrir ---------------------------------------------------------------

def _derivar(segredo: bytes, sal: bytes = b"") -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=sal or None, info=b"nova-backup").derive(segredo)


def _da_senha(senha: str, sal: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    return Scrypt(salt=sal, length=32, n=2 ** 17, r=8, p=1).derive(senha.encode("utf-8"))


def criar_chaves(senha: str, pasta: Path = PASTA) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    privada = X25519PrivateKey.generate()
    crua = privada.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                 serialization.NoEncryption())
    publica = privada.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    sal, nonce = os.urandom(16), os.urandom(12)
    trancada = MAGICA_CHAVE + sal + nonce + AESGCM(_da_senha(senha, sal)).encrypt(nonce, crua + publica, None)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / PUBLICA.name).write_bytes(publica)
    (pasta / CHAVE_TRANCADA.name).write_bytes(trancada)


def trancar(dados: bytes, publica: bytes) -> bytes:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    efemera = X25519PrivateKey.generate()
    pub_efemera = efemera.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    chave = _derivar(efemera.exchange(X25519PublicKey.from_public_bytes(publica)), pub_efemera + publica)
    nonce = os.urandom(12)
    return MAGICA_BACKUP + pub_efemera + nonce + AESGCM(chave).encrypt(nonce, dados, None)


def abrir(trancado: bytes, chave_trancada: bytes, senha: str) -> bytes:
    """Senha errada ou arquivo estragado: ValueError."""
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not chave_trancada.startswith(MAGICA_CHAVE) or not trancado.startswith(MAGICA_BACKUP):
        raise ValueError("isso não é um backup ou uma chave da NOVA")
    k = chave_trancada[len(MAGICA_CHAVE):]
    try:
        crua = AESGCM(_da_senha(senha, k[:16])).decrypt(k[16:28], k[28:], None)
    except InvalidTag:
        raise ValueError("senha errada") from None
    privada, publica = X25519PrivateKey.from_private_bytes(crua[:32]), crua[32:]
    b = trancado[len(MAGICA_BACKUP):]
    pub_efemera, nonce = b[:32], b[32:44]
    chave = _derivar(privada.exchange(X25519PublicKey.from_public_bytes(pub_efemera)), pub_efemera + publica)
    try:
        return AESGCM(chave).decrypt(nonce, b[44:], None)
    except InvalidTag:
        raise ValueError("o arquivo do backup está estragado") from None


# -- juntar o que vai -------------------------------------------------------------------

def _rodar(*cmd: str) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return r.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _copiar(origem: Path, destino: Path) -> None:
    """Copia arquivo ou pasta. Banco sqlite vai pela cópia segura do próprio
    sqlite (o Jarvis e a ponte gravam neles o tempo todo)."""
    if origem.is_symlink() or not origem.exists():
        return
    if origem.is_dir():
        for filho in origem.iterdir():
            _copiar(filho, destino / filho.name)
        return
    if origem.name.endswith(("-wal", "-shm", "-journal")):
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origem.suffix == ".db":
        try:
            fonte = sqlite3.connect(f"file:{origem}?mode=ro", uri=True, timeout=30)
            alvo = sqlite3.connect(destino)
            with alvo:
                fonte.backup(alvo)
            fonte.close()
            alvo.close()
            return
        except sqlite3.Error:
            pass
    shutil.copy2(origem, destino)


def juntar(destino: Path) -> list[str]:
    """Copia tudo o que vai para `destino`. Devolve o que faltou (avisos)."""
    faltou: list[str] = []
    nova = destino / "NOVA"
    for item in sorted(DADOS.iterdir()) if DADOS.is_dir() else []:
        if item.name not in FORA_DO_JARVIS:
            _copiar(item, nova / "jarvis" / item.name)
    _copiar(DADOS / "whatsapp-mcp/whatsapp-bridge/store", nova / "whatsapp-ponte-store")

    claude = destino / "Claude Code"
    for mem in sorted((CASA / ".claude/projects").glob("*/memory")):
        if any(mem.iterdir()):
            _copiar(mem, claude / "memorias" / mem.parent.name)
    for nome in ("skills", "settings.json", "CLAUDE.md", ".credentials.json"):
        _copiar(CASA / ".claude" / nome, claude / nome)
    _copiar(CASA / ".claude.json", claude / "claude.json")

    mint = destino / "Mint"
    (mint).mkdir(parents=True, exist_ok=True)
    (mint / "cinnamon-dconf.ini").write_text(_rodar("dconf", "dump", "/"), encoding="utf-8")
    (mint / "programas-apt.txt").write_text(_rodar("apt-mark", "showmanual"), encoding="utf-8")
    (mint / "programas-flatpak.txt").write_text(
        _rodar("flatpak", "list", "--app", "--columns=application"), encoding="utf-8")
    (mint / "extensoes-vscode.txt").write_text(_rodar("code", "--list-extensions"), encoding="utf-8")
    (mint / "crontab.txt").write_text(_rodar("crontab", "-l"), encoding="utf-8")
    for rel in (".config/autostart", ".config/systemd/user", ".config/wallpaper-engine",
                ".local/share/fonts", ".bashrc", ".profile", ".gitconfig", ".ssh",
                ".config/BraveSoftware/Brave-Browser/Default/Bookmarks",
                ".config/Code/User/settings.json", ".config/Code/User/keybindings.json",
                ".config/Code/User/snippets",
                ".var/app/com.obsproject.Studio/config/obs-studio/basic",
                ".var/app/com.obsproject.Studio/config/obs-studio/global.ini",
                ".var/app/com.obsproject.Studio/config/obs-studio/user.ini",
                ".var/app/com.obsproject.Studio/config/obs-studio/plugin_config/obs-websocket"):
        if (CASA / rel).exists():
            _copiar(CASA / rel, mint / "casa" / rel)
        else:
            faltou.append(rel)
    # Os comandos do Léo (~/.local/bin): os pequenos inteiros; atalhos e programas grandes, só o nome.
    lista = []
    for f in sorted((CASA / ".local/bin").glob("*")):
        if f.is_symlink():
            lista.append(f"{f.name} -> {os.readlink(f)}")
        elif f.is_file() and f.stat().st_size > GRANDE:
            lista.append(f"{f.name} (programa de {f.stat().st_size // 1024 ** 2} MB, não foi junto)")
        else:
            _copiar(f, mint / "casa/.local/bin" / f.name)
    (mint / "local-bin-atalhos.txt").write_text("\n".join(lista) + "\n", encoding="utf-8")
    return faltou


# -- o relatório do mês -------------------------------------------------------------------

PEDIDO_DO_RELATORIO = """Escreva o "Relatório - {mes}.md" do backup mensal da NOVA.

Quem vai ler: o Léo (que não é programador e lê mal inglês) E o Jarvis e a
Friday depois de uma formatação, quando a memória deles tiver sumido. Escreva
em português do Brasil, simples e claro para o Léo, mas completo e preciso o
bastante para o Jarvis/Friday voltarem a conhecer ele só com este arquivo.
Nada de inventar: só o que está nas fontes abaixo. Sem senhas, chaves ou
números de telefone no texto.

Seções (títulos em português, curtas e diretas):
1. Quem é o Léo: vida, escola, canal, jeito, gostos, pessoas próximas.
2. Como ele quer ser tratado: regras, preferências, o que irrita, o que ele
   já pediu para nunca fazer (cada uma com o porquê, se estiver nas fontes).
3. O computador: peças, discos e o que mora em cada um, sistema, programas.
4. A NOVA (Jarvis e Friday): o que fazem, personas, grupos e pessoas dos
   grupos, o que ficou pendente.
5. Os projetos: cada um, onde está, em que pé está.
6. O que mudou neste mês (pelas datas das anotações).

As fontes vêm a seguir, cada uma com o nome do arquivo."""


def _fontes() -> str:
    partes = []

    def junta(rotulo: str, caminho: Path) -> None:
        try:
            partes.append(f"\n===== {rotulo}: {caminho.name} =====\n{caminho.read_text(encoding='utf-8')}")
        except (OSError, UnicodeDecodeError):
            pass

    junta("caderno do Jarvis", DADOS / "casa/CLAUDE.md")
    for md in sorted((DADOS / "memorias").rglob("*.md")):
        junta("memória do Jarvis", md)
    for md in sorted(PROJETO.glob("jarvis/personas/persona_*.md")):
        junta("persona", md)
    for md in sorted((CASA / ".claude/projects").glob("*/memory/*.md")):
        junta("memória do Claude Code", md)
    partes.append("\n===== o PC agora =====\n" + "\n".join([
        _rodar("lscpu").split("\n\n")[0][:1500],
        _rodar("free", "-h"),
        _rodar("nvidia-smi", "--query-gpu=name,memory.total", "--format=csv"),
        _rodar("df", "-h", "-x", "tmpfs", "-x", "squashfs", "-x", "efivarfs"),
        _rodar("lsb_release", "-ds")]))
    return "".join(partes)


def escrever_relatorio(mes: str) -> str:
    """Pelo Claude Code (o mesmo cérebro do Jarvis), sem ferramentas: só lê e escreve."""
    claude = shutil.which("claude") or str(CASA / ".local/bin/claude")
    try:
        r = subprocess.run([claude, "-p", PEDIDO_DO_RELATORIO.format(mes=mes), "--model", "sonnet",
                            "--tools", "", "--no-session-persistence"],
                           input=_fontes(), capture_output=True, text=True, timeout=1800, cwd=str(PASTA))
        texto = r.stdout.strip()
        if r.returncode == 0 and len(texto) > 500:
            return texto
        erro = (r.stderr or r.stdout).strip()[-300:]
    except (OSError, subprocess.SubprocessError) as e:
        erro = str(e)
    return (f"# Relatório - {mes}\n\nNão deu pra escrever o relatório este mês ({erro}).\n"
            "Tudo o que ele teria está nas memórias dentro deste backup (pastas NOVA e Claude Code).\n")


# -- o backup -------------------------------------------------------------------------------

def _nome(agora: dt.date) -> tuple[str, str]:
    mes = f"{MESES[agora.month - 1].capitalize()} {agora.year}"
    return mes, f"Backup {agora:%Y-%m} ({MESES[agora.month - 1]}).nova"


def _rclone(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["rclone", *args], capture_output=True, text=True, timeout=3600)


def enviar(arquivo: Path) -> None:
    """Pro Drive: o backup, a chave trancada e o COMO RESTAURAR (sem segredo nenhum)."""
    for origem in (arquivo, CHAVE_TRANCADA, COMO_RESTAURAR):
        r = _rclone("copyto", str(origem), f"{REMOTO}/{origem.name}")
        if r.returncode != 0:
            raise RuntimeError(f"rclone: {(r.stderr or r.stdout).strip()[-300:]}")
    # Só DEPOIS do novo subir inteiro: ficam sempre os 3 mais novos (contando o de agora).
    backups = sorted(n for n in _rclone("lsf", REMOTO, "--files-only").stdout.splitlines()
                     if n.startswith("Backup ") and n.endswith(".nova"))
    for velho in backups[:-MANTER]:
        _rclone("deletefile", f"{REMOTO}/{velho}")


def fazer(mandar: bool = True, hoje: dt.date | None = None) -> dict:
    hoje = hoje or dt.date.today()
    mes, nome = _nome(hoje)
    if not PUBLICA.exists():
        return _guardar({"quando": dt.datetime.now().isoformat(timespec="minutes"), "ok": False,
                         "erro": "falta criar a senha (--criar-senha)"})
    if mandar and not shutil.which("rclone"):
        return _guardar({"quando": dt.datetime.now().isoformat(timespec="minutes"), "ok": False,
                         "erro": "falta instalar o rclone"})
    base = _HD_TMP if _HD_TMP.is_dir() else None
    with tempfile.TemporaryDirectory(prefix="nova-backup-", dir=base) as tmp:
        raiz = Path(tmp) / nome.removesuffix(".nova")
        faltou = juntar(raiz)
        relatorio = escrever_relatorio(mes)
        (raiz / f"Relatório - {mes}.md").write_text(relatorio, encoding="utf-8")
        PASTA.mkdir(parents=True, exist_ok=True)
        (PASTA / "ultimo-relatorio.md").write_text(relatorio, encoding="utf-8")
        if COMO_RESTAURAR.exists():
            shutil.copy2(COMO_RESTAURAR, raiz / COMO_RESTAURAR.name)
        pacote = io.BytesIO()
        with tarfile.open(fileobj=pacote, mode="w:gz") as tar:
            tar.add(raiz, arcname=raiz.name)
        trancado = trancar(pacote.getvalue(), PUBLICA.read_bytes())
        arquivo = Path(tmp) / nome
        arquivo.write_bytes(trancado)
        resultado = {"quando": dt.datetime.now().isoformat(timespec="minutes"), "mes": mes, "arquivo": nome,
                     "mb": round(len(trancado) / 1024 ** 2, 1), "faltou": faltou, "contado": False}
        if mandar:
            try:
                enviar(arquivo)
                resultado["ok"] = True
            except (RuntimeError, OSError, subprocess.SubprocessError) as e:
                resultado.update(ok=False, erro=str(e))
        else:
            guardado = PASTA / nome
            shutil.copy2(arquivo, guardado)
            resultado.update(ok=True, local=str(guardado))
    return _guardar(resultado)


def _guardar(r: dict) -> dict:
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return r


def restaurar(arquivo: Path, chave: Path, destino: Path, senha: str) -> Path:
    dados = abrir(arquivo.read_bytes(), chave.read_bytes(), senha)
    destino.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(dados), mode="r:gz") as tar:
        tar.extractall(destino, filter="data")
    return destino


def relatorio() -> str:
    try:
        r = json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "nenhum backup ainda"
    if r.get("contado"):
        return "nada novo"
    if r.get("ok"):
        return f"backup de {r.get('mes', '?')} feito em {r['quando']}: {r.get('mb')} MB no Drive"
    return f"o backup de {r.get('quando', '?')} NÃO foi feito: {r.get('erro', '?')}"


def marcar_contado() -> None:
    try:
        r = json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    r["contado"] = True
    _guardar(r)


def main(a: list[str]) -> int:
    if a[:1] == ["--criar-senha"]:
        if PUBLICA.exists() and input("Já existe uma senha. Trocar? Os backups antigos continuam "
                                      "abrindo só com a senha antiga. (s/n) ").strip().lower() != "s":
            return 1
        senha = getpass.getpass("Escolha a senha do backup: ")
        if len(senha) < 8 or senha != getpass.getpass("Repita a senha: "):
            print("As senhas não batem ou são curtas demais (mínimo 8). Nada mudou.")
            return 1
        criar_chaves(senha)
        print("Pronto. Guarde essa senha: sem ela, ninguém abre o backup (nem eu).")
        return 0
    if a[:1] in (["--agora"], ["--local"]):
        r = fazer(mandar=a[0] == "--agora")
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    if a[:1] == ["--restaurar"] and len(a) == 4:
        try:
            print(restaurar(Path(a[1]), Path(a[2]), Path(a[3]), getpass.getpass("Senha do backup: ")))
            return 0
        except ValueError as e:
            print(e)
            return 1
    if a[:1] == ["--relatorio"]:
        print(relatorio())
        return 0
    if a[:1] == ["--contado"]:
        marcar_contado()
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
