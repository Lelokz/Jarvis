# Jarvis — instruções do projeto

Assistente pessoal por voz em Python, rodando local na máquina do Léo
(RTX 3060 12GB). Escopo completo, etapas e funções: leia `ESCOPO.md`
antes de planejar qualquer etapa.

## Regras invioláveis

- **Nunca** gerar código ou comando de shell para o modelo executar.
  O LLM escolhe de uma lista fechada de funções escritas à mão.
  Sem `exec`, sem `eval`, sem string indo pro PowerShell.
- **Nunca** chutar intenção. Ambíguo ou busca com vários resultados →
  perguntar em voz alta. Silêncio não é resposta.
- Ação destrutiva (mover, renomear, sobrescrever) exige confirmação
  falada antes de executar.
- Não apagar arquivo. Lixeira no máximo, e só depois da Etapa 5.
- Toda ação executada vai pro log.
- Funcionar bem > arquitetura elegante. Latência baixa é prioridade.

## Método

1. Léo descreve → 2. investigar → 3. **PLAN MODE** (plano escrito, sem
código) → 4. Léo aprova → 5. implementar → 6. rodar → 7. **Léo testa
manualmente** (é a fonte de verdade) → 8. próxima etapa.

Não pular etapas. Não implementar sem plano aprovado.
Não fazer commit git sem o Léo pedir.
Nunca usar `sudo` sem avisar antes o que o comando faz.

## Ambiente

- **Linux Mint Cinnamon** (base Ubuntu), bash
- RTX 3060 12GB com driver proprietário NVIDIA, Ryzen 5 3400G, 16GB RAM
- Projeto em `~/Projetos/Jarvis`, repositório Git privado
- Áudio via PipeWire
- Python 3 do sistema; usar venv no projeto
- Não instalar biblioteca por memória: verificar o que está atual antes

## Persona do Jarvis

Voz masculina, nome "Jarvis" (trocável via config — não chumbar no
código). Fala como pessoa normal: nem formal, nem cheio de gíria.
Respostas curtas, é voz e não texto.
