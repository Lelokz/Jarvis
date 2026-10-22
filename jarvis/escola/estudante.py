"""Estudante Online (SED-SC): o Jarvis entra com o login do gov.br do Léo.

O CPF e a senha ficam em ~/.local/share/jarvis/escola.env (só neste PC,
fora do git; foi o Léo que preencheu). Se o gov.br pedir um desafio do
captcha, o Jarvis NÃO tenta resolver: avisa para o Léo entrar à mão.
"""

from __future__ import annotations

import re
from pathlib import Path

LOGIN = "https://estudanteonline.sed.sc.gov.br/loginweb.aspx"
CREDENCIAIS = Path.home() / ".local/share/jarvis/escola.env"
# A sessão (cookies) depois que o Léo entra: a leitura escondida carrega daqui.
SESSAO = Path.home() / ".local/share/jarvis/escola-sessao.json"


BASE = "https://estudanteonline.sed.sc.gov.br/"


class PrecisaDoLeo(Exception):
    """O Jarvis não conseguiu entrar sozinho: o Léo tem que entrar uma vez."""


def _credenciais() -> tuple[str, str]:
    valores = {}
    for linha in CREDENCIAIS.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.lstrip().startswith("#"):
            chave, valor = linha.split("=", 1)
            valores[chave.strip()] = valor.strip()
    cpf = "".join(c for c in valores.get("CPF", "") if c.isdigit())
    senha = valores.get("SENHA", "")
    if not cpf or not senha:
        raise PrecisaDoLeo(f"falta o CPF ou a senha em {CREDENCIAIS}")
    return cpf, senha


def logado(pagina) -> bool:
    return "estudanteonline.sed.sc.gov.br" in pagina.url and "loginweb" not in pagina.url.lower()


def entrar(pagina) -> None:
    """Abre o Estudante Online e, se tiver deslogado, entra pelo gov.br."""
    pagina.goto(LOGIN, wait_until="load")
    pagina.wait_for_timeout(2000)
    if logado(pagina):
        return
    cpf, senha = _credenciais()
    pagina.click("#BTNBTNALUNO")
    pagina.wait_for_url("**sso.acesso.gov.br/**", timeout=30000)
    if logado(pagina):  # o gov.br ainda lembrava: voltou direto
        return
    pagina.fill("#accountId", cpf)
    pagina.click("#enter-account-id")
    pagina.wait_for_selector("#password", timeout=30000)
    pagina.fill("#password", senha)
    pagina.click("#submit-button")
    try:
        pagina.wait_for_url("**estudanteonline.sed.sc.gov.br/**", timeout=30000)
    except Exception:
        raise PrecisaDoLeo("o gov.br não deixou entrar sozinho (captcha ou senha)") from None
    pagina.wait_for_load_state("load")


def salvar_sessao(contexto) -> None:
    SESSAO.touch(mode=0o600, exist_ok=True)
    contexto.storage_state(path=str(SESSAO))


PORTA = 9333  # só em 127.0.0.1: o Jarvis se liga à janela depois do login


def _abas() -> list[dict]:
    import json
    import urllib.request
    with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/json", timeout=3) as r:
        return json.load(r)


