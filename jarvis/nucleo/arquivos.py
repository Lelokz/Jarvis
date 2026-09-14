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
import shutil
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


def _proibido(real: Path, regras) -> bool:
    """Se o caminho cai num buraco que a lista negra recortou.

    As três formas de veto, e cada uma existe por um achado da varredura:

      caminho    o projeto inteiro, ou uma pasta cujo conteúdo outro programa
                 localiza por caminho absoluto (o Estudio/Gravacoes)
      nome       em QUALQUER nível — `.git` e `node_modules` aparecem fundo na
                 árvore e vetar só o topo não protegeria nada
      extensão   `.desktop` em qualquer lugar, para a Área de trabalho seguir
                 liberada para arquivo de verdade
    """
    for bruto in regras.nunca_mexer:
        try:
            veto = Path(bruto).expanduser().resolve()
        except OSError:
            continue
        if real == veto or veto in real.parents:
            return True
    if set(real.parts) & set(regras.nunca_mexer_nomes):
        return True
    proibidas = {e.lower() for e in regras.nunca_mexer_extensoes}
    return real.suffix.lower() in proibidas


def pode_mexer(caminho: Path, regras) -> bool:
    """Se o caminho está liberado: dentro da branca E fora da negra.

    Resolver antes de comparar é o que fecha as duas portas dos fundos: `..`
    subindo para fora, e symlink apontando para fora. A forma da checagem é a
    mesma do `busca._sob_raiz`, que já estava escrita.

    **A negra é consultada aqui dentro, e não ao lado**, de propósito: qualquer
    código futuro que pergunte "posso mexer aqui?" já recebe as duas listas
    aplicadas. Se a negra ficasse numa checagem separada, bastaria um caminho
    novo esquecer de chamá-la para abrir um buraco em silêncio.

    **A branca é o portão, a negra recorta buracos.** A negra sempre ganha: numa
    regra que protege arquivo, previsível vale mais que flexível.
    """
    try:
        real = caminho.expanduser().resolve()
    except OSError:
        return False
    dentro = any(
        real == r or r in real.parents for r in _raizes(regras.onde_pode_mexer)
    )
    return dentro and not _proibido(real, regras)


def vetado(caminho: Path, regras) -> bool:
    """Se o caminho cai num buraco que a lista negra recortou.

    A pergunta que separa as duas formas de "não posso": *você nunca liberou
    isso* e *você vetou isso de propósito*. São recusas diferentes e levam a
    ações diferentes — a primeira é uma linha na branca, a segunda é rever um
    veto que você escreveu sabendo por quê.
    """
    try:
        return _proibido(caminho.expanduser().resolve(), regras)
    except OSError:
        return False


def _recusar_alvo(caminho: Path, regras) -> Resultado | None:
    """As recusas que valem para qualquer operação. None = pode seguir."""
    alvo = caminho.expanduser()
    if alvo.is_symlink():
        # Renomear um atalho é quase sempre engano, e decidir se a operação
        # vale para o atalho ou para o que ele aponta é ambiguidade que não
        # cabe numa confirmação falada de uma frase.
        return Resultado(False, f"{alvo.name} é um atalho. Não mexo em atalho.")
    if not alvo.exists():
        return Resultado(False, f"{alvo.name} não está mais lá.")
    if not pode_mexer(alvo, regras):
        return Resultado(
            False, "Não mexo em arquivo fora das pastas que você liberou."
        )
    return None


def renomear(caminho: Path, falado: str, regras) -> Resultado:
    """Renomeia um arquivo dentro da própria pasta.

    Só arquivo: pasta nunca é alvo. Renomear uma pasta com 3000 arquivos dentro
    é uma confirmação para 3000 consequências, e não há como ouvir o que tem lá.

    Nunca sobrescreve. Nome ocupado é o único caminho de perda silenciosa de
    dado desta etapa — a confirmação falada não pega, porque o Léo não sabe que
    havia algo com aquele nome.
    """
    alvo = caminho.expanduser()
    recusa = _recusar_alvo(alvo, regras)
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


def reverter(de: Path, para: Path, regras) -> Resultado:
    """Desfaz uma renomeação, devolvendo o nome exato que o arquivo tinha.

    Separado do `renomear` de propósito: aqui o nome não veio de fala, veio do
    disco. Passá-lo pelo `limpar_nome` poderia devolver um nome **parecido** com
    o original em vez do original, e desfazer que não desfaz exatamente é pior
    que não ter desfazer.
    """
    recusa = _recusar_alvo(de, regras)
    if recusa:
        return recusa
    if not pode_mexer(para.parent, regras):
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


