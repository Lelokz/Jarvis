# Reconhecer a voz do Léo — etapa 1: a impressão de voz separa? (21/10/2026)

**Pergunta:** a impressão de voz ECAPA (SpeechBrain, `spkrec-ecapa-voxceleb`)
separa o Léo de outras pessoas, no celular e no PC, com um perfil só?

**Dados (fora do git):**
- Léo, celular: 47 áudios que ele MANDOU no WhatsApp em out/2026 (21,6 min),
  baixados e decifrados direto do servidor (`rascunho/voz_leo/baixar_audios.py`;
  o download da ponte leva 403 porque corta a assinatura do endereço). Os de
  antes de out/2026 já tinham expirado (403/410). Ficam em
  `~/.local/share/jarvis/voz-leo/celular/`.
- Léo, PC: 200 falas sorteadas de `logs/audio` (microfone do PC).
- Outras pessoas: 224 trechos das cenas dubladas do treino da voz (vozes
  adultas, de estúdio). **Não** se usaram áudios recebidos de amigos: são
  deles, sem consentimento (o classificador do Claude Code barrou, com razão).

**Perfil:** média das impressões de metade dos áudios de celular (24), em
trechos de 3 s. Testado na outra metade, no PC e nos outros.

| fala | limiar | outros aceitos | Léo celular | Léo PC |
|---|---|---|---|---|
| 1,5 s | 0,30 | 0% | 91,5% | 96,2% |
| 1,5 s | 0,35 | 0% | 85,4% | 93,2% |
| 3 s | 0,30 | 0% | 99,1% | 100% |
| 3 s | 0,35 | 0% | 99,1% | 100% |

Nota mais alta de outra pessoa: 0,21 (1,5 s) e 0,27 (3 s). Mediana do Léo:
0,50–0,65. **Um perfil (do celular) serve para o PC também.**

**O que isto NÃO mostra:** os "outros" são atores adultos em estúdio, mais
fáceis de separar que um amigo da mesma idade gravando pelo mesmo tipo de
celular. A calibração de verdade é com voluntários que topem (etapa 2), e o
relógio ainda não foi medido. Frase curta ("sim", "pode") fica abaixo de
1,5 s e não dá para confiar.

Script: `rascunho/voz_leo/medir.py` (venv do treino da voz).
