"""As travas da voz: o que só o Léo pode pedir (out/2026).

Quando a impressão de voz diz que quem falou NÃO é o Léo (`jarvis/quem_fala.py`),
estas ferramentas são barradas no código, antes de rodar, mesmo que alguém
convença o Claude. Decisão do Léo (21/10/2026):

- livre para qualquer um: conversar, olhar arquivos, música, volume e
  ACRESCENTAR coisa na memória;
- o Claude julga (persona, "Outras vozes"): mandar mensagem;
- só o Léo (aqui): apagar ou trocar o que está na memória, criar/editar/mover/
  apagar arquivo, instalar ou desinstalar, desligar ou bloquear o PC.

A lista do Bash (e a do PowerShell, no Windows) é de comandos claramente perigosos,
não um cadeado perfeito:
o resto fica com o julgamento do Claude. Bloquear demais só atrapalha os
amigos do Léo, nunca ele.
"""
from __future__ import annotations

import re
from pathlib import Path

_BASH = [
    (re.compile(r"(^|[;&|`(]|\s)(sudo|rm|rmdir|shred|unlink|mv|dd|truncate|chmod|chown|crontab)\s"),
     "apagar, mover ou mexer em arquivo"),
    (re.compile(r"\bfind\b.*\s-delete\b|\bgio\s+(trash|remove|move|rename|save|copy)\b"),
     "apagar ou mexer em arquivo"),
    (re.compile(r"\bsed\s+(-\w*i|--in-place)|\btee\b|\btouch\s|\bmkdir\s|\bcp\s"),
     "criar ou editar arquivo"),
    (re.compile(r"(?<![0-9&>])>(?![&>])\s*(?!/dev/null)[^\s]|>>\s*(?!/dev/null)[^\s]"),
     "criar ou editar arquivo"),
    (re.compile(r"\b(apt|apt-get|aptitude|dpkg|snap|flatpak|pip|pip3|pipx|npm|pnpm|yarn|cargo|gem)\s+"
                r"(install|remove|purge|uninstall|i|add|rm)\b|\|\s*(sudo\s+)?(sh|bash)\b"),
     "instalar ou desinstalar programa"),
    (re.compile(r"(^|[;&|`(]|\s)(shutdown|poweroff|reboot|halt|kill|pkill|killall)\b"
                # com ou sem opções no meio ("systemctl --user stop ...", furo achado em 25/10/2026)
                r"|\bsystemctl\s+(-{1,2}[\w=-]+\s+)*(poweroff|reboot|suspend|hibernate|halt|stop|disable|mask|kill|restart)\b"
                r"|\bloginctl\s+(lock|terminate|poweroff|reboot|kill)"),
     "desligar o PC ou fechar programa à força"),
    (re.compile(r"\bcinnamon-screensaver-command\s+(-l|--lock|-a|--activate)\b|\bxdg-screensaver\s+lock\b"),
     "bloquear o PC"),
    (re.compile(r"\bgit\s+(push|reset|clean|rm|commit|checkout|restore)\b"),
     "mexer em arquivo"),
]

# No Windows o Claude Code roda comando pelo PowerShell (e não só pelo Bash): as
# mesmas regras, com os nomes de lá. Os apelidos do PowerShell (rm, mv, cp, kill...)
# já caem na lista do Bash, que também vale para ele.
_POWERSHELL = [
    (re.compile(r"\b(Remove-Item|Move-Item|Rename-Item|Clear-Content|Clear-RecycleBin|del|erase|rd|ri|ren|move|mi|rni)\b",
                re.I), "apagar, mover ou mexer em arquivo"),
    (re.compile(r"\b(New-Item|Copy-Item|Set-Content|Add-Content|Out-File|Export-\w+|md|ni|copy|cpi|sc|ac)\b"
                r"|\[System\.IO\.File\]::Write", re.I), "criar ou editar arquivo"),
    (re.compile(r"\b(winget|choco|scoop)\s+(install|uninstall|upgrade|remove)\b|\bmsiexec\b"
                r"|\b(Install|Uninstall)-(Package|Module|Script)\b|-Verb\s+RunAs\b"
                r"|\b(irm|iwr|Invoke-RestMethod|Invoke-WebRequest)\b.*\|\s*(iex|Invoke-Expression)\b", re.I),
     "instalar ou desinstalar programa"),
    (re.compile(r"\b(Stop-Computer|Restart-Computer|Stop-Process|spps|taskkill|tskill|Stop-Service|Set-Service"
                r"|Disable-\w+|Suspend-Computer)\b|\bshutdown(\.exe)?\s", re.I),
     "desligar o PC ou fechar programa à força"),
]
TERMINAIS = {"Bash", "PowerShell"}

