"""O "Conectar" de Ajustes → Conexões (janela e app, beta 0.17): o passo a
passo de cada conexão. A janela pede ({"pedir": "conexao", "id", "acao",
"valor"}) e repete o "estado" a cada 2 s enquanto o passo a passo está aberto;
a resposta vai só para ela ({"ev": "conexao", ...}).

Tudo aqui é rápido (a ponte responde na hora): ler arquivo, perguntar à ponte
do WhatsApp ou ao Tailscale com teto curto, ou soltar um processo. Nada roda
como administrador: o que precisa de senha vira um comando para copiar.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.request
from pathlib import Path

from jarvis import ajustes
from jarvis.config import Config

# A ponte do WhatsApp que ESTE módulo subiu (para cancelar ou trocar o
# telefone). A que o jarvis.sh sobe se acha pelo arquivo do pareamento.
_ponte: subprocess.Popen | None = None
_telefone = ""


def agir(cfg: Config, dados: dict, conectados: set[str]) -> dict:
    id_, acao, valor = dados.get("id", ""), dados.get("acao", "estado"), dados.get("valor", "")
    funcao = {"whatsapp": _whatsapp, "grupo": _grupo, "fora": _fora,
              "celular": _celular, "musica": _musica, "vozes": _vozes}.get(id_)
    if funcao is None:
        return {"ev": "conexao", "id": id_, "estado": "desligado"}
    try:
        resposta = funcao(cfg, acao, valor, conectados)
    except Exception as e:  # o passo a passo mostra, em vez de travar a janela
        resposta = {"estado": "erro", "detalhe": f"{e.__class__.__name__}: {e}"[:200]}
    return {"ev": "conexao", "id": id_, **resposta}


def _qr(texto: str) -> str:
    import segno
    return segno.make(texto, error="l").png_data_uri(scale=6, border=2, dark="#0a0c10", light="#ffffff")


# -- WhatsApp ------------------------------------------------------------------

def _pasta_ponte(cfg: Config) -> Path:
    # O banco fica em whatsapp-bridge/store/messages.db.
    return Path(cfg.whatsapp.banco).expanduser().parent.parent


def _api(cfg: Config, caminho: str, corpo: bytes | None = None) -> dict | None:
    base = cfg.whatsapp.api.rsplit("/api/", 1)[0]
    try:
        with urllib.request.urlopen(urllib.request.Request(base + caminho, corpo), timeout=1.5) as r:
            return json.loads(r.read() or b"{}")
    except (OSError, ValueError):
        return None


def _pareamento(cfg: Config) -> dict:
    """O que a ponte escreveu em store/pareamento.json (patch da NOVA)."""
    arquivo = _pasta_ponte(cfg) / "store" / "pareamento.json"
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        idade = time.time() - arquivo.stat().st_mtime
    except (OSError, ValueError):
        return {}
    # O QR troca a cada ~20 s; parado há mais de 70 s, a ponte já desistiu.
    if dados.get("estado") == "esperando" and idade > 70:
        dados = {"estado": "expirou"}
    return dados


def _subir_ponte(cfg: Config, telefone: str) -> None:
    global _ponte, _telefone
    if _ponte is not None and _ponte.poll() is None:
        _ponte.terminate()
        _ponte.wait(timeout=5)
    pasta = _pasta_ponte(cfg)
    (pasta / "store" / "pareamento.json").unlink(missing_ok=True)
    env = dict(os.environ, NOVA_TELEFONE=telefone)
    log = open(Path.home() / ".local/share/jarvis/whatsapp-bridge.log", "ab")
    _ponte = subprocess.Popen(["./whatsapp-bridge"], cwd=pasta, env=env, stdout=log, stderr=log,
                              stdin=subprocess.DEVNULL, start_new_session=True,
                              preexec_fn=lambda: os.umask(0o077))
    _telefone = telefone


def _estado_whatsapp(cfg: Config) -> dict:
    api = _api(cfg, "/api/estado")
    if api and api.get("logado"):
        return {"estado": "conectado" if api.get("conectado") else "pronto"}
    p = _pareamento(cfg)
    if p.get("estado") == "esperando":
        return {"estado": "esperando", "qr": _qr(p["qr"]) if p.get("qr") else "",
                "codigo": p.get("codigo", ""), "erro_codigo": p.get("erro", "")}
    if p.get("estado") == "conectado":
        return {"estado": "conectado"}
    if _ponte is not None and _ponte.poll() is None:
        return {"estado": "abrindo"}  # subiu agora, o primeiro QR ainda não veio
    return {"estado": p.get("estado") or "desligado"}  # expirou, saiu ou nunca ligou


def _whatsapp(cfg: Config, acao: str, valor: str, _conectados) -> dict:
    if not (_pasta_ponte(cfg) / "whatsapp-bridge").is_file():
        return {"estado": "falta", "detalhe": "A ponte do WhatsApp não está instalada neste PC."}
    if acao == "conectar":
        atual = _estado_whatsapp(cfg)
        telefone = "".join(c for c in valor if c.isdigit())
        # Número novo, ou o mesmo depois de o WhatsApp recusar: sobe a ponte de novo.
        quer_codigo = telefone and (telefone != _telefone or atual.get("erro_codigo"))
        if atual["estado"] in ("conectado", "pronto") or (atual["estado"] in ("esperando", "abrindo")
                                                        and not quer_codigo):
            return atual
        if atual["estado"] == "esperando" and (_ponte is None or _ponte.poll() is not None):
            # Esperando numa ponte que não é a nossa (a do jarvis.sh, ainda sem conta):
            # o QR dela serve para a janela; o código (o app) pede uma nossa no lugar.
            if not quer_codigo:
                return atual
            subprocess.run(["pkill", "-x", "whatsapp-bridge"], capture_output=True)
            time.sleep(0.5)
        _subir_ponte(cfg, telefone)
        return {"estado": "abrindo"}
    if acao == "cancelar":
        if _ponte is not None and _ponte.poll() is None and _estado_whatsapp(cfg)["estado"] != "conectado":
            _ponte.terminate()
        return {"estado": "desligado"}
    if acao == "desconectar":
        r = _api(cfg, "/api/sair", b"{}")
        return {"estado": "desligado"} if r and r.get("ok") else \
            {"estado": "erro", "detalhe": "A ponte não respondeu. Tenta de novo daqui a pouco."}
    return _estado_whatsapp(cfg)


# -- Grupo do WhatsApp ---------------------------------------------------------

def _grupo(cfg: Config, acao: str, valor: str, _conectados) -> dict:
    banco = Path(cfg.whatsapp.banco).expanduser()
    if not banco.is_file():
        return {"estado": "falta", "detalhe": "Conecta o WhatsApp primeiro."}
    if acao == "escolher" and valor.endswith("@g.us"):
        ajustes.mudar(grupo_jid=valor, grupo_ligado=True)
    elif acao == "desconectar":
        ajustes.mudar(grupo_jid="", grupo_ligado=False)
    con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True, timeout=3)
    try:
        linhas = con.execute("SELECT jid, name FROM chats WHERE jid LIKE '%@g.us' AND name != '' "
                             "ORDER BY last_message_time DESC LIMIT 40").fetchall()
    finally:
        con.close()
    dados = ajustes.ler()
    return {"estado": "conectado" if dados["grupo_jid"] and dados["grupo_ligado"]
            else "pronto" if dados["grupo_jid"] else "desligado",
            "grupos": [{"jid": j, "nome": n} for j, n in linhas],
            "escolhido": dados["grupo_jid"], "ligado": dados["grupo_ligado"]}


# -- Fora de casa (Tailscale) e celular -----------------------------------------

def _tailscale_exe() -> str:
    return shutil.which("tailscale") or str(Path.home() / ".local/bin/tailscale")


def _ts(*args: str, teto: float = 2.0) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run([_tailscale_exe(), *args], capture_output=True, text=True, timeout=teto)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _situacao_tailscale(cfg: Config) -> dict:
    """instalado, conta, celular (o nome dele), servindo e o endereço do PC."""
    s = {"instalado": False, "conta": "", "celular": "", "servindo": False, "endereco": ""}
    r = _ts("status", "--json")
    if r is None:
        return s
    s["instalado"] = True
    try:
        st = json.loads(r.stdout or "{}")
    except ValueError:
        return s
    if st.get("BackendState") != "Running":
        return s
    eu = st.get("Self") or {}
    s["endereco"] = (eu.get("DNSName") or "").rstrip(".")
    usuario = (st.get("User") or {}).get(str(eu.get("UserID")), {})
    s["conta"] = usuario.get("LoginName") or "a tua conta"
    for par in (st.get("Peer") or {}).values():
        if par.get("OS") in ("android", "iOS"):
            s["celular"] = par.get("HostName") or "o celular"
            break
    servir = _ts("serve", "status", "--json")
    s["servindo"] = bool(servir and servir.returncode == 0 and f":{cfg.remoto.porta}" in servir.stdout)
    return s


def _fora(cfg: Config, acao: str, valor: str, _conectados) -> dict:
    s = _situacao_tailscale(cfg)
    detalhe = ""
    if acao == "conectar" and s["celular"] and not s["servindo"]:
        # O último passo é nosso: levar a porta do celular para a rede do Tailscale.
        r = _ts("serve", "--bg", str(cfg.remoto.porta), teto=8)
        if r is None or r.returncode != 0:
            detalhe = ("O Tailscale não deixou. Roda isto uma vez no terminal e tenta de novo: "
                       "sudo tailscale set --operator=$USER")
        s = _situacao_tailscale(cfg)
    elif acao == "desconectar" and s["servindo"]:
        _ts("serve", "reset", teto=5)
        s = _situacao_tailscale(cfg)
    pronto = s["instalado"] and s["conta"] and s["celular"] and s["servindo"]
    return {"estado": "conectado" if pronto else "desligado", "detalhe": detalhe,
            "instalado": s["instalado"], "conta": s["conta"], "celular": s["celular"],
            "servindo": s["servindo"],
            "comando_instalar": "curl -fsSL https://tailscale.com/install.sh | sh",
            "comando_entrar": "sudo tailscale up --operator=$USER"}


def _celular(cfg: Config, acao: str, valor: str, conectados: set[str]) -> dict:
    s = _situacao_tailscale(cfg)
    if not s["servindo"]:
        return {"estado": "falta", "detalhe": "Liga o Fora de casa primeiro."}
    from porta_remota import ler_chave
    link = f"https://{s['endereco']}/ligar#chave={ler_chave(Path(cfg.remoto.chave))}"
    return {"estado": "conectado" if "celular-app" in conectados else "esperando", "qr": _qr(link)}


# -- Música --------------------------------------------------------------------

def _musica(cfg: Config, acao: str, valor: str, _conectados) -> dict:
    return {"estado": "conectado" if shutil.which("mpv") else "desligado",
            "comando": "sudo apt install mpv mpv-mpris"}


# -- Vozes dubladas (Ajustes → Voz e som) ---------------------------------------

def _vozes(cfg: Config, acao: str, valor: str, _conectados) -> dict:
    from jarvis import vozes
    v = vozes.escolher(valor) if acao == "escolher" and valor else vozes.estado()
    if acao == "escolher" and not v.get("detalhe"):
        # Os servidores de voz sobem com a NOVA (jarvis.sh): a pasta nova vale no próximo ligar.
        v["detalhe"] = "Achei. As vozes dubladas entram na próxima vez que a NOVA ligar."
    return {"estado": "conectado" if v["jarvis"] or v["friday"] else "desligado", **v}


if __name__ == "__main__":
    # A tela 7 do instalador (a NOVA ainda não está ligada): um pedido JSON por
    # linha na entrada, a resposta de `agir` por linha na saída.
    import sys
    from jarvis.config import carregar

    _cfg = carregar()
    for _linha in sys.stdin:
        try:
            _dados = json.loads(_linha)
        except ValueError:
            continue
        print(json.dumps(agir(_cfg, _dados, set()), ensure_ascii=False), flush=True)