def entrar_com_o_leo(playwright, espera_s: int = 600):
    """Abre uma janela COMUM do Chromium (sem automação: assim o captcha
    trata o Léo como pessoa) e espera ele entrar. Só depois o Jarvis se liga
    à janela, guarda a sessão e devolve (navegador, página logada).
    Para fechar a janela: `fechar_janela(navegador)` (o close() só desliga)."""
    import subprocess
    import time
    from .navegador import ARGS, CHROMIUM, PERFIL
    subprocess.Popen([str(CHROMIUM), f"--user-data-dir={PERFIL}", f"--remote-debugging-port={PORTA}",
                      *ARGS, LOGIN], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    fim = time.time() + espera_s
    while time.time() < fim:
        time.sleep(3)
        try:
            if any("estudanteonline.sed.sc.gov.br" in a.get("url", "") and "loginweb" not in a["url"].lower()
                   for a in _abas()):
                break
        except OSError:
            pass
    else:
        raise PrecisaDoLeo("o Léo não entrou a tempo")
    time.sleep(3)
    navegador = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{PORTA}")
    contexto = navegador.contexts[0]
    salvar_sessao(contexto)
    pagina = next(p for p in contexto.pages if logado(p))
    return navegador, pagina


def fechar_janela(navegador) -> None:
    navegador.new_browser_cdp_session().send("Browser.close")


def abrir_escondido(playwright):
    """Navegador escondido com a sessão guardada: (navegador, contexto)."""
    from .navegador import ARGS, CHROMIUM
    if not SESSAO.exists():
        raise PrecisaDoLeo("nunca entrou")
    navegador = playwright.chromium.launch(executable_path=str(CHROMIUM), headless=True, args=ARGS)
    return navegador, navegador.new_context(storage_state=str(SESSAO))


def manter() -> bool:
    """Visita o início para a sessão não cair. True se ainda está logado."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        navegador, contexto = abrir_escondido(p)
        pagina = contexto.new_page()
        pagina.goto(BASE + "wp_dashboardfigma.aspx", wait_until="load")
        pagina.wait_for_timeout(1500)
        ok = logado(pagina)
        if ok:
            salvar_sessao(contexto)
        navegador.close()
        return ok


def _linhas(pagina) -> list[list[str]]:
    """As linhas da tabela da página, cada uma com as células que têm texto."""
    # Só as células visíveis: a tabela traz códigos escondidos (display:none).
    return pagina.evaluate("""() => [...document.querySelectorAll("tr[id^='GridContainerRow_']")]
        .map(tr => [...tr.querySelectorAll('td')]
            .filter(td => getComputedStyle(td).display !== 'none')
            .map(td => td.innerText.trim()).filter(t => t))
        .filter(l => l.length)""")


def _periodo(pagina, numero: int) -> None:
    if pagina.locator("#vPERIODO").input_value() != str(numero):
        pagina.select_option("#vPERIODO", str(numero))
        pagina.wait_for_timeout(3000)


def _notas_do_periodo(pagina) -> dict[str, str]:
    """Abre cada matéria e guarda o que aparece embaixo dela (as avaliações,
    ou "Sem avaliação ou notas não liberadas.")."""
    materias = [l[0] for l in _linhas(pagina)]
    notas = {}
    for i, materia in enumerate(materias, start=1):
        seta = pagina.locator(f"#span_vDETAILWEBCOMPONENT_{i:04d} a")
        if not seta.count():
            continue
        seta.click()
        pagina.wait_for_timeout(2500)
        texto = pagina.inner_text("#GridContainerDiv") if pagina.locator("#GridContainerDiv").count() \
            else pagina.inner_text("body")
        depois = texto.split(materia, 1)[-1]
        proxima = materias[i] if i < len(materias) else None
        if proxima and proxima in depois:
            depois = depois.split(proxima, 1)[0]
        notas[materia] = " ".join(depois.split())
        seta.click()  # fecha de novo
        pagina.wait_for_timeout(1000)
    return notas


def _agenda(pagina, hoje) -> dict[str, list[str]]:
    """As atividades dos dias de hoje até o fim do mês."""
    pagina.goto(BASE + "wp_dashboardfigma.aspx", wait_until="load")
    pagina.wait_for_timeout(1500)
    pagina.goto(BASE + "wp_agenda.aspx", wait_until="load")
    pagina.wait_for_timeout(3000)
    agenda = {}
    for dia in range(hoje.day, 32):
        celula = pagina.locator(f"span[id*='vDISCIPLINAATIVIDADECOL']:text-is('{dia}')").first
        if not celula.count():
            break
        celula.click()
        pagina.wait_for_timeout(2500)
        texto = pagina.inner_text("body")
        cabecalho = re.search(rf"\n{dia} de \w+ de \d{{4}}\n", texto)
        if not cabecalho:
            continue
        resto = texto[cabecalho.end():].split("Fim da lista", 1)[0]
        itens = [l.strip() for l in resto.splitlines() if l.strip()]
        if itens:
            agenda[f"{hoje.year}-{hoje.month:02d}-{dia:02d}"] = itens
    return agenda


def ler(playwright) -> dict:
    """Boletim, faltas e notas dos três períodos, e a agenda do mês."""
    import datetime
    navegador, contexto = abrir_escondido(playwright)
    try:
        pagina = contexto.new_page()
        pagina.goto(BASE + "wp_dashboardfigma.aspx", wait_until="load")
        pagina.wait_for_timeout(1500)
        if not logado(pagina):
            raise PrecisaDoLeo("a sessão caiu")
        dados = {"boletim": {}, "faltas": {}, "notas": {}}
        for pagina_do_site, chave in (("wp_boletim_figma.aspx", "boletim"), ("wp_consultafaltas_figma.aspx", "faltas"),
                                      ("wp_consultanotas_figma.aspx", "notas")):
            pagina.goto(BASE + pagina_do_site, wait_until="load")
            pagina.wait_for_timeout(3000)
            for numero in (1, 2, 3):
                _periodo(pagina, numero)
                if chave == "boletim":  # matéria, faltas, média
                    valor = {l[0]: {"faltas": l[1], "media": l[2]} for l in _linhas(pagina) if len(l) >= 3}
                elif chave == "faltas":
                    valor = {l[0]: l[1] for l in _linhas(pagina) if len(l) >= 2}
                else:
                    valor = _notas_do_periodo(pagina)
                dados[chave][f"{numero}º período"] = valor
        dados["agenda"] = _agenda(pagina, datetime.date.today())
        salvar_sessao(contexto)
        return dados
    finally:
        navegador.close()
