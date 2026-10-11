#!/usr/bin/env python3
"""A regressão obrigatória de toda etapa.

Rodar antes de fechar qualquer etapa:

    python3 regressao.py            # tudo
    python3 regressao.py --rapido   # pula os conjuntos de 10 rodadas

**Por que este arquivo existe.** Até a Etapa 5.5 a regressão morava num script
de rascunho, e sumiu duas vezes. Foi reconstruída das frases guardadas em
`medicoes/etapa5-arquivos.md` — ou seja, sobreviveu por sorte, porque a medição
estava commitada. É a mesma lição dos logs apagados por engano na Etapa 0.5 e do
prompt antigo do classificador preservado na Etapa 4: **o que prova alguma coisa
tem que estar versionado.**

E o que ela pega justifica o arquivo: nesta rodada apanhou uma perda que faz o
Jarvis ABRIR a pasta de músicas quando o Léo pede para pausar.

**Cada conjunto traz o número esperado e o motivo dele.** Sem isso, uma queda no
total não é atribuível — é só um número menor, e o próximo a rodar não sabe se
quebrou agora ou se sempre foi assim.

**Nada aqui toca arquivo, volume ou player do Léo** (ESCOPO §2, regra da Etapa
3). O que precisa de disco usa pasta temporária; o que precisa de mídia é casado
contra a lista fechada, que é string, sem efeito nenhum.

⚠️ **O classificador AMOSTRA, e por isso alguns mínimos são menores que o
total.** O `interpretar()` não passa `temperature` ao ollama, então usa o padrão
do modelo — cada roteamento é uma amostra, não uma função. Medido, n=20:

    frase                                      padrão     temperature 0
    procura o relatório e renomeia pra ...     18/20      20/20
    Abaixa.                                    16/20      20/20
    abre o loft                                20/20      20/20
    Para a música.                              0/20       0/20

As duas primeiras oscilam entre rodadas por amostragem pura — foi o que fez o
mesmo caso dar 5/5, 4/5 e 0/5 em três execuções seguidas desta regressão. A
última NÃO oscila: é preferência determinística do modelo, e por isso é bug e
não ruído.

**Enquanto a temperatura não for decidida, os mínimos aqui são a taxa medida, e
não um número redondo.** Mínimo frouxo esconde regressão; mínimo apertado
produz vermelho falso e treina quem roda a ignorar a regressão — que é pior.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from jarvis.config import carregar
from jarvis.nucleo import cerebro as mod_cerebro
from jarvis.nucleo import midia as mod_midia
from jarvis.nucleo import sistema as mod_sistema
from jarvis.nucleo.atalhos import Tabela
from jarvis.nucleo.busca import Buscador
from jarvis.nucleo.nucleo import Nucleo


@dataclass(frozen=True)
class Caso:
    frase: str
    esperado: str | None
    # Mínimo de acertos por rodada. None = tem que acertar TODAS.
    #
    # Existe para falha conhecida não virar ruído vermelho toda rodada, e para
    # o dia em que ela for consertada aparecer como surpresa boa em vez de
    # passar despercebida. Todo mínimo abaixo do total precisa de um `porque`.
    minimo: int | None = None
    porque: str = ""


@dataclass
class Conjunto:
    nome: str
    casos: list[Caso]
    rodadas: int
    porque: str
    # Conjuntos de 10 rodadas são caros; o --rapido os pula.
    caro: bool = field(default=False)


# ---------------------------------------------------------------------------
# Os conjuntos
# ---------------------------------------------------------------------------

# As 15 da Etapa 1. É o conjunto mais antigo do projeto e o mais importante:
# ele responde "o que já funcionava continua funcionando?". Toda etapa desde a
# 1 o rodou, e ele nunca caiu de 75/75 — se cair, a etapa não fecha.
ETAPA1 = Conjunto(
    nome="15 frases da Etapa 1",
    rodadas=5,
    porque="75/75 em toda etapa desde a Etapa 1. Queda aqui reprova a etapa.",
    casos=[
        Caso("abre o loft", "abrir"),
        Caso("abre gravações", "abrir"),
        Caso("abre o projeto loft", "abrir"),
        Caso("abre o projeto loft pra mim", "abrir"),
        Caso("põe o loft na tela", "abrir"),
        Caso("abre a pasta de gravações", "abrir"),
        Caso("dá uma aberta no loft aí", "abrir"),
        # As três com erro de transcrição: o Whisper escreve assim de verdade.
        Caso("abre o lofti", "abrir"),
        Caso("abre gravasoes", "abrir"),
        Caso("abre o projeto lofit", "abrir"),
        # As três que NÃO podem virar função nenhuma.
        Caso("que horas são?", None),
        Caso("tudo bem?", None),
        Caso("obrigado", None),
        Caso("toca uma música", "tocar"),
        Caso("qual a temperatura da GPU?", "status_pc"),
    ],
)

# Uma frase por função do núcleo, mais os pares que já brigaram de verdade.
# Cresce junto com o número de ferramentas: hoje são 11.
ROTEAMENTO = Conjunto(
    nome="roteamento com 11 funções",
    rodadas=5,
    porque="uma frase por função, mais os pares que já brigaram. 65/65.",
    casos=[
        Caso("Renomeia o relatório para proposta comercial.", "renomear"),
        Caso("Muda o nome do print pra tela de erro.", "renomear"),
        Caso("Chama esse arquivo de acordo final.", "renomear"),
        Caso("Cria uma pasta chamada notas na documentos.", "criar_pasta"),
        Caso("Desfaz.", "desfazer"),
        # "Volta atrás" é a frase da Etapa 5, e "Volta." sozinho quase foi
        # roubado pela lista de mídia — ver a guarda em CRUS_TABELA.
        Caso("Volta atrás.", "desfazer"),
        Caso("Abre o relatório.", "abrir"),
        Caso("Cria um evento amanhã às 9 chamado dentista.", "criar_evento"),
        Caso("O que eu tenho hoje?", "agenda_do_dia"),
        # Etapa 5.5. O par que eu esperava que brigasse — mover contra
        # renomear, porque "para X" foi ensinado como nome novo na Etapa 5 —
        # não brigou: 90/90 no fechamento.
        Caso("Move o trabalho sobre cuba pra estudos.", "mover"),
        Caso("Guarda esse pdf na pasta de estudos.", "mover"),
        Caso("Copia o contrato pra documentos.", "copiar"),
        Caso("Faz uma cópia do relatório na downloads.", "copiar"),
    ],
)

# O conserto do verbo "procura" (Etapa 5). A lição: a instrução mora na
# ferramenta que deve GANHAR, nunca na que deve perder.
PROCURA = Conjunto(
    nome="o conserto do 'procura'",
    rodadas=5,
    porque="40/40. Procurar e abrir são o mesmo pedido; com verbo de ação, "
           "manda o verbo de ação.",
    casos=[
        Caso("procura o arquivo de configuração", "abrir"),
        Caso("procura o relatório", "abrir"),
        Caso("acha a pasta de gravações", "abrir"),
        Caso("cadê o loft?", "abrir"),
        Caso("encontra o currículo", "abrir"),
        Caso(
            "procura o relatório e renomeia pra proposta", "renomear", minimo=0,
            porque="FALHA CONHECIDA (ESCOPO §8): frase no quase empate entre "
                   "abrir e renomear, e decide pelo estado do servidor — "
                   "18/20 numa carga nova, 2/5 numa carga longa, desde set/2026. "
                   "Com mínimo 4 a regressão reprovava toda rodada e virou "
                   "ruído. Fica travado em 0 até a rodada de roteamento.",
        ),
        Caso("abre música", "abrir"),
        Caso("toca uma música", "tocar"),
    ],
)

# Mídia COM objeto: a lista fechada não pega (ela casa a fala inteira), então
# estas chegam ao modelo. 10 rodadas e não 5 — ver a lição no rodapé.
MIDIA = Conjunto(
    nome="mídia com objeto",
    rodadas=10,
    caro=True,
    porque="o custo de crescer a lista se concentra nas falas curtas. "
           "10 rodadas porque 5 não enxergam efeito de 1 em 10.",
    casos=[
        Caso("Abaixa o volume.", "midia"),
        Caso("Abaixa o som.", "midia"),
        Caso("aumenta o volume", "midia"),
        Caso("Toca uma música.", "tocar"),
        Caso("qual a temperatura da GPU?", "status_pc"),
        Caso("Pode parar a música.", "midia"),
        Caso(
            "Abaixa.", "midia", minimo=7,
            porque="16/20 medido, e o que falta vira None. O 10/10 registrado "
                   "no conserto do volume veio de 5 rodadas e era otimista; "
                   "com 9 ferramentas dá o mesmo, então não é regressão da "
                   "5.5. É amostragem: 20/20 com temperature 0.",
        ),
        Caso(
            "Para a música.", "midia", minimo=0,
            porque="⚠️ LIMITAÇÃO CONHECIDA. Foi de 10/10 (9 ferramentas) para "
                   "0/10 (11), e vai para `abrir` — ação errada, pior que não "
                   "entender: abre a pasta de músicas em vez de pausar. NÃO é "
                   "amostragem: 0/20 também com temperature 0. O padrão das "
                   "três vezes anteriores não explica, porque a descrição do "
                   "`midia` reivindica 'para a música' por escrito. Espera "
                   "rodada própria com diagnóstico antes do conserto. Se este "
                   "caso subir de 0, foi consertado — atualize o mínimo.",
        ),
        Caso(
            "Para o vídeo.", "midia", minimo=0,
            porque="⚠️ NUNCA funcionou: 0/10 com 9 e com 11 ferramentas, e "
                   "0/20 com temperature 0, indo para `tocar` 20/20. Não foi "
                   "a 5.5 que quebrou. Mesmo conserto do caso acima.",
        ),
    ],
)

# A lista fechada do `midia.COMANDOS_CRUS`, consultada no `processar` ANTES do
# modelo. É determinística — uma passada basta, e custa 0ms.
#
# Medir estas frases com `interpretar()` mede uma camada que a voz não
# atravessa. Foi o erro da primeira reconstrução desta regressão.
CRUS_TABELA = [
    ("Pausa.", "pausar"),
    ("pausa", "pausar"),
    ("Para!", "pausar"),
    ("Para.", "pausar"),
    ("Continua.", "continuar"),
    ("continua", "continuar"),
    ("Dá play.", "continuar"),
    ("Pode dar play agora.", "continuar"),
    ("Próxima.", "proxima"),
    ("Pula.", "proxima"),
    # A guarda que a medição impediu: `volta → anterior` teria roubado o
    # desfazer da Etapa 5 de forma DETERMINÍSTICA, que é a pior espécie —
    # sem oscilação para denunciar. "Volta." não pode ser comando de mídia.
    ("Volta.", None),
]

# O gatilho de tela (Etapa 6.6), também lista fechada e também antes do modelo.
# Inclui as que NÃO podem casar: a palavra solta ficou de fora de propósito, e
# "bloqueia o relatório" é o vizinho perigoso.
TELA_TABELA = [
    ("bloqueia o PC", "bloquear"),
    ("Bloqueia o computador.", "bloquear"),
    ("Trava a tela.", "bloquear"),
    ("tranca o pc", "bloquear"),
    ("bloqueia", None),
    ("trava", None),
    ("bloqueia o relatório", None),
    ("abre o loft", None),
]

# A busca da Etapa 2 continua achando. Números do disco real do Léo, que mudam
# com o conteúdo dele — por isso a checagem é "achou alguma coisa", não um
# número exato. `dança` está aqui porque já falhou de duas formas diferentes:
# devolvendo o arquivo ERRADO (bug do acento) e devolvendo ZERO com o arquivo
# no disco (índice velho + `exists()` na ordem errada).
BUSCA = ["downloads", "readme", "experimento wakeword", "atalhos", "dança"]

CONJUNTOS = [ETAPA1, ROTEAMENTO, PROCURA, MIDIA]


# ---------------------------------------------------------------------------


def rodar(cerebro, conjunto: Conjunto) -> tuple[int, int, list[str]]:
    acertos = total = 0
    avisos: list[str] = []
    for caso in conjunto.casos:
        vistos: Counter = Counter()
        for _ in range(conjunto.rodadas):
            # A conversa do Claude lembra das frases anteriores; uma frase de
            # teste não pode ser lida à luz da outra. Recomeça a cada caso.
            if hasattr(cerebro, "recomecar_conversa"):
                cerebro.recomecar_conversa()
            vistos[cerebro.interpretar(caso.frase).funcao] += 1
        acertou = vistos[caso.esperado]
        minimo = conjunto.rodadas if caso.minimo is None else caso.minimo
        acertos += acertou
        total += conjunto.rodadas
        if acertou < minimo:
            outros = ", ".join(f"{k}:{v}" for k, v in vistos.items()
                               if k != caso.esperado)
            avisos.append(
                f"    ✗ {caso.frase!r} {acertou}/{conjunto.rodadas} "
                f"(mínimo {minimo}) -> {outros}"
            )
        elif caso.minimo is not None:
            primeira = (caso.porque.splitlines() or ["sem motivo registrado"])[0]
            avisos.append(
                f"    · {caso.frase!r} {acertou}/{conjunto.rodadas}, "
                f"esperado ≥{minimo} — {primeira}"
            )
    return acertos, total, avisos


SEM_SENTIDO = "quorvelinho trapiscúdio"


def main() -> int:
    rapido = "--rapido" in sys.argv
    cfg = carregar(Path(__file__).parent / "config.toml")

    # O cérebro configurado: desde out/2026 é o Claude (Opus 5.5 pela
    # assinatura). Cada rodada GASTA limite da assinatura (~180 perguntas no
    # --rapido): rode antes de commit que mexe em roteamento, não toda hora.
    if cfg.llm.cerebro == "claude":
        from jarvis.nucleo.cerebro_claude import CerebroClaude
        cerebro = CerebroClaude(cfg.llm.claude_binario, cfg.llm.claude_modelo,
                                cfg.llm.claude_effort, cfg.llm.claude_timeout_s,
                                cfg.persona.nome)
        cerebro.carregar()
    else:
        cerebro = mod_cerebro.Cerebro(cfg.llm)
    cerebro.conferir()
    tabela = Tabela.carregar(cfg.raiz / "atalhos.toml")
    cerebro.usar_atalhos([a.nome for a in tabela.atalhos])

    modelo = cfg.llm.claude_modelo if cfg.llm.cerebro == "claude" else cfg.llm.modelo
    print(f"\n=== regressão · {modelo} · "
          f"{len(mod_cerebro.FERRAMENTAS)} ferramentas ===\n")

    reprovou = False
    acertos = total = 0
    for conjunto in CONJUNTOS:
        if rapido and conjunto.caro:
            print(f"  {conjunto.nome:44} (pulado por --rapido)")
            continue
        a, t, avisos = rodar(cerebro, conjunto)
        acertos, total = acertos + a, total + t
        print(f"  {conjunto.nome:44} {a}/{t}")
        for aviso in avisos:
            print(aviso)
            reprovou = reprovou or aviso.lstrip().startswith("✗")

    # A lista fechada: determinística, uma passada.
    def casa(frase, esperado):
        cru = mod_midia.comando_cru(frase)
        return (cru.acao if cru else None) == esperado

    def casa_tela(frase, esperado):
        return mod_sistema.comando_de_tela(frase) == esperado

    tela_ok = sum(1 for f, e in TELA_TABELA if casa_tela(f, e))
    print(f"  {'gatilho de tela contra a lista fechada':44} "
          f"{tela_ok}/{len(TELA_TABELA)}")
    for f, e in TELA_TABELA:
        if not casa_tela(f, e):
            print(f"    ✗ {f!r} -> {mod_sistema.comando_de_tela(f)} (esperado {e})")

    tabela_ok = sum(1 for f, e in CRUS_TABELA if casa(f, e))
    print(f"  {'comandos crus contra a lista fechada':44} "
          f"{tabela_ok}/{len(CRUS_TABELA)}")
    for f, e in CRUS_TABELA:
        if not casa(f, e):
            cru = mod_midia.comando_cru(f)
            print(f"    ✗ {f!r} -> {cru.acao if cru else None} (esperado {e})")
            reprovou = True

    # A ancoragem: nome que não existe não pode virar AÇÃO. A pergunta não é
    # para onde o modelo roteia — é se o núcleo age. Quem barra é a ancoragem.
    buscador = Buscador(cfg.busca)
    # Era "abridança.ppxt" até out/2026: o teste pegava o qwen INVENTANDO um
    # nome ("abridança" virava "loft"). O Opus leu como "abri dança.pptx" e
    # abriu o Dança.pptx que existe na Downloads — decifrou a transcrição, não
    # inventou. A frase agora não tem leitura possível.
    if buscador.buscar(SEM_SENTIDO):
        print(f"    ✗ a busca acharia {SEM_SENTIDO!r} — teste não confiável")
        reprovou = True
    else:
        nucleo = Nucleo(cfg, com_diario=False)

        # O bloqueio de tela pelo núcleo, sem NUNCA travar a tela: confere que
        # a resposta traz a ação e o `depois`, e não chama o `depois`.
        bloqueio = nucleo.processar("bloqueia o pc")
        tela_no_nucleo = (bloqueio.acao == "bloquear_tela"
                          and bloqueio.depois is not None
                          and bloqueio.texto == cfg.persona.bloqueando)
        print(f"  {'bloquear a tela pelo núcleo (sem executar)':44} "
              f"{'ok' if tela_no_nucleo else 'FALHOU'}")
        reprovou = reprovou or not tela_no_nucleo

        # As ações viram anotação neste teste: ele roda o núcleo de verdade, e
        # o Opus resolvendo "tocar quorvelinho" tocaria música no PC do Léo.
        import jarvis.nucleo.acoes as _acoes
        import jarvis.nucleo.arquivos as _arquivos
        import jarvis.nucleo.midia as _midia
        def _anota(*_a, **_k):
            return _acoes.Resultado(True, "anotado")
        _acoes._abrir = lambda *_a, **_k: None
        _midia.tocar_audio = _midia.tocar_navegador = _midia.controlar = _anota
        _arquivos.criar_pasta = _anota
        acoes = sum(1 for _ in range(20)
                    if nucleo.processar(SEM_SENTIDO).acao)
        print(f"  {'frase sem sentido x20 (ancoragem)':44} "
              f"{acoes} ações (exigido 0)")
        reprovou = reprovou or acoes > 0

    print("\n  a busca da Etapa 2 continua achando:")
    for termo in BUSCA:
        n = len(buscador.buscar(termo))
        print(f"    {termo!r:26} {n:3} achados" + ("  ✗ ZERO" if not n else ""))
        reprovou = reprovou or n == 0

    print(f"\n  TOTAL: {acertos}/{total}")
    print("  REPROVOU\n" if reprovou else "  passou\n")
    reprovou = reprovou or tela_ok != len(TELA_TABELA)
    return 1 if reprovou else 0


if __name__ == "__main__":
    raise SystemExit(main())
