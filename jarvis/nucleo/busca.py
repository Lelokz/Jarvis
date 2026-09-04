"""Procurar arquivos e pastas no disco.

O ESCOPO resume a etapa numa frase: *"O Jarvis não precisa saber onde as coisas
ficam. Ele precisa saber procurar."*

O problema não é achar — é achar **pouco**. Medido antes de escrever isto:
procurar "config" no `plocate` devolve 6382 resultados, 1317 na home, e 617
deles estão dentro de `node_modules`, `.venv` e `site-packages`. Nenhuma
quantidade de desambiguação por voz salva uma lista desse tamanho. Por isso o
escopo e as exclusões do `config.toml` não são enfeite: são o que torna a busca
usável.

Duas fontes, nesta ordem:

  `plocate`  índice do sistema, instantâneo — mas atualizado uma vez por dia,
             então arquivo baixado hoje pode não estar lá
  `find`     rede de segurança: só roda quando o plocate não achou nada, só nas
             raízes configuradas, e com prazo para não travar a conversa
"""

from __future__ import annotations

import os
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ..config import Busca as ConfigBusca
from .atalhos import normalizar


@dataclass(frozen=True)
class Achado:
    caminho: Path
    pasta: str  # nome da pasta que o contém — é isto que se fala em voz alta

    @property
    def nome(self) -> str:
        return self.caminho.name

    @property
    def e_pasta(self) -> bool:
        return self.caminho.is_dir()


def _sem_acento(texto: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )


def _nome_falavel(caminho: Path) -> str:
    """O nome do arquivo como ele seria falado: separadores viram espaço."""
    texto = _sem_acento(caminho.stem)
    for sep in ("_", "-", ".", "+"):
        texto = texto.replace(sep, " ")
    return " ".join(texto.split())


def _todas_no_nome(palavras: list[str], caminho: Path) -> bool:
    nome = _nome_falavel(caminho)
    return all(p in nome for p in palavras)


