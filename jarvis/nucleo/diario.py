"""O diário de conversas: do que o Léo e o Jarvis falaram, com dia, hora e tema.

Existe porque a conversa do Claude morria quando o Jarvis dormia ou era
desligado: "o que eu te falei agora há pouco?" não tinha resposta. Pedido do
Léo (out/2026): a memória tem que servir aos dois — ao Jarvis, por dentro, e
a ele, numa seção da janela.

Como funciona:
- cada troca (o que ele disse, o que o Jarvis respondeu) vai na hora para
  `conversa-atual.jsonl`. Se o Jarvis cair no meio, nada se perde;
- quando o Jarvis dorme, o episódio fecha 10 minutos depois se ninguém
  voltar a falar (dormir e acordar logo em seguida é a mesma conversa; no
  primeiro teste, cada "dorme aí" virava uma entrada à toa). Ao desligar,
  fecha na hora. Fechado, é resumido pelo Claude em segundo plano — tema curto e uma ou duas frases — e vai para
  `conversas.jsonl`. Um resumo por linha, do mais antigo ao mais novo;
- os últimos resumos acompanham cada mensagem ao Claude, e a janela mostra
  todos.

Os dois arquivos ficam na raiz e fora do git: são a vida do Léo.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path
from typing import Callable

_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


class Diario:
    def __init__(self, raiz: Path,
                 resumir: Callable[[list[dict]], tuple[str, str] | None]) -> None:
        Path(raiz).mkdir(parents=True, exist_ok=True)
        self.atual = Path(raiz) / "conversa-atual.jsonl"
        self.arquivo = Path(raiz) / "conversas.jsonl"
        self._resumir = resumir
        self._trava = threading.Lock()
        self._relogio: threading.Timer | None = None
        # Sobrou episódio de uma sessão que caiu sem dormir: resume agora.
        if self._trocas():
            self.fechar_episodio()

    # -- o episódio em andamento -----------------------------------------------

    def registrar(self, dito: str, resposta: str, acao: str | None) -> None:
        if not dito.strip() or (not resposta.strip() and not acao):
            return  # o que ele ignorou (vídeo, TV) não é conversa
        self._cancelar_relogio()
        linha = {"quando": dt.datetime.now().isoformat(timespec="seconds"),
                 "voce": dito, "jarvis": resposta, "acao": acao}
        with self._trava, open(self.atual, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")

    def _trocas(self) -> list[dict]:
        try:
            linhas = self.atual.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        trocas = []
        for l in linhas:
            try:
                trocas.append(json.loads(l))
            except ValueError:
                pass
        return trocas

    def _cancelar_relogio(self) -> None:
        if self._relogio is not None:
            self._relogio.cancel()
            self._relogio = None

    def fechar_depois(self, segundos: float = 600) -> None:
        """Ele dormiu: fecha o episódio se ninguém falar nos próximos minutos."""
        self._cancelar_relogio()
        self._relogio = threading.Timer(segundos, self.fechar_episodio)
        self._relogio.daemon = True
        self._relogio.start()

    def fechar_episodio(self, esperar: bool = False) -> None:
        """Resume o episódio e guarda no diário. Em segundo plano, salvo na
        hora de desligar (`esperar`), quando o processo vai acabar."""
        self._cancelar_relogio()
        with self._trava:
            trocas = self._trocas()
            if not trocas:
                return
            # Tira do arquivo antes de resumir: um segundo fechar enquanto o
            # primeiro ainda resume não pode resumir duas vezes a mesma coisa.
            self.atual.unlink(missing_ok=True)
        t = threading.Thread(target=self._guardar, args=(trocas,), daemon=not esperar)
        t.start()
        if esperar:
            t.join(timeout=60)

    def _guardar(self, trocas: list[dict]) -> None:
        resumo = None
        try:
            resumo = self._resumir(trocas)
        except Exception:
            pass
        if resumo is None:
            # Sem Claude (sem internet, limite): guarda um resumo cru, para não
            # perder a conversa. Melhor feio que sumido.
            resumo = ("conversa", "; ".join(t["voce"] for t in trocas)[:300])
        tema, texto = resumo
        registro = {"inicio": trocas[0]["quando"], "fim": trocas[-1]["quando"],
                    "tema": tema, "resumo": texto, "trocas": len(trocas)}
        with self._trava, open(self.arquivo, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    # -- leitura --------------------------------------------------------------

    def conversas(self, quantas: int | None = None) -> list[dict]:
        """Do mais antigo ao mais novo."""
        try:
            linhas = self.arquivo.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        lista = []
        for l in linhas:
            try:
                lista.append(json.loads(l))
            except ValueError:
                pass
        return lista[-quantas:] if quantas else lista

    @staticmethod
    def quando_falado(iso: str) -> str:
        """"sáb 11/10 02:31"."""
        try:
            d = dt.datetime.fromisoformat(iso)
        except ValueError:
            return iso
        return f"{_SEMANA[d.weekday()]} {d:%d/%m %H:%M}"

    def para_o_cerebro(self, quantas: int = 10) -> str:
        return "\n".join(
            f"- {self.quando_falado(c['inicio'])} — {c['tema']}: {c['resumo']}"
            for c in self.conversas(quantas))
