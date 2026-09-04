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
            "projeto. Use apenas quando o usuário pedir para abrir, mostrar ou "
            "acessar alguma coisa.\n"
            "Quem decide é o VERBO, não o assunto: 'abre', 'mostra', 'acessa' "
            "e 'põe na tela' são abrir.\n"
            "Para 'toca', 'reproduz' ou 'ouve', use `tocar`. Para 'pausa', "
            "'continua', 'próxima' ou 'volume', use `midia`. Para perguntas "
            "sobre o computador, use `status_pc`.\n"
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

# A ordem importa pouco para o modelo, mas manter `abrir` primeiro deixa
# explícito que ele é o mais usado.
FERRAMENTAS = [
    FERRAMENTA_ABRIR,
    FERRAMENTA_TOCAR,
    FERRAMENTA_MIDIA,
    FERRAMENTA_STATUS,
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

    def confirmar(self, frase: str) -> Confirmacao:
        """Classifica a resposta a uma pergunta de sim/não."""
        resposta = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "O usuário está respondendo a uma pergunta de sim ou "
                        "não. Responda com uma palavra só:\n"
                        "SIM — ele concordou.\n"
                        "NAO — ele negou, discordou ou corrigiu. Use NAO "
                        "também quando ele nega e já diz o que queria, como "
                        "em 'não, eu quis dizer outra coisa' ou 'nada disso, "
                        "quero X'.\n"
                        "OUTRO — ele ignorou a pergunta e falou de um assunto "
                        "sem relação."
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
