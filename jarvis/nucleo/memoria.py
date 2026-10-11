"""A memória do Jarvis: o que o Léo pediu para ele lembrar.

**Um arquivo de texto, um fato por linha** (`memoria.txt`, na raiz). É o
`atalhos.toml` desta função: o Léo abre, lê, corrige e apaga à mão, sem
mexer em código. Linha começando com `#` é comentário. O arquivo é lido de
novo a cada uso, então editar com o Jarvis ligado vale na hora.

Três caminhos:

- **"lembra que X"** guarda X como foi dito. Lista fechada de começos de
  frase, antes do modelo: guardar é mecânico, e o modelo só teria chance de
  reescrever o que o Léo disse.
- **"esquece que X"** acha o fato mais parecido e PERGUNTA antes de apagar
  (§2.3: apagar memória destrói uma coisa).
- **Pergunta que nenhuma função atende** vai ao modelo com os fatos e a hora
  na mesa. Ele responde só com o que está ali; não sabendo, diz que não sabe.
"""

from __future__ import annotations

import difflib
import os
import re
from pathlib import Path

from .atalhos import normalizar

CABECALHO = (
    "# Memória do Jarvis: um fato por linha, do jeito que você falou.\n"
    "# Pode editar e apagar à mão. Linha com # é comentário.\n"
)

# "Jarvis, lembra que…", "anota aí que…", "não esquece que…". O que vem depois
# do "que" é o fato.
_LEMBRAR = re.compile(
    r"^(?:jarvis[,\s]+)?(?:por favor[,\s]+)?"
    r"(?:lembra|lembre|lembra-se|anota|anote|guarda|guarde|grava|grave|"
    r"memoriza|memorize|salva|n[ãa]o esquece|n[ãa]o esque[çc]a)"
    r"(?:[\s,]+(?:a[íi]|pra mim|para mim|disso|isso))*"
    r"(?:[\s,]+(?:de|da|do))?[\s,]+que[\s,]+(.+)$",
    re.IGNORECASE,
)
_ESQUECER = re.compile(
    r"^(?:jarvis[,\s]+)?(?:pode[\s,]+)?"
    r"(?:esquecer|esquece|esque[çc]a|apaga|apague|tira)"
    r"(?:[\s,]+(?:a[íi]|da (?:tua |sua )?mem[óo]ria))*"
    r"(?:[\s,]+(?:de|disso))?[\s,]+(?:que|o fato de que|aquilo de que)[\s,]+(.+)$",
    re.IGNORECASE,
)


def _limpar(fato: str) -> str:
    fato = fato.strip().strip(".!?,; ").strip()
    return fato[:1].upper() + fato[1:] if fato else ""


def pedido_de_lembrar(falado: str) -> str | None:
    m = _LEMBRAR.match(falado.strip())
    return _limpar(m.group(1)) if m else None


def pedido_de_esquecer(falado: str) -> str | None:
    m = _ESQUECER.match(falado.strip())
    return _limpar(m.group(1)) if m else None


class Memoria:
    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)

    def fatos(self) -> list[str]:
        try:
            linhas = self.caminho.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        return [l.strip() for l in linhas if l.strip() and not l.lstrip().startswith("#")]

    def guardar(self, fato: str) -> bool:
        """Acrescenta no fim. False se já sabia (não duplica)."""
        if any(normalizar(f) == normalizar(fato) for f in self.fatos()):
            return False
        novo = not self.caminho.exists()
        with open(self.caminho, "a", encoding="utf-8") as arq:
            if novo:
                arq.write(CABECALHO)
            arq.write(fato.replace("\n", " ") + "\n")
        return True

    def mais_parecido(self, falado: str) -> str | None:
        """O fato que mais se parece com o que ele mandou esquecer.

        Por palavras em comum, não por letra: "esquece que eu tenho um gato"
        tem que achar "Eu tenho um gato chamado Bolinha".
        """
        alvo = set(normalizar(falado).split())
        melhor, nota_melhor = None, 0.0
        for fato in self.fatos():
            palavras = set(normalizar(fato).split())
            if not palavras or not alvo:
                continue
            comuns = len(alvo & palavras) / len(alvo)
            letras = difflib.SequenceMatcher(None, normalizar(falado), normalizar(fato)).ratio()
            nota = max(comuns, letras)
            if nota > nota_melhor:
                melhor, nota_melhor = fato, nota
        return melhor if nota_melhor >= 0.6 else None

    def esquecer(self, fato: str) -> bool:
        """Tira a linha exata. Reescreve por arquivo temporário: um corte no
        meio não pode deixar a memória pela metade."""
        try:
            linhas = self.caminho.read_text(encoding="utf-8").splitlines(keepends=True)
        except FileNotFoundError:
            return False
        restantes = [l for l in linhas if l.strip() != fato]
        if len(restantes) == len(linhas):
            return False
        temp = self.caminho.with_suffix(".tmp")
        temp.write_text("".join(restantes), encoding="utf-8")
        os.replace(temp, self.caminho)
        return True