def desfazer_movimento(atual: Path, pasta_anterior: Path, regras) -> Resultado:
    """Desfaz um mover levando o arquivo de volta para a pasta de onde saiu.

    **O desfazer de um mover é um mover**, e chama o `mover` mesmo. Escrever um
    caminho de volta separado seria escrever uma segunda chance de errar, com
    metade da atenção — e é o caminho de volta que ninguém testa. Chamando o
    original vêm juntas a invariante (o original nunca some antes de a cópia
    verificada existir) e a travessia entre discos, que é justamente o caso em
    que um segundo caminho erraria.

    A revalidação também vem de graça, e é a que o Léo pediu: o `_preparar`
    confere que o arquivo ainda está onde o registro diz, que o nome antigo
    está livre na pasta antiga, e que os dois lados continuam passando pelo
    portão. Renomeou o arquivo depois de mover? Ele diz que não achou mais, em
    vez de mexer no que não devia.
    """
    r = mover(atual, pasta_anterior, regras)
    if not r.ok:
        return r
    return Resultado(
        True,
        f"Voltei {falar_nome(atual)} para {pasta_anterior.name}.",
        r.detalhe,
    )


# Até onde descer procurando pasta de destino. Medido no território real do
# Léo: 160 pastas em ~0,1s varrendo tudo, então a profundidade não é o gargalo
# — o teto existe só para uma árvore futura não virar surpresa.
FUNDO_DO_DESTINO = 4


def destinos_possiveis(regras) -> list[Path]:
    """Todas as pastas onde o Léo pode pôr um arquivo, enumeradas AGORA.

    **É isto que mata o problema do `plocate`.** O índice dele atualiza uma vez
    por dia, então "cria a pasta X e move isso pra lá" — o fluxo mais natural que
    existe — quebrava: a pasta tinha dois segundos de idade e o índice não a
    conhecia. Era o que a Etapa 5 tinha adiado.

    A saída não foi consertar o índice, foi não precisar dele: **todo destino é
    uma pasta**, e pasta dentro do território liberado dá para listar na hora.
    Medido no disco real do Léo: 160 pastas em ~0,1s. Uma pasta criada agora
    aparece, porque a resposta é o disco e não um cache.

    O `plocate` continua servindo para achar o **arquivo** de origem, que é o que
    ele faz bem.
    """
    achadas: list[Path] = []
    for raiz in _raizes(regras.onde_pode_mexer):
        if pode_mexer(raiz, regras):
            achadas.append(raiz)
        for atual, subpastas, _ in os.walk(raiz):
            aqui = Path(atual)
            if len(aqui.relative_to(raiz).parts) >= FUNDO_DO_DESTINO:
                subpastas.clear()
                continue
            # Poda na descida: não entra no que a negra vetou. Sem isto a
            # varredura desceria em node_modules, que é onde está o volume.
            subpastas[:] = [
                s for s in subpastas if pode_mexer(aqui / s, regras)
            ]
            achadas.extend(aqui / s for s in subpastas)
    return achadas


def casar_destino(falado: str, regras) -> list[Path]:
    """As pastas cujo NOME casa com o que ele falou.

    Casamento pelo nome normalizado, não pelo caminho: o Léo diz "pra
    documentos", não "para barra home barra lelokz barra Documentos". Usa o
    mesmo `normalizar()` dos atalhos, então acento, caixa e pontuação do Whisper
    convergem de graça.

    Devolve tudo que casou — quem chama pergunta quando é mais de um, que é a
    §2.2. Lista vazia significa que **nenhuma pasta liberada** tem esse nome, o
    que não é a mesma coisa que a pasta não existir: quem precisa da diferença
    chama o `explicar_destino`.
    """
    chave = normalizar(falado)
    if not chave:
        return []
    exatas = [d for d in destinos_possiveis(regras) if normalizar(d.name) == chave]
    if exatas:
        return exatas
    # Nada exato: aceita a pasta cujo nome CONTÉM o que ele falou. É o que faz
    # "senai" achar "SENAI-2026" sem precisar que ele diga o nome inteiro.
    return [d for d in destinos_possiveis(regras) if chave in normalizar(d.name)]


