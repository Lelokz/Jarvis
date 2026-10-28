# A ponte do WhatsApp da NOVA

Os três arquivos de `whatsapp-bridge/` do projeto
[lharries/whatsapp-mcp](https://github.com/lharries/whatsapp-mcp) (licença MIT),
commit 7d6a06dcdce1f01dfb24f60e1030d5efba9f3b88, com as mudanças da NOVA:

- `store/pareamento.json`: o QR e o código de 8 letras para Ajustes → Conexões
  (`NOVA_TELEFONE` pede o código), e as rotas `/api/estado` e `/api/sair`.
- `NOVA_PORTA`: outra porta, para testar uma ponte ao lado da de verdade.
- O REST só em 127.0.0.1 (no original, qualquer aparelho da rede mandava mensagem).
- SQLite em Go puro (`modernc.org/sqlite`): compila sem gcc, no Linux e no Windows.

O instalador (tela 4) baixa a ponte já compilada, do Drive do Léo (19 MB, conferida
pelo sha256 de `PONTE_PRONTA` em `nova_instalador/passos.py`). Sem o id do Drive lá,
ele baixa o Go oficial e compila no PC da pessoa (`CGO_ENABLED=0 go build`).

Para compilar de novo (mudou o `main.go`), com o Go 1.27.3 oficial, e trocar o arquivo
no Drive e o sha256 no `passos.py`:

    CGO_ENABLED=0 GOOS=linux   GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o whatsapp-bridge-linux-amd64 .
    CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o whatsapp-bridge-windows-amd64.exe .
