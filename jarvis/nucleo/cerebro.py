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
            "nome', use `renomear`; para 'cria uma pasta', `criar_pasta`.\n"
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
        "description": (
            "Controla o que JÁ está tocando, seja música, vídeo ou o som de um "
            "jogo. Não serve para começar a tocar algo — para isso use `tocar`."
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
                "valor": {
                    "type": "string",
                    "description": (
                        "Só para acao='volume': um número de 0 a 100, ou "
                        "'mais', 'menos', 'mudo'."
                    ),
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

# São NOVE agora, e é o maior salto do projeto — de 6 para 9 de uma vez. A
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

    def aquecer(self) -> None:
        """Manda o Ollama carregar o modelo, sem esperar resposta.

        Com `keep_alive` de 5 minutos, o `qwen3:8b` cai da VRAM quando o Léo
        fica um tempo sem falar, e o comando seguinte paga ~7,5s de recarga —
        medido. Mas entre o wake word disparar e a saudação terminar de tocar
        passam uns 2 a 3 segundos que já estão sendo gastos de qualquer jeito.

        Carregar nessa janela esconde quase toda a recarga sem segurar VRAM
        enquanto ele dorme, que era o que o ESCOPO §4 queria proteger.

        Requisição com `messages` vazio: o Ollama carrega o modelo e não gera
        nada. Em thread daemon, porque isto **nunca** pode atrasar a saudação.
        """

        def carregar() -> None:
            try:
                requests.post(
                    f"{self.cfg.url}/api/chat",
                    json={
                        "model": self.cfg.modelo,
                        "messages": [],
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