# Até onde descer para EXPLICAR uma recusa. Dois níveis, não os quatro do
# destino, e o número saiu da medição: varrer a home inteira a quatro níveis
# custa 1,49s e a dois custa 0,07s. Dois já alcançam tudo que precisa ser
# explicado — `~/Jogos` é nível 1, `~/Projetos/Jarvis` e `Estudio/Gravacoes`
# são nível 2. Esta varredura só roda quando a resposta já vai ser "não", e
# nunca no caminho de agir.
FUNDO_DA_EXPLICACAO = 2

# Nomes que o Léo fala e que não são o `.name` de pasta nenhuma. "Home" é o
# caso real: no disco ela se chama "lelokz", e ninguém diz isso em voz alta.
#
# Só é consultado DEPOIS de a varredura não achar nada, então uma pasta de
# verdade chamada "Casa" continua ganhando desta lista.
_APELIDOS_DA_HOME = ("home", "casa", "minha pasta", "pasta pessoal")


def _territorio(regras) -> list[Path]:
    """As pastas-mãe de onde a lista branca recortou as raízes liberadas.

    `~/Downloads` e `~/Projetos` vêm da home; `Midia` e `Estudio` vêm do ponto
    de montagem do HD. Então o território é `{~, /mnt/<hd>}` — o lugar exato
    onde estão as pastas que ele conhece e que a branca não liberou.
    """
    maes: list[Path] = []
    for raiz in _raizes(regras.onde_pode_mexer):
        if raiz.parent not in maes:
            maes.append(raiz.parent)
    return maes


def explicar_destino(falado: str, regras) -> tuple[str, str] | None:
    """Por que o destino não casou: ele não existe, ou existe e é proibido?

    **"Não existe" e "não posso" são fatos diferentes, e dizer um pelo outro
    manda o Léo procurar problema onde não tem.** Foi o que aconteceu com
    "move a pasta legal para a Home": a recusa estava certa — a home não está
    liberada, só as pastas dentro dela — mas a frase dizia que ela não existe.

    É a mesma imprecisão do `arquivo_fora_da_lista`, corrigida na rodada
    passada: a mensagem descrevendo o estado interno em vez do que ele pediu.

    Devolve `(motivo, nome)` com motivo em `"fora_da_branca"` ou `"vetada"`, ou
    `None` quando a pasta realmente não existe em lugar nenhum visível.
    """
    chave = normalizar(falado)
    if not chave:
        return None

    candidatas: list[Path] = []
    for mae in _territorio(regras):
        candidatas.append(mae)
        for atual, subpastas, _ in os.walk(mae):
            aqui = Path(atual)
            if len(aqui.relative_to(mae).parts) >= FUNDO_DA_EXPLICACAO:
                subpastas.clear()
                continue
            candidatas.extend(aqui / s for s in subpastas)

    for pasta in candidatas:
        nome = normalizar(pasta.name)
        if (nome == chave or chave in nome) and not pode_mexer(pasta, regras):
            motivo = "vetada" if vetado(pasta, regras) else "fora_da_branca"
            return motivo, pasta.name

    if chave in _APELIDOS_DA_HOME and not pode_mexer(Path.home(), regras):
        # O nome falável aqui é o que ELE disse, não "lelokz".
        return "fora_da_branca", falado.strip()

    return None


def _copiar_verificando(origem: Path, destino: Path) -> Resultado:
    """Copia para um nome temporário, confere o tamanho, e só então nomeia.

    Esta função existe por causa da travessia entre discos. `~/Downloads` e o HD
    são sistemas de arquivos diferentes — conferido, `st_dev` 2066 contra 2050 —
    e `os.rename` entre eles dá EXDEV. Então mover para o HD é copiar e apagar,
    que não é atômico e pode falhar pela metade. O HD está com 30 GB livres de
    293, ou seja: disco cheio não é hipótese.

    **O nome temporário é o ponto.** Copiando direto para o nome final, uma
    falha no meio deixa um arquivo com o nome certo e o conteúdo truncado — que
    parece pronto e não é. Com o nome temporário, o que sobra é obviamente lixo
    e é removido.

    A conferência é de **tamanho**, byte a byte, e não de hash. Decisão do Léo:
    hash seria ler 5 GB duas vezes num HD mecânico, minutos de espera para
    proteger contra um caso que praticamente não acontece; tamanho pega os dois
    que acontecem, cópia truncada e disco cheio.
    """
    parcial = destino.parent / f".jarvis-parcial-{destino.name}"
    esperado = origem.stat().st_size
    try:
        shutil.copyfile(origem, parcial)
        if parcial.stat().st_size != esperado:
            raise OSError(
                f"copiou {parcial.stat().st_size} de {esperado} bytes"
            )
        os.rename(parcial, destino)  # mesmo disco: atômico
    except OSError as e:
        # Falhou em qualquer ponto: o parcial vira lixo e sai. O ORIGINAL FICA.
        try:
            parcial.unlink(missing_ok=True)
        except OSError:
            pass
        return Resultado(False, f"Não consegui copiar: {e}")
    return Resultado(True, "", {"bytes": esperado})


