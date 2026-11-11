"""O Jarvis nos grupos do WhatsApp (23/10/2026, pedido do Léo; começou só
no grupo da família e, desde 09/11/2026, vale para quantos grupos ele marcar
nos Ajustes: cada um com a própria memória, conversa aberta e limite).

Quem está no grupo conversa com o Jarvis escrevendo "Jarvis" em qualquer
parte da mensagem; ele lê pelo contexto se é com ele. Depois que ele
responde, a conversa fica aberta por uns minutos: a resposta de quem falou
com ele chega mesmo sem "Jarvis" (o Chris respondeu ao "em que posso
ajudar?" e ficou no vácuo, 23/10/2026). A resposta sai pelo
WhatsApp do dono, com "🤖 Jarvis:" na frente.

**O Claude completo, com as coisas do dono fechadas (25/10/2026).** Antes
era trancado com meia dúzia de ferramentas fechadas (lista de compras etc.)
e, sem ter como lembrar alguém numa hora, pediu aprovação do Léo para
"lembra a Karyn que segunda tem o CIEE". O Léo: o Jarvis tem que saber fazer,
sem ferramenta para tudo. Agora ele tem terminal, internet e uma pasta só
dele para anotar; o que é do dono (pastas, conversas, memória, e-mail,
agenda, código do Jarvis) é barrado no gancho (`trava_do_grupo`), e mexer no
PC ou nas coisas dele vira um pedido no celular (`jarvis/nucleo/aprovacoes.py`;
se ele aprovar, quem faz é o Jarvis do PC: `pegar()` -> o laço principal).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import queue
import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import NamedTuple

from jarvis import ajustes
from jarvis.agente import travas
from jarvis.agente.agente import sim_ou_nao
from jarvis.nucleo import aprovacoes, recados
from jarvis.nucleo.atalhos import normalizar
from jarvis.grupo import audios, historico

PREFIXO = "🤖 Jarvis:"
# A Friday também responde nos grupos (09/11/2026), com o mesmo jeito de
# trabalhar e o jeito de falar dela, ajustado para muita gente.
PREFIXOS = {"jarvis": PREFIXO, "friday": "💜 Friday:"}
NOMES = {"jarvis": "Jarvis", "friday": "Friday"}
PERSONA = Path(__file__).with_name("persona_grupo.md")          # as regras, iguais para os dois
JEITO = {p: Path(__file__).with_name(f"jeito_{p}.md") for p in PREFIXOS}   # o jeito de falar de cada um
# O 👀 na mensagem de quem chamou, assim que ele lê (fica lá depois da resposta).
OLHINHOS = "👀"
# A pasta de cada grupo (memorias/grupos/<id>/): só o Jarvis daquele grupo
# entra nela. A memória do grupo (anotações, lista, recados) é o memoria.md,
# que o Léo vê e edita na aba "Memórias" da janela e do app.
from jarvis import memorias  # noqa: E402
CASA = memorias.GRUPOS  # trocado por grupo em _atender (pasta_do_grupo)
MEMORIA = "memoria.md"
NOVIDADES = Path.home() / ".local/share/jarvis/novidades.jsonl"
# O limite do Claude é do dono: a família não pode gastar tudo. Por grupo
# (decisão do Léo, 09/11/2026: 50 por grupo).
MAX_POR_HORA = 50
# Depois de responder alguém, só as mensagens DESSA pessoa chegam sem chamar o
# nome, por um tempo (09/11/2026: com a conversa aberta para o grupo todo, ele
# se metia no papo dos outros).
CONVERSA_ABERTA_S = 2 * 60
# O pedido ao dono que o app não recebeu vai para o WhatsApp dele depois disto.
ESPERA_DO_APP_S = 45


class Msg(NamedTuple):
    quem: str          # o nome para mostrar
    texto: str
    quando: dt.datetime
    id: str = ""       # o id da mensagem no WhatsApp (para o 👀)
    remetente: str = ""  # como o banco guarda quem mandou (número ou LID; o dono: o número dele)
    midia: str = ""    # "audio", "image"... (o áudio vira texto: jarvis/grupo/audios.py)


def chamou(texto: str) -> list[str]:
    """Quem a mensagem chama pelo nome, na ordem: ["jarvis"], ["friday"], os dois ou nenhum."""
    t = f" {normalizar(texto)} "
    achados = [(t.find(p), p) for p in PREFIXOS if f"{p}" in t]
    return [p for _, p in sorted(achados)]


def de_bot(texto: str) -> bool:
    return texto.startswith(tuple(PREFIXOS.values()))


_MEXE_EM_ARQUIVO = {"criar ou editar arquivo", "apagar, mover ou mexer em arquivo", "apagar ou mexer em arquivo"}
_CAMINHO_DE_FORA = re.compile(r"(^|[\s\"'=<>|;&(])/(?!dev/null\b)")
_NUNCA = re.compile(r"\b(sudo|chmod|chown|dd|crontab|shred|truncate|git|ln)\b")
_COM_CAMINHO = {"Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep", "LS"}
# No terminal: qualquer caminho da casa do dono que não seja a pasta do grupo,
# sair da pasta com "..", e os bancos/segredos pelo nome.
_PESSOAL = re.compile(r"(~|\$HOME|\$\{HOME\}|/home/[\w.-]+)(?!/\.local/share/jarvis/grupo\b)"
                      r"|\.\./|/root\b|/etc/(shadow|passwd)|\bsqlite3?\b|messages\.db|whatsapp\.db"
                      r"|\.ssh\b|\.env\b|senha|password|token|cookie"
                      # o Windows: a pasta do usuário e os outros discos
                      r"|\$env:|%\w+%|\b[a-z]:[\\/]", re.I)


def trava_do_grupo(ferramenta: str, entrada: dict, casa: Path | None = None) -> str | None:
    """Por que a ferramenta é barrada no grupo, ou None se pode.

    Livre: conversar, internet, terminal e anotar na própria pasta. Barrado:
    tudo que é do dono (fora da pasta do grupo), o que as travas da voz
    barram para outra pessoa (apagar, instalar, desligar...), a tela e os
    conectores da conta dele (Gmail, Agenda, Drive)."""
    casa = casa or CASA
    if ferramenta.startswith("mcp__"):
        return None if ferramenta.startswith("mcp__grupo__") else "as contas do dono (e-mail, agenda...)"
    if ferramenta in _COM_CAMINHO:
        caminho = str(entrada.get("file_path") or entrada.get("notebook_path") or entrada.get("path") or "")
        padrao = str(entrada.get("pattern") or "") if ferramenta == "Glob" else ""
        for c in (caminho, padrao):
            if c and (c.startswith(("/", "~")) or ".." in c):
                alvo = Path(c.split("*")[0] or "/").expanduser()
                alvo = (casa / alvo).resolve() if not alvo.is_absolute() else alvo.resolve()
                if alvo != casa.resolve() and casa.resolve() not in alvo.parents:
                    return "abrir ou mexer em coisa do dono (fora da sua pasta)"
        return None
    if ferramenta in travas.TERMINAIS:
        comando = str(entrada.get("command") or "")
        if travas.mexe_na_tela(comando):
            return "bloquear ou desbloquear o PC"
        if _PESSOAL.search(comando):
            return "abrir coisa do dono (fora da sua pasta)"
        motivo = travas.precisa_do_leo(ferramenta, entrada, casa / "nada.md")
        # Gravar, mover e apagar na própria pasta (o terminal roda dentro dela)
        # pode; com qualquer caminho de fora, ou sudo/permissões, não. No PowerShell
        # (Windows) os caminhos são outros: lá, mexer em arquivo só pelo Write/Edit.
        if motivo in _MEXE_EM_ARQUIVO and ferramenta == "Bash" and not _CAMINHO_DE_FORA.search(comando) \
                and not _NUNCA.search(comando):
            return None
        return motivo
    return None


class GrupoFamilia(threading.Thread):
    def __init__(self, whatsapp, binario: str, modelo: str, app_desde=None, transcrever=None,
                 falar=None) -> None:
        super().__init__(name="grupo-familia", daemon=True)
        self.whatsapp = whatsapp
        self.binario = binario
        self.modelo = modelo
        # Desde quando o app do celular está conectado (a ponte), ou None.
        self._app_desde = app_desde or (lambda: None)
        # Pedidos ao dono que foram para o WhatsApp dele: id -> quando foi.
        self._pelo_whats: dict[str, dt.datetime] = {}
        self._pelo_app: set[str] = set()
        # Até onde as respostas dele já foram usadas: um "sim" vale um pedido só.
        self._resposta_usada = dt.datetime.now()
        # Para o laço principal: ("executar", texto) e ("notificar", texto).
        self._saidas: queue.Queue[tuple[str, str]] = queue.Queue()
        # Por grupo (jid): as respostas da última hora, até onde já leu e até
        # quando a conversa fica aberta.
        self._chamadas: dict[str, deque[float]] = {}
        self._visto: dict[str, dt.datetime] = {}
        # (grupo, persona) -> {remetente: até quando a conversa com ele fica aberta}
        self._aberta: dict[tuple[str, str], dict[str, float]] = {}
        # O histórico de cada grupo, puxado do celular e escrito em historico.txt.
        # Os áudios viram texto com o Whisper do Jarvis (`transcrever`: áudio -> texto).
        self._audios = audios.Audios(whatsapp, transcrever) if transcrever else None
        # A resposta em áudio: (persona, texto) -> caminho de um .ogg, ou None.
        self._falar = falar
        self._puxador = historico.Puxador(whatsapp, self._quem, tuple(PREFIXOS.values()), self._audios)

    def pegar(self) -> tuple[str, str] | None:
        try:
            return self._saidas.get_nowait()
        except queue.Empty:
            return None

    # -- o grupo ----------------------------------------------------------------

    def _jids(self) -> list[str]:
        return ajustes.grupos_ativos()

    def _nome(self, jid: str) -> str:
        try:
            return self.whatsapp.nome_de(jid) or "grupo"
        except Exception:
            return "grupo"

    def _dono(self) -> str:
        return ajustes.nome_de_quem_usa() or "dono"

    def _quem(self, remetente: str, minha: bool, texto: str = "") -> str:
        if minha and de_bot(texto):
            return next(NOMES[p] for p, pre in PREFIXOS.items() if texto.startswith(pre))
        if minha:
            return self._dono()
        try:
            return self.whatsapp.nome_de(remetente if "@" in remetente else remetente + "@lid")
        except Exception:
            return "alguém"

    def _mensagens(self, jid: str, quantas: int = 15) -> list[Msg]:
        """Mais antiga primeiro."""
        linhas = self.whatsapp._consultar(
            "SELECT sender, is_from_me, content, timestamp, id, media_type FROM messages WHERE chat_jid = ? "
            "ORDER BY timestamp DESC LIMIT ?", (jid, quantas))
        feitos = self._audios.todas(jid) if self._audios else {}
        dos_bots = self._audios.do_bot(jid) if self._audios else {}
        saida = []
        for s, eu, c, t, i, midia in reversed(linhas):
            texto = c or "(mídia)"
            if midia == "audio":
                texto = audios.Audios.como_texto(feitos.get(str(i or "")))
                bot = next((p for p, n in NOMES.items() if n == dos_bots.get(str(i or ""))), None)
                if bot:  # o áudio que o Jarvis/Friday mandou conta como mensagem deles
                    texto = f"{PREFIXOS[bot]} {texto}"
            saida.append(Msg(self._quem(s or "", bool(eu), texto if eu else c or ""), texto,
                             self.whatsapp._quando(t), str(i or ""), "eu" if eu else (s or ""), midia or ""))
        return saida

    def _mandar(self, jid: str, texto: str, persona: str = "jarvis") -> None:
        self.whatsapp.enviar(jid, f"{PREFIXOS[persona]} {texto.strip()}")

    def _mandar_audio(self, jid: str, persona: str, texto: str) -> bool:
        """Fala o texto na voz da persona e manda como mensagem de voz."""
        if not self._falar:
            return False
        try:
            caminho = self._falar(persona, texto)
        except Exception:
            caminho = None
        if not caminho:
            return False
        try:
            ok, _ = self.whatsapp.enviar(jid, "", arquivo=str(caminho))
        finally:
            Path(caminho).unlink(missing_ok=True)
        id_msg = getattr(self.whatsapp, "ultimo_id", "")
        if ok and id_msg and self._audios:
            self._audios.marcar_do_bot(jid, id_msg, NOMES[persona], texto)
        return ok

    def _abrir(self, jid: str, persona: str, msgs: list[Msg]) -> None:
        """A conversa fica aberta só com quem falou com ele agora; se essa
        pessoa estava conversando com o outro (Jarvis/Friday), passa a ser com este."""
        for m in msgs:
            for p in PREFIXOS:
                self._aberta.setdefault((jid, p), {}).pop(m.remetente, None)
            self._aberta[(jid, persona)][m.remetente] = time.time() + CONVERSA_ABERTA_S

    def _olhar(self, jid: str, m: Msg) -> None:
        """O 👀: "já li, estou pensando". Sem a ponte nova, só não aparece."""
        if not m.id or not hasattr(self.whatsapp, "reagir"):
            return
        try:
            self.whatsapp.reagir(jid, m.id, "" if m.remetente == "eu" else m.remetente, OLHINHOS)
        except Exception:
            pass

    def _notificar(self, texto: str, titulo: str = "Grupo do WhatsApp") -> None:
        """Para o dono: notificação no PC e no app (nada de WhatsApp)."""
        try:   # o aviso do PC (Linux); sem ele (Windows), o app e a janela avisam do mesmo jeito
            subprocess.run(["notify-send", "-a", "NOVA", "-i", "jarvis-atomo", titulo, texto],
                           check=False, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
        NOVIDADES.touch(mode=0o600, exist_ok=True)
        with NOVIDADES.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": time.time_ns() // 1_000_000, "titulo": titulo,
                                "texto": texto, "tipo": "grupo"}, ensure_ascii=False) + "\n")
        self._saidas.put(("notificar", texto))

    # -- o laço -----------------------------------------------------------------

    def run(self) -> None:
        threading.Thread(target=self._laco_historico, name="grupo-historico", daemon=True).start()
        while True:
            time.sleep(3)
            try:
                self._uma_volta()
            except Exception:
                pass  # banco ocupado, ponte fora: tenta na próxima

    def _laco_historico(self) -> None:
        """Devagar e à parte das respostas: um pedido por grupo a cada volta."""
        while True:
            time.sleep(15)
            for jid in self._jids():
                try:
                    self._puxador.passo(jid)
                    if self._audios:  # os áudios antigos, um por volta (o mais novo primeiro)
                        for id_msg in self._audios.pendentes(jid)[:1]:
                            self._audios.transcrever(jid, id_msg)
                    self._puxador.escrever(jid, self._nome(jid))
                except Exception:
                    pass  # ponte fora, banco ocupado: na próxima volta

    def _aprovacoes_pelo_whatsapp(self) -> None:
        """O pedido ao dono que o app não recebeu (app fechado, sem internet,
        Tailscale fora) vai para o WhatsApp dele, no chat com ele mesmo, e ele
        responde "sim" ou "não" ali. Só quando o app não funciona (decisão do
        Léo, 25/10/2026): com o app conectado desde antes do pedido, fica lá."""
        pendentes = [a for a in aprovacoes.pendentes() if a.get("origem") == "grupo"]
        ids = {a["id"] for a in pendentes}
        self._pelo_whats = {i: q for i, q in self._pelo_whats.items() if i in ids}
        self._pelo_app &= ids
        eu = ""
        for a in pendentes:
            if a["id"] in self._pelo_whats or a["id"] in self._pelo_app \
                    or time.time() - a["criado"] < ESPERA_DO_APP_S:
                continue
            desde = self._app_desde()
            if desde is not None and desde <= a["criado"]:
                self._pelo_app.add(a["id"])  # o app estava lá: recebeu
                continue
            eu = eu or self.whatsapp.meu_jid()
            if not eu:
                return
            ate = dt.datetime.fromtimestamp(a["expira_em"]).strftime("%H:%M")
            onde = f"no grupo \"{self._nome(a['jid'])}\"" if a.get("jid") else "no grupo"
            ok, _ = self.whatsapp.enviar(eu, f"{PREFIXO} {a['quem']} pediu {onde}: "
                                             f"\"{a['pedido']}\". O app não está conectado, então pergunto "
                                             f"aqui: responde *sim* para liberar ou *não* para recusar "
                                             f"(vale até {ate}).")
            if ok:
                self._pelo_whats[a["id"]] = dt.datetime.now()
        if not self._pelo_whats:
            return
        eu = eu or self.whatsapp.meu_jid()
        if not eu:
            return
        # A resposta: "sim" ou "não" curtinho, escrita por ele depois do pedido
        # (a ponte não guarda o que o Jarvis manda; o que aparece veio dele).
        desde = max(min(self._pelo_whats.values()), self._resposta_usada)
        for quando, texto in sorted(self.whatsapp.eu_mandei_desde(eu, desde)):
            if texto.startswith(PREFIXO) or len(normalizar(texto).split()) > 3:
                continue
            sim = sim_ou_nao(texto)
            antes = [(q, i) for i, q in self._pelo_whats.items() if q < quando]
            if sim is None or not antes:
                continue
            _, id_pedido = max(antes)  # o pedido mais recente antes da resposta
            del self._pelo_whats[id_pedido]
            self._resposta_usada = quando
            resultado = aprovacoes.responder(id_pedido, sim)
            self.whatsapp.enviar(eu, f"{PREFIXO} " + {"aprovado": "Liberado, já vou fazer.",
                                                      "recusado": "Recusado, aviso no grupo."}
                                 .get(resultado, "Esse pedido já tinha vencido."))
            if not self._pelo_whats:
                return

    def _uma_volta(self) -> None:
        jids = self._jids()
        self._aprovacoes_pelo_whatsapp()
        for a in aprovacoes.resolvidas("grupo"):
            # O pedido volta para o grupo de onde veio (os antigos, sem jid: o primeiro).
            jid = a.get("jid") or (jids[0] if jids else "")
            if not jid:
                continue
            nome = self._nome(jid)
            if a["estado"] == "aprovado":
                self._saidas.put(("executar",
                    f"[Pedido de {a['quem']} no grupo \"{nome}\" do WhatsApp, APROVADO pelo "
                    f"{self._dono()} no celular] {a['pedido']}\n"
                    f"Faça o pedido. Depois responda no grupo com a ferramenta whatsapp_mandar "
                    f"(jid {jid}, nome \"{nome}\"), começando o texto com \"{PREFIXO}\"."))
            else:
                motivo = "não liberou" if a["estado"] == "recusado" else "não respondeu a tempo"
                self._mandar(jid, f"O {self._dono()} {motivo} o pedido de {a['quem']}.")
        for jid in jids:
            try:
                self._volta_do_grupo(jid)
            except Exception:
                pass  # um grupo com problema não trava os outros
        # Grupo desmarcado esquece onde parou: se voltar, começa do zero (sem responder o velho).
        for jid in set(self._visto) - set(jids):
            self._visto.pop(jid, None)

    def _volta_do_grupo(self, jid: str) -> None:
        if jid not in self._visto:  # grupo novo (ou religado): só o que chegar daqui pra frente
            self._visto[jid] = dt.datetime.now()
            return
        # O relógio interno: recados que ele deixou para si mesmo (jarvis/nucleo/recados.py),
        # dentro da memória do grupo.
        venceram = recados.vencidos(memorias.pasta_do_grupo(jid) / MEMORIA)
        if venceram:
            asyncio.run(self._atender(jid, "jarvis", [], recados_da_hora=venceram))
        novas = [m for m in self._mensagens(jid, 20) if m.quando > self._visto[jid]]
        if not novas:
            return
        self._visto[jid] = max(m.quando for m in novas)
        # Áudio novo vira texto antes de tudo: "Jarvis, ..." falado chama igual ao escrito.
        if self._audios:
            novas = [m._replace(texto=audios.Audios.como_texto(self._audios.transcrever(jid, m.id)))
                     if m.midia == "audio" and m.texto == "(áudio)" else m for m in novas]
        agora = time.time()
        # Para cada um (Jarvis e Friday): quem chamou pelo nome, e quem estava
        # conversando com ele e continuou (só essa pessoa, nunca o grupo todo).
        trabalho: list[tuple[str, list[Msg], list[Msg]]] = []
        for persona in PREFIXOS:
            abertas = self._aberta.setdefault((jid, persona), {})
            for r, ate in list(abertas.items()):
                if ate < agora:
                    del abertas[r]
            chamadas, seguidas = [], []
            for m in novas:
                if de_bot(m.texto):
                    continue
                nomes = chamou(m.texto)
                if nomes and nomes[0] == persona:
                    chamadas.append(m)
                elif not nomes and m.remetente in abertas:
                    seguidas.append(m)
            if chamadas or seguidas:
                trabalho.append((persona, chamadas, seguidas))
        if not trabalho:
            return
        feitas = self._chamadas.setdefault(jid, deque())
        while feitas and feitas[0] < agora - 3600:
            feitas.popleft()
        for persona, chamadas, seguidas in trabalho:
            if len(feitas) >= MAX_POR_HORA:
                if chamadas:
                    self._mandar(jid, "Por agora já conversei bastante; daqui a pouco eu volto.", persona)
                continue
            feitas.append(agora)
            for m in chamadas:
                self._olhar(jid, m)
            asyncio.run(self._atender(jid, persona, chamadas, seguidas=seguidas))

    # -- o Claude, trancado --------------------------------------------------------

    async def _atender(self, jid: str, persona: str, chamadas: list[Msg], seguidas: list[Msg] | None = None,
                       recados_da_hora: list[str] | None = None) -> None:
        seguidas = seguidas or []
        nome = NOMES[persona]
        from claude_agent_sdk import (ClaudeAgentOptions, HookMatcher, create_sdk_mcp_server, query,
                                      tool)

        def _t(texto: str) -> dict:
            return {"content": [{"type": "text", "text": texto}]}

        mandadas: list[str] = []

        @tool("responder", f"Manda uma mensagem no grupo (o \"{PREFIXOS[persona]}\" entra sozinho).", {"texto": str})
        async def responder(args):
            mandadas.append(str(args.get("texto") or ""))
            self._mandar(jid, mandadas[-1], persona)
            self._abrir(jid, persona, chamadas + seguidas)
            return _t("Mandado no grupo.")

        @tool("responder_em_audio", "Responde com um ÁUDIO na sua voz (para quem mandou áudio). "
              "`falado`: o que você diz, como fala (sem link, lista ou emoji). `escrito`: opcional, "
              "o que não dá para ouvir (link, lista, número) vai logo depois numa mensagem escrita; "
              "senão deixe vazio.", {"falado": str, "escrito": str})
        async def responder_em_audio(args):
            falado = str(args.get("falado") or "").strip()
            escrito = str(args.get("escrito") or "").strip()
            foi = await asyncio.to_thread(self._mandar_audio, jid, persona, falado) if falado else False
            if not foi and falado:  # sem voz (caiu, ponte fora): vai escrito mesmo
                self._mandar(jid, falado, persona)
            if escrito:
                self._mandar(jid, escrito, persona)
            mandadas.append(falado + ("\n" + escrito if escrito else ""))
            self._abrir(jid, persona, chamadas + seguidas)
            return _t("Áudio mandado no grupo." if foi else "A voz falhou: foi por escrito.")

        @tool("nao_era_comigo", f"A mensagem só falava SOBRE {'o' if persona == 'jarvis' else 'a'} {nome}: "
              "avisa o dono, sem responder no grupo.", {"quem": str, "resumo": str})
        async def nao_era_comigo(args):
            self._notificar(f"{args.get('quem') or 'Alguém'} falou de {nome} no grupo: {args.get('resumo') or ''}",
                            self._nome(jid))
            return _t("O dono foi avisado.")

        @tool("pedir_ao_dono", "Pede ao dono, no celular dele, para liberar um pedido que mexe no PC ou nas "
              "coisas dele. Se ele aprovar, a NOVA do PC faz.", {"quem": str, "pedido": str})
        async def pedir_ao_dono(args):
            a = aprovacoes.criar(str(args.get("quem") or "alguém"), str(args.get("pedido") or ""), jid=jid)
            self._saidas.put(("aprovacao", a["id"]))
            return _t(f"Pedi para o {self._dono()} liberar (vale por 5 minutos). Avise no grupo.")

        servidor = create_sdk_mcp_server("grupo", tools=[responder, responder_em_audio, nao_era_comigo,
                                                         pedir_ao_dono])

        casa = memorias.pasta_do_grupo(jid)

        async def trancar(entrada, _id, _ctx) -> dict:
            motivo = trava_do_grupo(str(entrada.get("tool_name") or ""), entrada.get("tool_input") or {}, casa)
            if motivo is None:
                return {}
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": f"Neste grupo você não pode {motivo}. Se a pessoa "
                                            "precisa disso, use pedir_ao_dono; senão, resolva de outro jeito."}}

        casa.mkdir(parents=True, exist_ok=True)
        nome_grupo = self._nome(jid)
        outra = next(p for p in PREFIXOS if p != persona)
        instrucoes = PERSONA.read_text(encoding="utf-8").replace("{jeito}", JEITO[persona].read_text(encoding="utf-8")) \
            .replace("{nome}", nome).replace("{outra}", NOMES[outra]).replace("{usuario}", self._dono()) \
            .replace("{grupo}", nome_grupo).replace("{casa}", str(casa)).replace("{recados}", recados.como_usar(MEMORIA))
        opcoes = ClaudeAgentOptions(
            cli_path=self.binario, cwd=str(casa), model=self.modelo,
            setting_sources=[],  # nada do dono: nem memória, nem MCPs, nem preferências
            system_prompt=instrucoes,
            mcp_servers={"grupo": servidor},
            permission_mode="bypassPermissions",
            hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[trancar])]},
            max_turns=20, stderr=lambda _linha: None,
        )
        conversa = "\n".join(f"[{m.quando:%H:%M}] {m.quem}: {m.texto}" for m in self._mensagens(jid, 15))
        agora = dt.datetime.now().astimezone()
        if recados_da_hora:
            pedido = (f"Agora: {agora:%A, %d/%m/%Y %H:%M} (fuso UTC{agora:%z}).\n\n"
                      "As últimas mensagens do grupo, para contexto:\n" + conversa +
                      "\n\nCHEGOU A HORA destes recados que VOCÊ deixou para si mesmo; faça o que anotou "
                      "(normalmente, mandar no grupo com `responder`):\n" +
                      "\n".join(f"- {r}" for r in recados_da_hora))
            async for _ in query(prompt=pedido, options=opcoes):
                pass
            if not mandadas:
                # Texto solto não vai para o WhatsApp: se ele só escrever (sem o
                # `responder`), o recado, já fora da lista, se perderia calado.
                # (O do CIEE, 26/10/2026, saiu certo às 8h00; isto é só a garantia.)
                async for _ in query(prompt=pedido + "\n\nATENÇÃO: numa tentativa anterior você respondeu "
                                     "só com texto e NADA chegou no grupo. Só o que passa pela ferramenta "
                                     "`responder` chega. Mande agora o recado com `responder`.", options=opcoes):
                    pass
            if not mandadas:
                self._notificar("Não consegui entregar no grupo o recado: " + "; ".join(recados_da_hora), nome_grupo)
            return
        pedido = (f"Agora: {agora:%A, %d/%m/%Y %H:%M} (fuso UTC{agora:%z}).\n\n"
                  "As últimas mensagens do grupo, para contexto:\n" + conversa)
        if chamadas:
            pedido += (f"\n\nAs NOVAS que chamam você ({nome}) pelo nome (trate cada uma; cada "
                       "pessoa recebe a resposta dela):\n" + "\n".join(f"- {m.quem}: {m.texto}" for m in chamadas))
        if seguidas:
            pedido += ("\n\nNOVAS de quem estava conversando com você, sem chamar o seu nome. Pode ser a "
                       "continuação da conversa com você, ou já outro assunto com o grupo. Só responda se "
                       "for claramente com você; na dúvida, fique quieto (não chame ferramenta nenhuma):\n"
                       + "\n".join(f"- {m.quem}: {m.texto}" for m in seguidas))
        async for _ in query(prompt=pedido, options=opcoes):
            pass
