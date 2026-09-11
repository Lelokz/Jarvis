#!/usr/bin/env python3
"""Autoriza o Jarvis a usar a sua conta do Google. Roda uma vez.

Abre o navegador, você escolhe a conta e concede. O token fica gravado em
`token_google.json` e a partir daí ele se renova sozinho.

**Você vai ver uma tela dizendo "O Google não verificou este app".** É
esperado: o app é seu, tem um usuário, e verificação do Google só é exigida
acima de 100 usuários. Clique em **Avançado** → **Acessar Jarvis (não seguro)**.

Se essa tela disser que a autorização expira em 7 dias, o app ficou em
"Testing" no console. Volte em Google Auth Platform → Público-alvo → Publicar
app, e rode isto de novo.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CREDENCIAIS = RAIZ / "credenciais_google.json"
TOKEN = RAIZ / "token_google.json"

# O mais estreito que cria e lê eventos. Não dá acesso a configurações do
# calendário nem a outros serviços — Drive e Fotos, quando entrarem, pedem os
# escopos deles, e é isso que torna esta etapa a fundação dos três.
ESCOPOS = ["https://www.googleapis.com/auth/calendar.events"]


def main() -> int:
    if not CREDENCIAIS.is_file():
        print(
            f"\nFalta o arquivo {CREDENCIAIS.name} na raiz do projeto.\n\n"
            "  Ele vem do Google Cloud Console:\n"
            "    Google Auth Platform → Clientes → Criar cliente\n"
            "    Tipo: App para computador → Criar → Baixar JSON\n"
            f"  Salve o download como {CREDENCIAIS.name} aqui em {RAIZ}\n",
            file=sys.stderr,
        )
        return 1

    from google_auth_oauthlib.flow import InstalledAppFlow

    print("\nAbrindo o navegador para você autorizar...")
    print('Se aparecer "O Google não verificou este app":')
    print("  Avançado → Acessar Jarvis (não seguro)\n")

    fluxo = InstalledAppFlow.from_client_secrets_file(str(CREDENCIAIS), ESCOPOS)
    credencial = fluxo.run_local_server(port=0, prompt="consent")

    TOKEN.write_text(credencial.to_json(), encoding="utf-8")
    TOKEN.chmod(0o600)  # é a chave da conta: só o dono lê

    print(f"  autorizado — token gravado em {TOKEN.name}")

    # Prova de que funcionou, e mostra QUAL conta foi conectada. Sem isto,
    # descobrir que autorizou a conta errada só aconteceria depois de escrever
    # um evento no lugar errado.
    from googleapiclient.discovery import build

    servico = build("calendar", "v3", credentials=credencial, cache_discovery=False)
    # `events().list()` e não `calendars().get()`: aquele lê metadados do
    # calendário e não cabe no escopo `calendar.events`, estourando 403. Este
    # cabe, e ainda traz o email da conta e o fuso de brinde.
    r = servico.events().list(calendarId="primary", maxResults=1).execute()
    print(f"  conta conectada: {r.get('summary')}")
    print(f"  fuso do calendário: {r.get('timeZone')}")
    print(f"  seu papel nela: {r.get('accessRole')}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
