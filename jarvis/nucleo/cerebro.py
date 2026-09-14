"""O LLM local, via Ollama. Só decide; não executa nada.

Duas perguntas, e só estas duas:

  `interpretar(frase)`  → chamou `abrir`? com que nome?
  `confirmar(frase)`    → isso foi um sim, um não, ou outra coisa?

A segunda existe porque a Etapa 0.6 deixou de fora entender sim/não —
justamente por não haver modelo ainda. Agora há, e ela não é uma lista de
palavras chumbada: esse atalho brigaria com o modelo depois, e foi vetado.

**A lista de nomes vai no prompt**, decidido com número no experimento da Fase 1:
70% contra 60% de resolução direta e 0,49s contra 0,91s de latência, com muito
menos variação. A tabela continua sendo a fonte da verdade e o casamento em
Python continua validando — o prompt só ajuda o modelo a extrair o nome já
perto da forma canônica.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum, auto

import requests

from ..config import Llm as ConfigLlm

FERRAMENTA_ABRIR = {
    "type": "function",
    "function": {
        "name": "abrir",
        "description": (
            "Abre uma coisa no computador do usuário: um site, uma pasta ou um "
            "projeto. Use também quando ele pedir para PROCURAR uma coisa: "
            "achar e abrir são o mesmo pedido aqui, porque procurar é o passo "
            "que vem antes de abrir.\n"
            "Quem decide é o VERBO, não o assunto: 'abre', 'mostra', 'acessa', "
            "'põe na tela', 'procura', 'acha', 'encontra' e 'cadê' são abrir.\n"
            "Mas 'procura X para renomear' é `renomear`, não isto: quando ele "
            "diz o que quer FAZER com a coisa, quem manda é esse verbo.\n"
            "Para 'toca', 'reproduz' ou 'ouve', use `tocar`. Para 'pausa', "
            "'continua', 'próxima' ou 'volume', use `midia`. Para perguntas "
            "sobre o computador, use `status_pc`. Para 'marca', 'agenda' ou "
            "'me lembra', use `criar_evento`; para o que já está marcado, "
            "`agenda_do_dia`. Para 'renomeia', 'muda o nome' ou 'troca o "
            "nome', use `renomear`; para 'cria uma pasta', `criar_pasta`; "
            "para levar um arquivo para outra pasta, `mover`.\n"
            "'abre músicas' é abrir a pasta; 'toca uma música' não é abrir."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nome": {
                    "type": "string",
                    "description": (
                        "O nome da coisa que o usuário pediu para abrir, "
                        "exatamente como ele falou, sem artigos e sem verbos."
                    ),
                }
            },
            "required": ["nome"],
        },
    },
}


FERRAMENTA_TOCAR = {
    "type": "function",
    "function": {
        "name": "tocar",
        "description": (
            "Toca uma música ou vídeo. Use quando o usuário disser 'toca', "
            "'reproduz', 'ouve', 'coloca uma música' ou 'põe pra tocar'.\n"
            "Se ele não disser o nome do que quer ('toca uma música', 'coloca "
            "um som'), chame mesmo assim com `o_que` vazio — vamos perguntar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "o_que": {
                    "type": "string",
                    "description": (
                        "O nome da música, artista ou vídeo, como o usuário "
                        "falou. Vazio se ele não disse o quê."
                    ),
                },
                "onde": {
                    "type": "string",
                    "enum": ["audio", "navegador"],
                    "description": (
                        "'navegador' quando ele pedir no YouTube, no navegador "
                        "ou quiser VER o vídeo. 'audio' no resto — é o padrão."
                    ),
                },
            },
            "required": ["o_que"],
        },
    },
}

FERRAMENTA_MIDIA = {
    "type": "function",
    "function": {
        "name": "midia",
        # A versão anterior era renúncia pura — "não serve para começar a tocar
        # algo, para isso use `tocar`" — e a lição do "procura" (ESCOPO §5) diz
        # que instrução de renúncia não funciona: o modelo já decidiu pela
        # outra função quando lê o primeiro verbo. Medido: com a renúncia,
        # "Continua." e "Dá play." davam 0/5; com a reivindicação abaixo, 5/5
        # nas duas, e "Para a música." parou de virar `tocar` — que era ação
        # errada, pior que não entender.
        "description": (
            "Controla o que JÁ está tocando, seja música, vídeo ou o som de um "
            "jogo.\n"
            "É ISTO que você usa quando ele manda parar, seguir ou pular o que "
            "já está tocando: 'para', 'pare', 'para a música', 'pode parar', "
            "'pausa', 'continua', 'pode continuar', 'dá play', 'segue', "
            "'próxima', 'pula essa', 'anterior'. Mandar PARAR ou SEGUIR o que "
            "toca é SEMPRE `midia`, nunca `tocar` — inclusive 'para a música', "
            "que é pausar e não começar.\n"
            "'dar play' é SEMPRE continuar o que está pausado, em qualquer "
            "forma que ele fale: 'dá play', 'pode dar play', 'tu pode dar "
            "play?'. Nunca é volume.\n"
            "VOLUME também é isto, e nada mais: 'abaixa o volume', 'abaixa o "
            "som', 'aumenta o volume', 'diminui', 'sobe o som', 'volume 30', "
            "'muta'. 'abaixa' e 'baixa' falando de som são SEMPRE volume — "
            "nunca têm a ver com mover ou copiar arquivo.\n"
            "Só é `tocar` quando ele disser O QUE quer que comece a tocar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "acao": {
                    "type": "string",
                    "enum": [
                        "pausar",
                        "continuar",
                        "proxima",
                        "anterior",
                        "volume",
                    ],
                    "description": "O que fazer com o que está tocando.",
                },
            },
            "required": ["acao"],
        },
    },
}

FERRAMENTA_STATUS = {
    "type": "function",
    "function": {
        "name": "status_pc",
        "description": (
            "Responde sobre o estado do computador: temperatura da placa de "
            "vídeo, quanto ela está sendo usada, memória de vídeo. Use quando "
            "ele PERGUNTAR sobre a máquina."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}

FERRAMENTA_CRIAR_EVENTO = {
    "type": "function",
    "function": {
        "name": "criar_evento",
        "description": (
            "Marca um compromisso na agenda do usuário. Use para 'marca', "
            "'agenda', 'me lembra de', 'põe na agenda', 'cria um evento'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "titulo": {
                    "type": "string",
                    "description": (
                        "O que é o compromisso, sem a parte de tempo. "
                        "Em 'marca dentista amanhã de manhã', é 'dentista'."
                    ),
                },
                "quando": {
                    "type": "string",
                    "description": (
                        "A expressão de tempo EXATAMENTE como o usuário falou. "
                        "NÃO calcule a data. Copie: 'amanhã de manhã', "
                        "'sexta que vem às três', 'daqui a duas horas'. "
                        "Vazio se ele não disse quando."
                    ),
                },
            },
            "required": ["titulo", "quando"],
        },
    },
}

FERRAMENTA_AGENDA_DIA = {
    "type": "function",
    "function": {
        "name": "agenda_do_dia",
        "description": (
            "Diz o que o usuário já tem marcado num dia. Use para 'o que eu "
            "tenho hoje', 'o que tem amanhã', 'como está minha agenda'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "quando": {
                    "type": "string",
                    "description": (
                        "O dia, como o usuário falou: 'hoje', 'amanhã', "
                        "'sexta'. NÃO calcule a data. Vazio significa hoje."
                    ),
                }
            },
        },
    },
}

# A ordem importa pouco para o modelo, mas manter `abrir` primeiro deixa
# explícito que ele é o mais usado.
#
FERRAMENTA_RENOMEAR = {
    "type": "function",
    "function": {
        "name": "renomear",
        "description": (
            "Muda o nome de um arquivo, no lugar onde ele já está. Use para "
            "'renomeia', 'muda o nome', 'troca o nome' e 'chama esse arquivo "
            "de'.\n"
            "Se o que vem depois do 'para' for uma PASTA, e não um nome novo, "
            "então é `mover` e não isto: 'move o relatório para documentos' é "
            "mover; 'renomeia o relatório para proposta' é isto.\n"
            "Use ISTO, e não `abrir`, sempre que a frase contiver 'renomear' "
            "ou 'mudar o nome' em qualquer lugar — inclusive quando ela "
            "começar com 'procura' ou 'acha', como em 'procura o relatório e "
            "renomeia pra proposta'. Procurar é só o passo para chegar no "
            "arquivo; o que ele quer feito é renomear.\n"
            "Não move o arquivo de pasta e não apaga nada."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "alvo": {
                    "type": "string",
                    "description": (
                        "Qual arquivo, como o usuário falou, sem artigo e sem "
                        "verbo. Em 'renomeia o relatório para proposta', é "
                        "'relatório'. Vazio se ele disse só 'esse arquivo' ou "
                        "'esse aí'."
                    ),
                },
                "nome_novo": {
                    "type": "string",
                    "description": (
                        "O nome novo, EXATAMENTE como o usuário falou, sem a "
                        "palavra 'para' e sem inventar extensão. Em 'renomeia "
                        "o relatório para proposta comercial', é 'proposta "
                        "comercial'. Vazio se ele não disse o nome novo."
                    ),
                },
            },
            "required": ["alvo", "nome_novo"],
        },
    },
}

FERRAMENTA_CRIAR_PASTA = {
    "type": "function",
    "function": {
        "name": "criar_pasta",
        "description": (
            "Cria uma pasta nova dentro de outra. Use só quando o usuário "
            "disser PASTA ou DIRETÓRIO: 'cria uma pasta', 'faz uma pasta "
            "chamada X'.\n"
            "'cria um evento', 'cria um lembrete' e 'cria um compromisso' NÃO "
            "são isto — são `criar_evento`. O verbo é o mesmo; quem decide é "
            "a palavra 'pasta'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nome": {
                    "type": "string",
                    "description": (
                        "O nome da pasta, como o usuário falou. Em 'cria uma "
                        "pasta chamada notas fiscais', é 'notas fiscais'."
                    ),
                },
                "dentro_de": {
                    "type": "string",
                    "description": (
                        "Onde criar, como o usuário falou: 'downloads', "
                        "'documentos'. Vazio se ele não disse onde."
                    ),
                },
            },
            "required": ["nome", "dentro_de"],
        },
    },
}

FERRAMENTA_DESFAZER = {
    "type": "function",
    "function": {
        "name": "desfazer",
        "description": (
            "Desfaz a última coisa que você mexeu em arquivo, voltando o nome "
            "anterior. Use para 'desfaz', 'desfaz isso', 'volta atrás', "
            "'cancela o que você fez' e 'não era pra ter feito isso'."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}

FERRAMENTA_MOVER = {
    "type": "function",
    "function": {
        "name": "mover",
        "description": (
            "Leva um arquivo para outra pasta. O arquivo sai de onde está e "
            "passa a ficar no destino, com o mesmo nome.\n"
            "É ISTO que você usa quando ele manda o arquivo para algum lugar: "
            "'move', 'manda pra', 'leva pra', 'joga pra', 'guarda em', 'põe na "
            "pasta', 'tira daqui e põe em', 'arquiva em'.\n"
            "'guarda' e 'arquiva' são SEMPRE mover, nunca copiar — guardar uma "
            "coisa não é ficar com duas.\n"
            "A diferença com `renomear`: aqui o que vem depois do 'para' é uma "
            "PASTA, e o nome do arquivo não muda. Em 'move o relatório para "
            "documentos', 'documentos' é pasta e isto é `mover`. Em 'renomeia o "
            "relatório para proposta', 'proposta' é o nome novo do arquivo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origem": {
                    "type": "string",
                    "description": (
                        "Qual arquivo, como o usuário falou, sem artigo e sem "
                        "verbo. Em 'move o relatório pra documentos', é "
                        "'relatório'. Vazio se ele disse só 'isso' ou 'esse aí'."
                    ),
                },
                "destino": {
                    "type": "string",
                    "description": (
                        "A PASTA de destino, como ele falou: 'documentos', "
                        "'estudos', 'senai'. Nunca um nome de arquivo. Vazio se "
                        "ele não disse para onde."
                    ),
                },
            },
            "required": ["origem", "destino"],
        },
    },
}

FERRAMENTA_COPIAR = {
    "type": "function",
    "function": {
        "name": "copiar",
        "description": (
            "Põe uma cópia do arquivo em outra pasta. O original FICA onde "
            "está — depois disto existem dois.\n"
            "É ISTO que você usa quando ele pede cópia: 'copia', 'faz uma "
            "cópia', 'duplica', 'manda uma cópia', 'deixa uma cópia em'.\n"
            "Só é isto quando ele disser COPIAR ou CÓPIA. Se ele só mandou o "
            "arquivo para algum lugar, sem falar de cópia, é `mover`."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origem": {
                    "type": "string",
                    "description": (
                        "Qual arquivo, como o usuário falou, sem artigo e sem "
                        "verbo. Em 'move o relatório pra documentos', é "
                        "'relatório'. Vazio se ele disse só 'isso' ou 'esse aí'."
                    ),
                },
                "destino": {
                    "type": "string",
                    "description": (
                        "A PASTA de destino, como ele falou: 'documentos', "
                        "'estudos', 'senai'. Nunca um nome de arquivo. Vazio se "
                        "ele não disse para onde."
                    ),
                },
            },
            "required": ["origem", "destino"],
        },
    },
}

# São ONZE agora. O par novo — `mover` contra `copiar` — foi marcado como "o
# próximo a brigar" quando a Etapa 5 fechou, e as duas descrições seguem a
# lição do "procura": cada uma REIVINDICA os próprios verbos, e nenhuma diz
# "não sou eu".
#
# O par que preocupa de verdade não é esse, é `mover` contra `renomear`: a
# Etapa 5 ensinou o modelo que "para X" é nome novo, e "move o relatório para
# documentos" tem a mesma forma. O sinal que separa é que destino é PASTA e
# nome novo não — está dito nas duas descrições, e medido. — de 6 para 9 de uma vez. A
# lição registrada na Etapa 2 diz que cada função nova amplia o que o modelo
# pode confundir com o que já existe, por isso o conjunto de roteamento cresce
# junto e é ele que decide se a etapa está de pé. O par que mais preocupa é
# `criar_pasta` contra `criar_evento`: mesmo verbo, destinos completamente
# diferentes.
FERRAMENTAS = [
    FERRAMENTA_ABRIR,
    FERRAMENTA_TOCAR,
    FERRAMENTA_MIDIA,
    FERRAMENTA_STATUS,
    FERRAMENTA_CRIAR_EVENTO,
    FERRAMENTA_AGENDA_DIA,
    FERRAMENTA_RENOMEAR,
    FERRAMENTA_CRIAR_PASTA,
    FERRAMENTA_DESFAZER,
    FERRAMENTA_MOVER,
    FERRAMENTA_COPIAR,
]


class Confirmacao(Enum):
    SIM = auto()
    NAO = auto()
    OUTRO = auto()


@dataclass(frozen=True)
class Interpretacao:
    """Qual função o modelo escolheu, e com que argumentos.

    Deixou de ser só `nome` na Etapa 3: com quatro ferramentas, o núcleo
    precisa saber qual foi escolhida, não só o que foi extraído.
    """

    funcao: str | None  # None = o modelo não chamou nada
    argumentos: dict
    segundos: float

    @property
    def nome(self) -> str | None:
        """O texto livre que o modelo extraiu, quando a função tem um."""
        for chave in ("nome", "o_que"):
            valor = self.argumentos.get(chave)
            if isinstance(valor, str) and valor.strip():
                return valor.strip()
        return None


class ErroDoCerebro(RuntimeError):
    """Ollama fora do ar ou modelo ausente, com instrução de como resolver."""


class Cerebro:
    def __init__(self, cfg: ConfigLlm) -> None:
        self.cfg = cfg
        self._nomes: list[str] = []

    def conferir(self) -> None:
        """Falha cedo e com mensagem útil, em vez de no meio de um comando."""
        try:
            r = requests.get(f"{self.cfg.url}/api/tags", timeout=5)
            r.raise_for_status()
            modelos = [m["name"] for m in r.json().get("models", [])]
        except Exception as e:
            raise ErroDoCerebro(
                f"Ollama não responde em {self.cfg.url} ({e}).\n"
                "  Suba com:  ollama serve"
            ) from e
        if self.cfg.modelo not in modelos:
            raise ErroDoCerebro(
                f"O modelo {self.cfg.modelo} não está no Ollama.\n"
                f"  Baixe com:  ollama pull {self.cfg.modelo}\n"
                f"  Disponíveis: {', '.join(modelos) or '(nenhum)'}"
            )

    def usar_atalhos(self, nomes: list[str]) -> None:
        self._nomes = nomes

    def carregar(self) -> float:
        """Carrega o modelo na VRAM AGORA, esperando terminar. Devolve segundos.

        Existe porque o `conferir()` da subida só chamava `/api/tags`, que
        confirma que o modelo está **listado** e não que está **carregado** — e
        o cliente imprimia "pronto" com a peça mais cara ainda no disco.

        O custo é ler 5,23 GB, e ele depende inteiramente do cache de página:

            disco frio   14,8s  (354 MB/s, o SSD)
            em cache      1,2s  (4311 MB/s, a RAM)

        Medido com o mesmo arquivo, esvaziando o cache com `posix_fadvise`
        entre as leituras. Chamar isto na subida não cria espera nova: move os
        15 segundos para dentro de uma espera que já existe, e que o Léo já
        respeita — ele espera o "pronto" antes de falar.

        As mesmas ferramentas do `aquecer()` vão junto, pelo mesmo motivo: o
        schema entra no cache de prompt e a primeira inferência de verdade cai
        de ~2,9s para ~1,0s.
        """
        inicio = time.monotonic()
        try:
            requests.post(
                f"{self.cfg.url}/api/chat",
                json={
                    "model": self.cfg.modelo,
                    "messages": [{"role": "user", "content": "oi"}],
                    "tools": FERRAMENTAS,
                    "stream": False,
                    "options": {"num_predict": 1},
                    "keep_alive": self.cfg.keep_alive,
                },
                timeout=self.cfg.timeout_s,
            )
        except Exception:
            # Falhar aqui não pode derrubar a subida: sem isto o primeiro
            # comando paga a carga, que é exatamente o que era antes.
            pass
        return time.monotonic() - inicio

    def aquecer(self) -> None:
        """Manda o Ollama carregar o modelo, sem esperar resposta.

        Com `keep_alive` de 5 minutos, o `qwen3:8b` cai da VRAM quando o Léo
        fica um tempo sem falar, e o comando seguinte paga ~7,5s de recarga —
        medido. Mas entre o wake word disparar e a saudação terminar de tocar
        passam uns 2 a 3 segundos que já estão sendo gastos de qualquer jeito.

        Carregar nessa janela esconde quase toda a recarga sem segurar VRAM
        enquanto ele dorme, que era o que o ESCOPO §4 queria proteger.

        **As ferramentas vão junto, e `num_predict=1` para não gerar nada.**
        Isto foi medido de três jeitos, descarregando o modelo antes de cada um:

            A  messages=[] sem tools      aquece 11,55s + 1ª inferência 2,94s
            B  com tools, gerando         aquece 17,24s + 1,06s  -> PIOR
            C  com tools, num_predict=1   aquece 12,74s + 1,12s  -> escolhido

        **B é pior que não aquecer direito, e o motivo importa:** o Ollama
        serializa por modelo, então um aquecimento que gera texto entra na
        frente do comando real e o atrasa. A versão A carregava o modelo mas
        deixava o schema das 9 ferramentas fora do cache, e a primeira
        inferência de verdade ainda pagava ~1,9s a mais por isso.

        Em thread daemon, porque isto **nunca** pode atrasar a saudação.
        """

        def carregar() -> None:
            try:
                requests.post(
                    f"{self.cfg.url}/api/chat",
                    json={
                        "model": self.cfg.modelo,
                        "messages": [{"role": "user", "content": "oi"}],
                        "tools": FERRAMENTAS,
                        "stream": False,
                        "options": {"num_predict": 1},
                        "keep_alive": self.cfg.keep_alive,
                    },
                    timeout=self.cfg.timeout_s,
                )
            except Exception:
                # Aquecer é otimização. Falhar aqui só custa a recarga que
                # já pagaríamos — nunca deve derrubar o assistente.
                pass

        threading.Thread(target=carregar, daemon=True).start()

    # ----------------------------------------------------------------------

    def _chat(self, mensagens: list[dict], tools: list[dict] | None = None) -> dict:
        r = requests.post(
            f"{self.cfg.url}/api/chat",
            json={
                "model": self.cfg.modelo,
                "messages": mensagens,
                **({"tools": tools} if tools else {}),
                "stream": False,
                # Sem "thinking": o modelo só escolhe uma função e extrai uma
                # palavra. Raciocínio em voz alta aqui é latência pura.
                "think": False,
                "keep_alive": self.cfg.keep_alive,
            },
            timeout=self.cfg.timeout_s,
        )
        r.raise_for_status()
        return r.json()

    def interpretar(self, frase: str) -> Interpretacao:
        mensagens = []
        if self._nomes:
            mensagens.append(
                {
                    "role": "system",
                    "content": (
                        "As coisas que você sabe abrir são exatamente estas: "
                        + ", ".join(f'"{n}"' for n in self._nomes)
                        + ". Ao chamar a função, use o nome desta lista que "
                        "corresponde ao pedido."
                    ),
                }
            )
        mensagens.append({"role": "user", "content": frase})

        inicio = time.monotonic()
        resposta = self._chat(mensagens, tools=FERRAMENTAS)
        segundos = time.monotonic() - inicio

        chamadas = resposta.get("message", {}).get("tool_calls") or []
        if not chamadas:
            return Interpretacao(None, {}, segundos)
        funcao = chamadas[0].get("function", {})
        return Interpretacao(
            funcao.get("name"), funcao.get("arguments") or {}, segundos
        )

    def detalhar_musica(self, frase: str) -> Interpretacao:
        """Lê a resposta a "qual música?", que vem sem verbo.

        `interpretar()` não dispara em "tempo perdido no youtube": sem verbo,
        não parece comando, e o modelo devolve nada. Sem isto o "no youtube" se
        perdia E ainda ia junto no termo de busca, procurando por
        "tempo perdido no youtube" no YouTube.

        Prompt dedicado dando o contexto que falta, e só a ferramenta `tocar`
        à mesa — o modelo não tem o que escolher errado.
        """
        inicio = time.monotonic()
        resposta = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Você perguntou ao usuário qual música ele quer, e "
                        "isto é a resposta dele. Chame `tocar` com o nome da "
                        "música. Se ele disser YouTube, navegador ou que quer "
                        "ver, use onde='navegador'."
                    ),
                },
                {"role": "user", "content": frase},
            ],
            tools=[FERRAMENTA_TOCAR],
        )
        segundos = time.monotonic() - inicio
        chamadas = resposta.get("message", {}).get("tool_calls") or []
        if not chamadas:
            return Interpretacao(None, {}, segundos)
        funcao = chamadas[0].get("function", {})
        return Interpretacao(
            funcao.get("name"), funcao.get("arguments") or {}, segundos
        )

    def corrigir(self, frase: str) -> str | None:
        """Extrai o nome certo de dentro de uma negação.

        Existe porque negar era beco sem saída: o Léo dizia "não, eu quis dizer
        configurações" — entregando o nome certo na mesma frase — e o sistema
        respondia "isso eu ainda não sei fazer", porque `interpretar()` não
        dispara em frase que não tem cara de comando.

        Prompt dedicado em vez de lista de palavras chumbada: o atalho por
        lista já foi vetado uma vez, por brigar com o modelo depois.
        """
        resposta = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "O usuário está corrigindo um pedido anterior que você "
                        "entendeu errado. Se ele disse qual é a coisa certa, "
                        "responda APENAS com o nome dela, sem verbo e sem "
                        "artigo. Se ele apenas negou sem dizer o que queria, "
                        "responda apenas NADA."
                    ),
                },
                {"role": "user", "content": frase},
            ]
        )
        texto = (resposta.get("message", {}).get("content") or "").strip()
        if not texto or texto.upper().startswith("NADA"):
            return None
        return texto.strip(" .\"'")

    def confirmar(self, frase: str, pergunta: str) -> Confirmacao:
        """Classifica a resposta a uma pergunta de sim/não.

        A `pergunta` entra no prompt, e isso não é enfeite. Sem ela o modelo
        empurra pedido novo para NAO: "abre o loft" dito durante uma
        confirmação virava "deixa pra lá" — cancelava o evento pendente E não
        abria o Loft, porque a saída de emergência do OUTRO nunca disparava.
        Medido em 5 rodadas de 16 frases: 61/80 sem a pergunta, 80/80 com ela.
        """
        resposta = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        f'Você perguntou ao usuário: "{pergunta}"\n'
                        "Classifique a resposta dele com uma palavra só:\n"
                        "SIM — ele concordou com ESSA pergunta. Em português "
                        "falado isso inclui 'pode', 'manda', 'isso', "
                        "'beleza', 'claro', 'vai lá', 'bora' e 'aham', não "
                        "só 'sim'.\n"
                        "NAO — ele recusou ESSA pergunta, ou corrigiu algo "
                        "dela, como em 'não, era terça' ou 'nada disso'.\n"
                        "OUTRO — ele não respondeu à pergunta. Qualquer frase "
                        "que seja um pedido novo, uma ordem, outra pergunta, "
                        f'ou que não tenha relação com "{pergunta}", é OUTRO '
                        "— mesmo que soe seca. Na dúvida entre NAO e OUTRO, "
                        "responda OUTRO."
                    ),
                },
                {"role": "user", "content": frase},
            ]
        )
        texto = (resposta.get("message", {}).get("content") or "").strip().upper()
        if texto.startswith("SIM"):
            return Confirmacao.SIM
        if texto.startswith("NAO") or texto.startswith("NÃO"):
            return Confirmacao.NAO
        return Confirmacao.OUTRO

    def resposta_solta(self, frase: str) -> bool:
        """Diz se a frase é só um sim ou um não, com nada pendente.

        Existe porque "pode" sem nada na mesa caía em nao_sei, e o Léo saiu de
        uma conversa acreditando ter marcado um dentista que nunca foi criado.
        Compromisso que você acredita ter e não tem é o pior resultado
        possível numa agenda — pior que dar erro.

        A nota sobre maiúsculas não é supérflua: o STT capitaliza a primeira
        palavra da frase, e medindo deu 'não' → SOLTA mas 'Não' → OUTRO. Com
        a nota, 90/90 em 5 rodadas de 18 frases.
        """
        resposta = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "A frase abaixo foi dita sem que houvesse nenhuma "
                        "pergunta na mesa. Responda uma palavra só:\n"
                        "SOLTA — a frase é só uma concordância ou uma recusa, "
                        "sem pedido próprio: 'sim', 'pode', 'manda', "
                        "'beleza', 'isso', 'aham', 'claro', 'não', 'deixa "
                        "pra lá', 'nada disso'.\n"
                        "OUTRO — qualquer outra coisa, incluindo saudação, "
                        "agradecimento, elogio, pergunta e frase sem "
                        "sentido.\n"
                        "Pontuação e maiúsculas não mudam nada: 'Não.' é o "
                        "mesmo que 'não'. Uma negação sozinha é SOLTA mesmo "
                        "sem nada para negar."
                    ),
                },
                {"role": "user", "content": frase},
            ]
        )
        texto = (resposta.get("message", {}).get("content") or "").strip().upper()
        return texto.startswith("SOLTA")