class Buscador:
    def __init__(self, cfg: ConfigBusca) -> None:
        self.cfg = cfg
        # Raiz inexistente é pulada em silêncio: o HD externo só entra quando
        # estiver montado, e não ter ele ligado não é erro.
        self.raizes = [
            p for p in (Path(r).expanduser() for r in cfg.raizes) if p.is_dir()
        ]
        self._ignorar = [_sem_acento(i) for i in cfg.ignorar]
        self.ultimo_diagnostico: dict = {}

    # ----------------------------------------------------------------------

    def _sob_raiz(self, caminho: Path) -> bool:
        return any(
            caminho == raiz or raiz in caminho.parents for raiz in self.raizes
        )

    def _aceitar(self, caminho: Path) -> bool:
        """Está sob alguma raiz e fora de tudo que mandamos ignorar?"""
        texto = _sem_acento(str(caminho))
        if any(f"/{ig}/" in texto or texto.endswith(f"/{ig}") for ig in self._ignorar):
            return False
        return self._sob_raiz(caminho)

    def _ordenar(self, caminhos: list[Path], termo: str) -> list[Path]:
        """Nome exato primeiro, depois caminho mais raso, depois alfabético.

        A ordem importa pouco enquanto sobrar mais de um — quem escolhe é o
        Léo, filtrando. Mas ela tem que ser estável, para a mesma pergunta dar
        sempre a mesma resposta.
        """
        alvo = _sem_acento(termo)

        def chave(p: Path):
            base = _sem_acento(p.stem)
            return (base != alvo, len(p.parts), str(p).lower())

        return sorted(caminhos, key=chave)

    # ----------------------------------------------------------------------

    def _plocate(self, termo: str) -> list[Path]:
        try:
            saida = subprocess.run(
                ["plocate", "-i", "--basename", termo],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        # O plocate devolve 1 quando não acha nada — não é erro.
        return [Path(l) for l in saida.stdout.splitlines() if l]

    def _find(self, termo: str) -> list[Path]:
        """A rede de segurança, para o arquivo que o índice ainda não viu."""
        achados: list[Path] = []
        for raiz in self.raizes:
            comando = ["find", str(raiz), "-iname", f"*{termo}*"]
            for ig in self.cfg.ignorar:
                comando += ["-not", "-path", f"*/{ig}/*"]
            try:
                saida = subprocess.run(
                    comando,
                    capture_output=True,
                    text=True,
                    timeout=self.cfg.segundos_find,
                )
                achados += [Path(l) for l in saida.stdout.splitlines() if l]
            except (OSError, subprocess.TimeoutExpired):
                # Estourou o prazo: devolve o que já tem em vez de nada.
                continue
        return achados

    # ----------------------------------------------------------------------

    def buscar(self, termo: str) -> list[Achado]:
        termo = termo.strip()
        if not termo or not self.raizes:
            return []

        # Falado tem espaço, arquivo tem underscore ou hífen: "experimento stt"
        # precisa achar `experimento_stt.py`. Então buscamos pela palavra mais
        # distintiva e exigimos que todas apareçam no nome, com os separadores
        # tratados como espaço. Sem isto, quase toda busca de nome com mais de
        # uma palavra falharia.
        palavras = [p for p in _sem_acento(termo).split() if p]
        chave = max(palavras, key=len) if palavras else termo

        def coletar(fonte, rotulo: str) -> list[Path]:
            crus = fonte(chave)
            sob_raiz = [p for p in crus if self._sob_raiz(p)]
            aceitos = [p for p in sob_raiz if self._aceitar(p)]
            filtrados = aceitos
            if len(palavras) > 1:
                filtrados = [p for p in aceitos if _todas_no_nome(palavras, p)]
            # Guardado para o log: sem estas contagens, investigar por que uma
            # busca não achou nada exige reproduzir a sessão inteira.
            self.ultimo_diagnostico = {
                "fonte": rotulo,
                "termo": termo,
                "chave": chave,
                "cru": len(crus),
                "apos_raizes": len(sob_raiz),
                "apos_exclusoes": len(aceitos),
                "apos_palavras": len(filtrados),
            }
            return filtrados

        caminhos = coletar(self._plocate, "plocate")
        # A rede só vale se for lançada quando não sobrou nada **depois** de
        # filtrar. O plocate pode devolver vinte arquivos e o filtro de
        # palavras descartar todos — foi o que aconteceu com "experimento stt",
        # criado depois do último updatedb: o índice trazia os irmãos dele, o
        # filtro os cortava, e o `find` nunca era chamado.
        if not caminhos:
            caminhos = coletar(self._find, "find")

        # Um caminho no índice pode já ter sido apagado desde o último updatedb.
        vistos: set[Path] = set()
        existentes = []
        for p in self._ordenar(caminhos, termo):
            if p not in vistos and p.exists():
                vistos.add(p)
                existentes.append(p)
            if len(existentes) >= self.cfg.max_resultados:
                break

        return [Achado(caminho=p, pasta=p.parent.name or "/") for p in existentes]

    def estreitar(self, achados: list[Achado], filtro: str) -> list[Achado]:
        """Aplica a pista que o Léo deu sobre onde a coisa está.

        Casa contra o caminho inteiro sem acento, então "gravações", "gravacoes"
        e "hd" funcionam igual. Palavras soltas são exigidas todas: "projeto
        loft" só casa quem tiver as duas.
        """
        # `normalizar()` — o mesmo do resto do núcleo — em vez do
        # `_sem_acento` local: aquele não tirava pontuação, e o Whisper
        # pontua. "Download." procurava literalmente `download.`, com ponto,
        # e nunca casava com nada. Era por isso que "Achei 90. Em qual pasta?"
        # nunca estreitava.
        palavras = [p for p in normalizar(filtro).split() if len(p) > 1]
        if not palavras:
            return achados
        return [
            a
            for a in achados
            if all(p in normalizar(str(a.caminho)) for p in palavras)
        ]


def pastas_que_distinguem(achados: list[Achado]) -> list[str]:
    """As pastas diferentes entre os candidatos — o mínimo para escolher.

    Falar `/home/lelokz/Projetos/Loft/docs/nota.md` em voz alta é impossível.
    Com poucos candidatos, dizer só a pasta de cada um já é a pergunta "qual?".

    Se as pastas não distinguirem — dois `jarvis/` que só diferem por
    maiúscula, por exemplo — sobe um nível até dar. Dizer "um em Jarvis, outro
    em jarvis" não ajuda ninguém a escolher.
    """
    for nivel in range(1, 4):
        vistas: list[str] = []
        for a in achados:
            partes = a.caminho.parent.parts[-nivel:]
            rotulo = "/".join(partes) or "/"
            if rotulo.lower() not in [v.lower() for v in vistas]:
                vistas.append(rotulo)
        if len(vistas) == len({v.lower() for v in vistas}) and len(vistas) > 1:
            return vistas
    return vistas
