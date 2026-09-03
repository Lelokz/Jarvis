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
            "acessar alguma coisa."
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


class Confirmacao(Enum):
    SIM = auto()
    NAO = auto()
    OUTRO = auto()


@dataclass(frozen=True)
class Interpretacao:
    nome: str | None  # None = não é pedido de abrir
    segundos: float


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
        resposta = self._chat(mensagens, tools=[FERRAMENTA_ABRIR])
        segundos = time.monotonic() - inicio

        chamadas = resposta.get("message", {}).get("tool_calls") or []
        if not chamadas:
            return Interpretacao(None, segundos)
        nome = chamadas[0].get("function", {}).get("arguments", {}).get("nome")
        return Interpretacao(nome or None, segundos)

    def confirmar(self, frase: str) -> Confirmacao:
        """Classifica a resposta a uma pergunta de sim/não."""
        resposta = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "O usuário está respondendo a uma pergunta de sim ou "
                        "não. Responda com uma palavra só: SIM se ele "
                        "concordou, NAO se ele negou, OUTRO se ele falou "
                        "outra coisa qualquer."
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
