# A ponte do WhatsApp da NOVA

Os três arquivos de `whatsapp-bridge/` do projeto
[lharries/whatsapp-mcp](https://github.com/lharries/whatsapp-mcp) (licença MIT),
commit 7d6a06dcdce1f01dfb24f60e1030d5efba9f3b88, com as mudanças da NOVA:

- `store/pareamento.json`: o QR e o código de 8 letras para Ajustes → Conexões
  (`NOVA_TELEFONE` pede o código), e as rotas `/api/estado` e `/api/sair`.
- `NOVA_PORTA`: outra porta, para testar uma ponte ao lado da de verdade.
- O REST só em 127.0.0.1 (no original, qualquer aparelho da rede mandava mensagem).
- SQLite em Go puro (`modernc.org/sqlite`): compila sem gcc, no Linux e no Windows.

O instalador (tela 4) baixa o Go oficial e compila com `CGO_ENABLED=0 go build`.
