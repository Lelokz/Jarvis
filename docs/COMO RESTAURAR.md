# Como restaurar tudo depois de formatar

Este é o passo a passo pra deixar o PC e a NOVA (Jarvis e Friday) como
estavam, usando o backup do mês. Escrito pro Léo e também pro Jarvis/Friday
(ou qualquer Claude) seguir.

**O que você precisa:**
- a internet;
- a **senha do backup**, a que só você sabe. Sem ela não dá pra abrir.

---

## 1. Pegar os arquivos no Drive

No Google Drive, abra a pasta **"NOVA - Backup"** e baixe dois arquivos:
- o backup mais novo, que tem o nome tipo `Backup 2026-11 (novembro).nova`;
- a `chave-trancada.key`.

Coloque os dois na pasta **Downloads**.

## 2. Pegar a NOVA no GitHub

Abra o terminal e cole:

    sudo apt install git python3-venv python3-pip python3-cryptography
    mkdir -p ~/Projetos && cd ~/Projetos
    git clone https://github.com/Lelokz/Jarvis.git

## 3. Abrir o backup

Ainda no terminal, troque o nome do arquivo pelo nome do seu backup:

    python3 ~/Projetos/Jarvis/jarvis/monitor/backup.py --restaurar ~/Downloads/"Backup 2026-11 (novembro).nova" ~/Downloads/chave-trancada.key ~/Downloads/backup-aberto

Ele pede a senha. Se aparecer "senha errada", é a senha. Se aparecer "o
arquivo do backup está estragado", baixe o mesmo arquivo de novo ou use o
backup do mês anterior.

Vai aparecer a pasta `~/Downloads/backup-aberto`. Dentro dela:
- `Relatório - <mês>.md`: tudo o que a NOVA sabia de você naquele mês;
- `NOVA/`: o que o Jarvis e a Friday sabem, mais a sessão do WhatsApp;
- `Claude Code/`: as memórias e as configurações do Claude Code;
- `Mint/`: as configurações do Linux e a lista de programas.

## 4. Pôr cada coisa no lugar

O jeito fácil: instale o Claude Code e peça **"restaura o backup da NOVA
seguindo o COMO RESTAURAR.md que está em ~/Downloads/backup-aberto"**.

Pra fazer na mão, `B` é a pasta do backup aberto (`~/Downloads/backup-aberto/Backup .../`):

| Do backup | Vai pra |
|---|---|
| `B/NOVA/jarvis/` (tudo) | `~/.local/share/jarvis/` |
| `B/NOVA/whatsapp-ponte-store/` | `~/.local/share/jarvis/whatsapp-mcp/whatsapp-bridge/store/` (a ponte precisa ser compilada antes) |
| `B/Claude Code/memorias/<pasta>/` | `~/.claude/projects/<pasta>/memory/` |
| `B/Claude Code/skills`, `settings.json`, `.credentials.json` | `~/.claude/` |
| `B/Claude Code/claude.json` | `~/.claude.json` |
| `B/Mint/casa/` (tudo, com os pontos: `.ssh`, `.config`...) | `~/` (a sua pasta pessoal) |
| `B/Mint/cinnamon-dconf.ini` | rode `dconf load / < B/Mint/cinnamon-dconf.ini` |
| `B/Mint/programas-apt.txt` | rode `sudo apt install $(cat B/Mint/programas-apt.txt)` |
| `B/Mint/programas-flatpak.txt` | rode `flatpak install $(cat B/Mint/programas-flatpak.txt)` |
| `B/Mint/extensoes-vscode.txt` | uma por uma: `code --install-extension <nome>` |

Depois de copiar o `.ssh`, rode `chmod 700 ~/.ssh && chmod 600 ~/.ssh/*`.

## 5. Ligar a NOVA de novo

    cd ~/Projetos/Jarvis && ./setup.sh

- **As vozes treinadas** (Jarvis dublado e Friday) estão no Drive, em
  **"NOVA - Pacote de vozes"**, e não no backup, porque são grandes demais.
  Descompacte o pacote em `~/.local/share/jarvis/`.
- **Os modelos do Ollama** baixam de novo com `ollama pull`. A lista está no
  relatório.
- **O WhatsApp:** se a sessão não voltar sozinha, escaneie o QR de novo.

Quando o Jarvis falar de novo, peça pra ele ler o `Relatório` do backup.
Assim ele volta a te conhecer.
