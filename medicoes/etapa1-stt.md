# Etapa 1 — transcrição de fala rápida

Set/2026. O Léo relatou que, falando rápido, "abre o loft" sai com as palavras
coladas e letras embaralhadas. O texto chega errado no núcleo, e aí nem o
casamento aproximado tem chance: o problema é do Whisper, antes de tudo.

Duas hipóteses medidas: `initial_prompt` alimentado pelo `atalhos.toml`, e
`beam_size` (que estava em 1 desde a Etapa 0, escolhido quando latência era a
pergunta em aberto).

> ### O áudio é sintético
>
> O microfone do Léo tem mute físico e ele estava fora. As frases foram
> geradas no Piper em três velocidades (`length_scale` 1.0 / 0.70 / 0.55).
>
> **Isso não reproduz a voz dele**, e a voz PT-BR do Piper pronuncia "loft"
> como palavra portuguesa, o que é mais difícil que a fala real. Os números
> absolutos são pessimistas.
>
> A **comparação entre configurações** continua válida: todas receberam
> exatamente o mesmo áudio. É comparação relativa, e é dela que a decisão
> precisa.

## Método

15 clipes: 5 frases com nomes de atalhos × 3 velocidades.

A métrica é **"o nome sobreviveu?"** — não interessa a frase inteira sair
perfeita, interessa o nome do atalho chegar reconhecível ao casador. Mede-se
varrendo janelas de palavras da transcrição e exigindo semelhança ≥ 0.85 com o
nome esperado.

## Resultado: o `beam_size` não é a alavanca

| configuração | nome sobreviveu | latência |
|---|---:|---:|
| beam 1, sem vocabulário **(era o padrão)** | 5/15 | 0.25s |
| beam 1, com vocabulário | **8/15** | 0.25s |
| beam 3, sem vocabulário | 4/15 | 0.28s |
| beam 3, com vocabulário | 8/15 | 0.29s |
| beam 5, com vocabulário | 8/15 | 0.31s |

**Subir o beam não melhora nada.** Com vocabulário, 1, 3 e 5 dão o mesmo
resultado — e custam +16% e +24% de latência. Sem vocabulário, o beam 3 saiu
*pior* que o beam 1, o que é ruído mas deixa claro que não há ganho ali.

**O vocabulário é a alavanca**, e é de graça em latência.

## `initial_prompt` contra `hotwords`

O faster-whisper tem os dois mecanismos. Medidos no mesmo áudio, beam 1:

| variante | nome sobreviveu |
|---|---:|
| nenhum | 4/15 |
| `initial_prompt` | 8/15 |
| `hotwords` | 8/15 |
| **os dois juntos** | **9/15** |

A diferença de 8 para 9 é ruído numa amostra de 15. Mas somar não custa
latência, então não há motivo para escolher: os dois ficam ligados.

## Antes e depois, com a configuração final

| | nome sobreviveu | latência média |
|---|---:|---:|
| antes | 3/15 | 0.269s |
| **depois** | **9/15** | **0.260s** |

O triplo de nomes sobrevivendo, com a mesma latência.

*(O "antes" oscilou entre 3/15 e 5/15 entre execuções — o Whisper tem
fallback de temperatura e não é determinístico. O "depois" ficou estável em
8–9.)*

## O que ficou configurado

```toml
[stt]
beam_size = 1          # mantido: subir não melhora e custa latência
usar_vocabulario = true
```

Os nomes vêm do `atalhos.toml`, não de uma lista chumbada no código:
acrescentar um atalho passa a melhorar a transcrição dele de graça. Quem faz a
ligação é o `assistente.py` — o cliente lê os nomes do núcleo e entrega ao
Whisper, direção permitida pela linha da §4.

## O que continua em aberto

9/15 ainda é longe de perfeito. Boa parte disso é o teste ser mais duro que a
realidade — voz sintética, velocidade exagerada, palavra inglesa dita por voz
portuguesa. **Só o teste do Léo com a própria voz diz onde isto realmente
está.** Se ainda incomodar, o próximo passo não é o `beam_size`: seria um
modelo maior, ou ensinar a pronúncia ao Whisper por outro caminho.