_EDITAM = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# A tela de bloqueio por comando direto: sempre barrado, até para o Léo. Só
# pelas ferramentas bloquear_pc e pedir_desbloqueio (esta pede o Sim no
# celular; um comando pularia a confirmação).
_TELA = re.compile(r"\bcinnamon-screensaver-command\b|\bloginctl\s+(un)?lock-sessions?\b"
                   r"|\bxdg-screensaver\b|ScreenSaver\.(SetActive|Lock)|\bgnome-screensaver-command\b"
                   r"|\bdm-tool\s+lock\b|\bxdg-screensaver\s+lock\b"
                   # o Windows
                   r"|LockWorkStation|\btsdiscon\b|\blogoff(\.exe)?\b"
                   # o código do próprio Jarvis e a porta que recebe o Sim do celular
                   r"|desbloque|tela\.(bloquear|desbloquear)")


def mexe_na_tela(comando: str) -> bool:
    return bool(_TELA.search(comando))


def precisa_do_leo(ferramenta: str, entrada: dict, memoria: Path) -> str | None:
    """O que a ferramenta faria que só o Léo pode pedir, ou None se pode.

    `memoria`: o CLAUDE.md da casa. Nele, outra pessoa pode ACRESCENTAR (o
    texto que já estava continua todo lá), mas não apagar nem trocar.
    """
    if ferramenta in _EDITAM:
        caminho = str(entrada.get("file_path") or entrada.get("notebook_path") or "")
        # Recado para ele mesmo ("me lembra daqui a 10 min") qualquer um pode
        # deixar: fica num arquivo dele, ao lado da memória.
        if caminho and Path(caminho).expanduser().resolve() == (memoria.parent / "recados.md").resolve():
            return None
        if caminho and Path(caminho).expanduser().resolve() == memoria.resolve():
            return None if _so_acrescenta(ferramenta, entrada, memoria) else \
                "apagar ou trocar o que está na memória"
        return "criar ou editar arquivo"
    if ferramenta in TERMINAIS:
        comando = str(entrada.get("command") or "")
        for padrao, o_que in _BASH + (_POWERSHELL if ferramenta == "PowerShell" else []):
            if padrao.search(comando):
                return o_que
        return None
    if ferramenta.startswith("mcp__"):
        acao = ferramenta.rsplit("__", 1)[-1].lower()
        if acao == "bloquear_pc":
            return "bloquear o PC"
        if acao == "pedir_desbloqueio":
            return "desbloquear o PC"
        if any(p in acao for p in ("trash", "delete", "remove", "uninstall")):
            return "apagar"
    return None


def _so_acrescenta(ferramenta: str, entrada: dict, memoria: Path) -> bool:
    if ferramenta == "Edit":
        return str(entrada.get("old_string", "")) in str(entrada.get("new_string", ""))
    if ferramenta == "MultiEdit":
        return all(str(e.get("old_string", "")) in str(e.get("new_string", ""))
                   for e in entrada.get("edits") or [])
    if ferramenta == "Write":
        try:
            antes = memoria.read_text()
        except OSError:
            antes = ""
        return antes.strip() in str(entrada.get("content", ""))
    return False
