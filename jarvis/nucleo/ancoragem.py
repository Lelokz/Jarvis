"""A guarda contra o modelo inventar nome de dentro da lista.

Por que existe: numa sessão real, `"abridança.ppxt"` fez o Jarvis responder
"Abrindo loft" e abrir o navegador. Em 6 execuções da mesma frase, 2 devolveram
`loft` — entrada sem nenhuma relação com a resposta. E vinha com nota 1.00 e
desfecho CERTO no casador de atalhos, porque a substituição acontecia **antes**
dele: o corte de 0.92 nunca via o erro.

Isso viola a §2.2 do escopo — agir com certeza total sobre algo que não foi
pedido.

A causa é a variante "com lista no prompt", escolhida na Etapa 1 com medição
(70% de resolução direta contra 60%, e metade da latência). O prompt manda usar
o nome da lista que corresponde ao pedido, e diante de entrada embaralhada o
modelo às vezes obedece literalmente. Voltar à variante cega custaria os dois
números; a correção é validar **depois** do modelo.

**O critério:** o nome devolvido tem que ser encontrável na transcrição.
Deslizamos janelas de palavras sobre o que o Whisper transcreveu e ficamos com
a melhor semelhança. Isso permite o que a lista existe para fazer — aproximar
`lofit` de `loft` — e proíbe o que ela causou de errado.

**Medido** nos pares reais, antes de fixar o corte:

    normalizações legítimas   pior caso 0.737 ("abre as gravasoins" → gravações)
    invenções                 pior caso 0.333 ("Download." → loft)

O corte de 0.60 fica quase no dobro da pior invenção e bem abaixo da pior
normalização legítima — folga dos dois lados.
"""

from __future__ import annotations

import difflib

from .atalhos import normalizar


def ancoragem(nome: str, transcricao: str) -> float:
    """Quanto o nome extraído se parece com algum trecho do que foi dito.

    Testa janelas do tamanho do nome e de ±1 palavra, porque o modelo às vezes
    engole um artigo ou junta uma palavra a mais.
    """
    palavras = normalizar(transcricao).split()
    alvo = normalizar(nome)
    if not alvo or not palavras:
        return 0.0

    n = len(alvo.split())
    melhor = 0.0
    for largura in {max(1, n - 1), n, n + 1}:
        for i in range(max(1, len(palavras) - largura + 1)):
            janela = " ".join(palavras[i : i + largura])
            melhor = max(melhor, difflib.SequenceMatcher(None, alvo, janela).ratio())
    return melhor
