"""Mexer em arquivo. A primeira coisa no projeto que pode destruir dado.

Até a Etapa 4, errar significava abrir a coisa errada — custo zero, é só
fechar. Aqui, errar significa perder arquivo. Este módulo existe para que o
caminho entre a fala do Léo e o disco tenha o máximo de recusas possível.

**O modelo nunca chega perto daqui**, igual ao `acoes.py`. Ele devolve uma
string; quem decide se ela vira operação é este arquivo, contra uma lista
branca que o Léo escreveu no `config.toml`. E não há `subprocess`: renomear é
`os.rename`, direto. Não existe razão para um shell existir perto de código que
mexe em arquivo (§2.1).

**Não há código de apagar neste módulo, nem em nenhum outro do núcleo.** A §2.4
não é respeitada por disciplina — é respeitada por ausência. A lixeira, que a
§2.4 permite como teto, entra só depois da Etapa 5.5.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .atalhos import normalizar

# Nome de arquivo mais longo que isto o ext4 recusa (255 bytes). O corte é em
# caracteres e bem abaixo do limite, porque acento em UTF-8 ocupa dois bytes e
# ninguém fala um nome de 200 letras.
MAX_NOME = 120

# Sufixo que conta como extensão dita pelo Léo. Só letras, de propósito: um
# arquivo "versão 2.5 do relatório" renomeado para "versão 2.5" terminaria em
# ".5", e tratar isso como extensão apagaria o .pdf de verdade.
MAX_EXTENSAO = 5


@dataclass(frozen=True)
class Resultado:
    ok: bool
    mensagem: str  # o que dizer ao Léo
    detalhe: dict | None = None  # para o log da §2.5


# Palavras que APONTAM sem nomear. O modelo às vezes preenche o campo do alvo
# com elas em vez de deixar vazio — medido em "Renomeia esse aí.", que devolveu
# alvo='esse aí'. Procurar isso no disco não acha nada e faz o Jarvis responder
# "não achei nada chamado esse aí", que manda o Léo repetir um nome que ele
# nunca disse. O certo é perguntar qual arquivo.
#
# Lista fechada de propósito, igual ao _SUPERFLUAS do atalhos.py: é limpeza
# mecânica de português, não julgamento — não é trabalho para o modelo.
APONTAM_SEM_NOMEAR = frozenset(
    {
        "esse", "essa", "este", "esta", "isso", "aquele", "aquela", "aquilo",
        "ele", "ela", "arquivo", "aquivo",
    }
)


def aponta_sem_nomear(falado: str) -> bool:
    """Se o que ele disse só aponta, sem dizer qual arquivo é."""
    palavras = normalizar(falado).split()
    extras = {"ai", "la", "aqui"}  # "esse aí", "aquele lá"
    return bool(palavras) and all(
        p in APONTAM_SEM_NOMEAR or p in extras for p in palavras
    )


def falar_nome(caminho: Path) -> str:
    """O nome do arquivo como ele deve ser FALADO na confirmação.

    Separadores viram espaço: `relatorio_final_v2.pdf` → "relatorio final v2".
    Sem isso o Piper soletra o underscore, e o §7 já registra que ele lê mal
    texto que não é frase corrida.

    **Não reusa o `_nome_falavel` da busca**, que parece igual e não serve: lá
    ele tira acento, porque existe para CASAR texto. Aqui o texto vai ser
    falado em voz alta, e "coracao" e "coração" são a mesma palavra para o
    casamento e não para o Piper.
    """
    texto = caminho.stem
    for sep in ("_", "-", ".", "+"):
        texto = texto.replace(sep, " ")
    return " ".join(texto.split()) or caminho.name


def limpar_nome(falado: str) -> str:
    """Transforma o que o Whisper entregou num nome de arquivo utilizável.

    Devolve "" quando não sobra nada aproveitável — quem chama tem que
    perguntar de novo, nunca inventar.

    O que isto tira, e por quê:
      - `/` e `\\0`, os dois únicos caracteres que o Linux proíbe num nome
      - o ponto final da frase, que o Whisper põe em tudo: "Proposta comercial."
        viraria "proposta comercial..pdf"
      - pontos no começo, que esconderiam o arquivo sem ninguém pedir
    """
    texto = falado.strip().replace("/", " ").replace("\0", "")
    texto = " ".join(texto.split())
    texto = texto.strip(". ")
    return texto[:MAX_NOME].strip()


def _disse_extensao(nome: str) -> bool:
    """Se o nome falado já termina numa extensão que o Léo disse."""
    sufixo = Path(nome).suffix
    return bool(sufixo) and sufixo[1:].isalpha() and len(sufixo) - 1 <= MAX_EXTENSAO


def nome_final(caminho: Path, falado: str) -> str:
    """O nome que o arquivo VAI ter. Uma fonte só para a confirmação e para a
    execução — se a frase falada e o `os.rename` calculassem isto separado,
    algum dia divergiriam, e a confirmação passaria a confirmar outra coisa.

    Devolve "" quando não sobra nome aproveitável.
    """
    limpo = limpar_nome(falado)
    if not limpo:
        return ""
    return limpo if _disse_extensao(limpo) else limpo + caminho.suffix


def _raizes(onde_pode_mexer: list[str]) -> list[Path]:
    """As raízes da lista branca, resolvidas. Raiz inexistente é ignorada."""
    raizes = []
    for bruto in onde_pode_mexer:
        try:
            raiz = Path(bruto).expanduser().resolve()
        except OSError:
            continue
        if raiz.is_dir():
            raizes.append(raiz)
    return raizes


def pode_mexer(caminho: Path, onde_pode_mexer: list[str]) -> bool:
    """Se o caminho está dentro da lista branca, já resolvido.

    Resolver antes de comparar é o que fecha as duas portas dos fundos: `..`
    subindo para fora, e symlink apontando para fora. A forma da checagem é a
    mesma do `busca._sob_raiz`, que já estava escrita.
    """
    try:
        real = caminho.expanduser().resolve()
    except OSError:
        return False
    return any(real == r or r in real.parents for r in _raizes(onde_pode_mexer))


def _recusar_alvo(caminho: Path, onde_pode_mexer: list[str]) -> Resultado | None:
    """As recusas que valem para qualquer operação. None = pode seguir."""
    alvo = caminho.expanduser()
    if alvo.is_symlink():
        # Renomear um atalho é quase sempre engano, e decidir se a operação
        # vale para o atalho ou para o que ele aponta é ambiguidade que não
        # cabe numa confirmação falada de uma frase.
        return Resultado(False, f"{alvo.name} é um atalho. Não mexo em atalho.")
    if not alvo.exists():
        return Resultado(False, f"{alvo.name} não está mais lá.")
    if not pode_mexer(alvo, onde_pode_mexer):
        return Resultado(
            False, "Não mexo em arquivo fora das pastas que você liberou."
        )
    return None


def renomear(caminho: Path, falado: str, onde_pode_mexer: list[str]) -> Resultado:
    """Renomeia um arquivo dentro da própria pasta.

    Só arquivo: pasta nunca é alvo. Renomear uma pasta com 3000 arquivos dentro
    é uma confirmação para 3000 consequências, e não há como ouvir o que tem lá.

    Nunca sobrescreve. Nome ocupado é o único caminho de perda silenciosa de
    dado desta etapa — a confirmação falada não pega, porque o Léo não sabe que
    havia algo com aquele nome.
    """
    alvo = caminho.expanduser()
    recusa = _recusar_alvo(alvo, onde_pode_mexer)
    if recusa:
        return recusa
    if alvo.is_dir():
        return Resultado(False, f"{alvo.name} é uma pasta. Só renomeio arquivo.")

    # A extensão é preservada sozinha. Arquivo sem extensão para de abrir, e é
    # uma quebra silenciosa: o nome fica certo e o arquivo não funciona.
    nome_novo = nome_final(alvo, falado)
    if not nome_novo:
        return Resultado(False, "Não entendi o nome novo.")
    destino = alvo.parent / nome_novo

    if destino == alvo:
        return Resultado(False, f"Já se chama {falar_nome(alvo)}.")
    if destino.exists():
        return Resultado(
            False, f"Já tem um {falar_nome(destino)} nessa pasta. Não sobrescrevo."
        )

    try:
        os.rename(alvo, destino)
    except OSError as e:
        return Resultado(False, f"Não consegui renomear: {e}")

    return Resultado(
        True,
        f"Renomeei para {falar_nome(destino)}.",
        {"de": str(alvo), "para": str(destino)},
    )


def reverter(de: Path, para: Path, onde_pode_mexer: list[str]) -> Resultado:
    """Desfaz uma renomeação, devolvendo o nome exato que o arquivo tinha.

    Separado do `renomear` de propósito: aqui o nome não veio de fala, veio do
    disco. Passá-lo pelo `limpar_nome` poderia devolver um nome **parecido** com
    o original em vez do original, e desfazer que não desfaz exatamente é pior
    que não ter desfazer.
    """
    recusa = _recusar_alvo(de, onde_pode_mexer)
    if recusa:
        return recusa
    if not pode_mexer(para.parent, onde_pode_mexer):
        return Resultado(False, "Não mexo em arquivo fora das pastas que você liberou.")
    if para.exists():
        return Resultado(
            False, f"Já tem um {falar_nome(para)} nessa pasta. Não sobrescrevo."
        )
    try:
        os.rename(de.expanduser(), para)
    except OSError as e:
        return Resultado(False, f"Não consegui desfazer: {e}")
    return Resultado(
        True, f"Voltei para {falar_nome(para)}.", {"de": str(de), "para": str(para)}
    )


def criar_pasta(falado: str, dentro_de: Path, onde_pode_mexer: list[str]) -> Resultado:
    """Cria uma pasta. É a única operação da etapa que não destrói nada.

    Por isso age sem confirmação falada: a §2.3 pede confirmação para mover,
    renomear, sobrescrever e apagar, e criar não está na lista. Confirmar tudo
    treinaria o Léo a dizer "pode" no reflexo, e isso enfraquece a confirmação
    justamente onde ela importa.
    """
    pai = dentro_de.expanduser()
    if not pai.exists():
        return Resultado(False, f"A pasta {pai.name} não existe.")
    if not pai.is_dir():
        return Resultado(False, f"{pai.name} não é uma pasta.")
    if not pode_mexer(pai, onde_pode_mexer):
        return Resultado(False, "Não crio pasta fora das pastas que você liberou.")

    limpo = limpar_nome(falado)
    if not limpo:
        return Resultado(False, "Não entendi o nome da pasta.")

    nova = pai / limpo
    if nova.exists():
        return Resultado(False, f"Já tem um {limpo} em {pai.name}.")

    try:
        nova.mkdir()
    except OSError as e:
        return Resultado(False, f"Não consegui criar a pasta: {e}")

    return Resultado(True, f"Criei {limpo} em {pai.name}.", {"criada": str(nova)})