def _preparar(caminho: Path, destino_pasta: Path, regras) -> Resultado | Path:
    """As recusas que mover e copiar têm em comum. Devolve o caminho de destino.

    Origem e destino passam os dois pelo portão. Não basta a origem estar
    liberada: mover para dentro de um buraco da negra seria o mesmo estrago
    pelo outro lado.
    """
    alvo = caminho.expanduser()
    recusa = _recusar_alvo(alvo, regras)
    if recusa:
        return recusa
    if alvo.is_dir():
        return Resultado(False, f"{alvo.name} é uma pasta. Só mexo em arquivo.")

    pasta = destino_pasta.expanduser()
    if not pasta.is_dir():
        return Resultado(False, f"A pasta {pasta.name} não existe.")
    if not pode_mexer(pasta, regras):
        return Resultado(False, "Não mexo em arquivo fora das pastas que você liberou.")

    destino = pasta / alvo.name
    if destino == alvo:
        return Resultado(False, f"{falar_nome(alvo)} já está em {pasta.name}.")
    if destino.exists():
        return Resultado(
            False, f"Já tem um {falar_nome(destino)} em {pasta.name}. Não sobrescrevo."
        )
    return destino


def mover(caminho: Path, destino_pasta: Path, regras) -> Resultado:
    """Leva o arquivo para outra pasta, com o mesmo nome.

    **A invariante: o original nunca é apagado antes de a cópia verificada
    existir.** No mesmo disco isso é de graça, porque `os.rename` é atômico —
    ou aconteceu, ou não aconteceu. Entre discos é o `_copiar_verificando`.
    """
    pronto = _preparar(caminho, destino_pasta, regras)
    if isinstance(pronto, Resultado):
        return pronto
    alvo, destino = caminho.expanduser(), pronto

    mesmo_disco = alvo.stat().st_dev == destino.parent.stat().st_dev
    if mesmo_disco:
        try:
            os.rename(alvo, destino)
        except OSError as e:
            return Resultado(False, f"Não consegui mover: {e}")
    else:
        r = _copiar_verificando(alvo, destino)
        if not r.ok:
            return r
        try:
            alvo.unlink()
        except OSError as e:
            # A cópia está boa e verificada; só o original resistiu. Dizer a
            # verdade é melhor que dizer "movi" com o arquivo ainda nos dois
            # lugares.
            return Resultado(
                False,
                f"Copiei {falar_nome(destino)} para {destino.parent.name}, "
                f"mas não consegui apagar o original: {e}",
                {"de": str(alvo), "para": str(destino), "original_ficou": True},
            )

    return Resultado(
        True,
        f"Movi {falar_nome(destino)} para {destino.parent.name}.",
        {"de": str(alvo), "para": str(destino), "mesmo_disco": mesmo_disco},
    )


def copiar(caminho: Path, destino_pasta: Path, regras) -> Resultado:
    """A versão que não destrói nada: o original fica onde está.

    Mesmo caminho do mover, menos o último passo. Vale até no mesmo disco:
    `os.rename` não serve para copiar.
    """
    pronto = _preparar(caminho, destino_pasta, regras)
    if isinstance(pronto, Resultado):
        return pronto
    alvo, destino = caminho.expanduser(), pronto

    r = _copiar_verificando(alvo, destino)
    if not r.ok:
        return r
    return Resultado(
        True,
        f"Copiei {falar_nome(destino)} para {destino.parent.name}.",
        {"de": str(alvo), "para": str(destino)},
    )


def criar_pasta(falado: str, dentro_de: Path, regras) -> Resultado:
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
    if not pode_mexer(pai, regras):
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
