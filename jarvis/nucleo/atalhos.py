"""A tabela de atalhos e o casamento aproximado de nomes.

O modelo extrai o nome que o Léo falou; é aqui que esse nome vira uma entrada
concreta da tabela. Aproximado porque a frase não chega limpa: ela passou pelo
Whisper antes, e "gravações" pode chegar como "gravasoes", "gravações" ou
"gravação".

Três desfechos, e a diferença entre eles é a regra §2.2 do ESCOPO — nada de
chutar:

  CERTO     casou bem e sem concorrente → executa
  SUGESTAO  casou mais ou menos, ou dois empataram → pergunta em voz alta
  NADA      não casou com coisa alguma → diz que não conhece

`difflib` é stdlib e o projeto já o usa no `--autoteste` do `etapa0.py`. Com
uma tabela de dezenas de entradas ele é instantâneo — não vale uma dependência
nova.
"""

from __future__ import annotations

import difflib
import re
import tomllib
import unicodedata
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

# Casou bem o bastante para agir sem perguntar.
#
# Alto de propósito. Semelhança de caracteres NÃO separa um erro do Whisper de
# uma palavra diferente que por acaso se parece: "gravitações" pontua 0.90
# contra "gravações", acima de "gravasoes" (0.89), que é o erro legítimo.
# Não existe corte que acerte os dois. Então só casamento quase exato age
# sozinho; o resto pergunta. Errar a pergunta custa um "sim"; errar a ação
# abre a coisa errada — a assimetria manda ser conservador, e a §2.2 também.
CERTEZA = 0.92
# Abaixo disto nem vale sugerir: é outra coisa.
SUGESTAO = 0.60
# Dois candidatos separados por menos que isto são um empate: perguntar qual.
EMPATE = 0.08

TIPOS_VALIDOS = ("site", "pasta", "vscode")


class Desfecho(Enum):
    CERTO = auto()
    SUGESTAO = auto()
    NADA = auto()


@dataclass(frozen=True)
class Atalho:
    nome: str
    tipo: str
    alvo: str


@dataclass(frozen=True)
class Casamento:
    desfecho: Desfecho
    atalho: Atalho | None
    pontuacao: float
    # Quando dois empatam, o cliente precisa saber os dois para perguntar.
    empatados: tuple[Atalho, ...] = ()


# Artigos e preposições que o modelo costuma trazer junto do nome. Sem tirar
# isto, "o loft" pontua 0.80 contra "loft" e vira pergunta desnecessária.
_SUPERFLUAS = {"o", "a", "os", "as", "um", "uma", "de", "do", "da", "no", "na"}


def normalizar(texto: str) -> str:
    """Tira acento, caixa, pontuação e artigos — o ruído que não é o nome.

    "Gravações!", "as gravações" e "gravasoes" convergem antes de comparar.
    """
    sem_acento = "".join(
        c
        for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )
    limpo = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", sem_acento)).strip()
    palavras = [p for p in limpo.split() if p not in _SUPERFLUAS]
    # Se sobrou nada, o texto era só artigo: devolve o original limpo.
    return " ".join(palavras) if palavras else limpo


class Tabela:
    def __init__(self, atalhos: list[Atalho]) -> None:
        self.atalhos = atalhos
        self._normalizados = [(normalizar(a.nome), a) for a in atalhos]

    @classmethod
    def carregar(cls, caminho: Path) -> Tabela:
        if not caminho.is_file():
            raise FileNotFoundError(
                f"atalhos.toml não encontrado em {caminho}.\n"
                "  É a tabela do que o Jarvis sabe abrir."
            )
        with caminho.open("rb") as f:
            bruto = tomllib.load(f)

        atalhos = []
        for nome, dados in bruto.items():
            if not isinstance(dados, dict):
                raise ValueError(f'atalhos.toml: "{nome}" não é uma tabela.')
            faltando = {"tipo", "alvo"} - dados.keys()
            if faltando:
                raise ValueError(
                    f'atalhos.toml: "{nome}" está sem {", ".join(sorted(faltando))}.'
                )
            if dados["tipo"] not in TIPOS_VALIDOS:
                raise ValueError(
                    f'atalhos.toml: "{nome}" tem tipo "{dados["tipo"]}", '
                    f"que não existe. Válidos: {', '.join(TIPOS_VALIDOS)}."
                )
            atalhos.append(Atalho(nome=nome, tipo=dados["tipo"], alvo=dados["alvo"]))
        return cls(atalhos)

    def __len__(self) -> int:
        return len(self.atalhos)

    # ----------------------------------------------------------------------

    def pontuar(self, falado: str) -> list[tuple[Atalho, float]]:
        """Todos os atalhos, do mais parecido ao menos."""
        alvo = normalizar(falado)
        notas = [
            (atalho, difflib.SequenceMatcher(None, alvo, nome).ratio())
            for nome, atalho in self._normalizados
        ]
        return sorted(notas, key=lambda p: p[1], reverse=True)

    def casar(self, falado: str) -> Casamento:
        if not falado.strip() or not self.atalhos:
            return Casamento(Desfecho.NADA, None, 0.0)

        notas = self.pontuar(falado)
        melhor, nota = notas[0]

        if nota < SUGESTAO:
            return Casamento(Desfecho.NADA, None, nota)

        # Empate: dois atalhos plausíveis e parecidos entre si. Perguntar qual
        # é obrigatório aqui — abrir o errado é justamente o que a §2.2 proíbe.
        if len(notas) > 1 and nota - notas[1][1] < EMPATE and notas[1][1] >= SUGESTAO:
            return Casamento(
                Desfecho.SUGESTAO, melhor, nota, empatados=(melhor, notas[1][0])
            )

        if nota >= CERTEZA:
            return Casamento(Desfecho.CERTO, melhor, nota)
        return Casamento(Desfecho.SUGESTAO, melhor, nota)
