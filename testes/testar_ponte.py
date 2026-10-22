"""As propriedades da ponte, uma por uma — sem assistente, sem áudio, sem GPU.

Duas partes. A primeira testa o servidor de dentro do processo. A segunda usa
processos de verdade — o `python -m jarvis.ponte.cliente` e um "assistente
falso" que é só a ponte — para provar o que só aparece quando alguém morre:
kill -9, reconexão, e o cliente aberto ANTES de o assistente existir.

Roda dentro do contido.sh, porque dispara processos. O socket de teste mora
num diretório temporário dentro do $XDG_RUNTIME_DIR, apagado no fim.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from jarvis.ponte import protocolo  # noqa: E402
from jarvis.ponte.cliente import Cliente  # noqa: E402
from jarvis.ponte.servidor import Servidor, ServidorOcupado  # noqa: E402

ok = falhou = 0
SESSAO = {"v": protocolo.VERSAO, "nome": "Jarvis", "log": "/x/sessão.jsonl"}


def checa(nome, cond, detalhe=""):
    global ok, falhou
    if cond:
        ok += 1
        print(f"  PASSOU  {nome}", flush=True)
    else:
        falhou += 1
        print(f"  FALHOU  {nome}  {detalhe}", flush=True)


def esperar(cond, timeout=3.0):
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def esperar_texto(srv, timeout=3.0):
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        t = srv.proximo_texto()
        if t is not None:
            return t
        time.sleep(0.01)
    return None


class Conexao:
    """Socket cru, para o teste controlar exatamente o que lê e quando."""

    def __init__(self, caminho):
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.s.settimeout(3)
        self.s.connect(str(caminho))
        self.buf = b""

    def enviar(self, obj):
        self.s.sendall(protocolo.codificar(obj))

    def crus(self, dados):
        self.s.sendall(dados)

    def ler(self, n, timeout=3.0):
        fim = time.monotonic() + timeout
        saida = []
        while len(saida) < n:
            while b"\n" in self.buf and len(saida) < n:
                linha, self.buf = self.buf.split(b"\n", 1)
                saida.append(json.loads(linha))
            if len(saida) >= n:
                break
            resto = fim - time.monotonic()
            if resto <= 0:
                break
            self.s.settimeout(resto)
            try:
                dados = self.s.recv(65536)
            except (socket.timeout, OSError):
                break
            if not dados:
                break
            self.buf += dados
        return saida

    def fim_de_conexao(self, timeout=3.0):
        fim = time.monotonic() + timeout
        while time.monotonic() < fim:
            self.s.settimeout(max(0.01, fim - time.monotonic()))
            try:
                dados = self.s.recv(65536)
            except socket.timeout:
                return False
            except OSError:
                return True
            if not dados:
                return True
        return False

    def fechar(self):
        try:
            self.s.close()
        except OSError:
            pass


def rodar(base: Path) -> None:
    caminho = base / "a.sock"
    srv = Servidor(caminho, fila_max=256, sessao=SESSAO)

    print("-- criação e permissão --")
    checa("sem cliente, o nível nem é pedido", srv.quer("nivel") is False)
    srv.receber({"ev": "estado", "estado": "dormindo"})  # sem cliente: só guarda
    srv.iniciar()
    modo = stat.S_IMODE(os.stat(caminho).st_mode)
    checa("o socket nasce com permissão 0600", modo == 0o600, oct(modo))

    print("-- ola --")
    a = Conexao(caminho)
    a.enviar({"pedir": "ola", "quem": "teste"})
    ev = a.ler(2)
    checa("ola devolve a sessão, com versão e log",
          len(ev) >= 1 and ev[0].get("ev") == "sessao"
          and ev[0].get("log") == SESSAO["log"] and ev[0].get("v") == protocolo.VERSAO, ev)
    checa("e o estado guardado de ANTES de conectar",
          len(ev) == 2 and ev[1] == {"ev": "estado", "estado": "dormindo"}, ev)
    checa("com cliente, o nível passa a ser pedido", esperar(lambda: srv.quer("nivel")))

    print("-- filtro e difusão --")
    b = Conexao(caminho)
    b.enviar({"pedir": "ola"})
    b.ler(2)
    checa("evento do terminal (tempos) não é público", srv.quer("tempos") is False)
    srv.receber({"ev": "tempos", "stt_s": 0.4})
    seq = [
        {"ev": "estado", "estado": "pensando"},
        {"ev": "voce_disse", "texto": "abre gravações", "origem": "voz"},
        {"ev": "jarvis_disse", "texto": "Abri Gravações.", "acao": "abrir:gravações",
         "perguntando": False},
    ]
    for e in seq:
        srv.receber(e)
    ra, rb = a.ler(3), b.ler(3)
    checa("os dois clientes recebem a mesma sequência, em ordem e com acento",
          ra == seq and rb == seq, (ra, rb))

    print("-- pedidos --")
    a.enviar({"pedir": "falar", "texto": "  abre   o loft  "})
    checa("'falar' chega na fila, com espaço normalizado", esperar_texto(srv) == "abre o loft")
    for crus, nome in [
        (b"isto nao e json\n", "não-JSON"),
        (b"[1,2]\n", "JSON que não é objeto"),
        (b'{"pedir":"voar"}\n', "pedido desconhecido"),
        (b'{"pedir":"falar"}\n', "falar sem texto"),
        (protocolo.codificar({"pedir": "falar", "texto": "x" * (protocolo.MAX_TEXTO + 1)}), "texto longo demais"),
    ]:
        a.crus(crus)
        r = a.ler(1)
        checa(f"{nome}: erro só para quem mandou", len(r) == 1 and r[0].get("ev") == "erro", r)
    checa("nenhum pedido inválido entrou na fila", srv.proximo_texto() is None)
    checa("e o outro cliente não viu erro nenhum", b.ler(1, timeout=0.3) == [])
    a.enviar({"pedir": "ola"})
    checa("depois dos erros, a conexão segue viva",
          [e["ev"] for e in a.ler(2)] == ["sessao", "estado"])

    print("-- linha gigante sem quebra --")
    c = Conexao(caminho)
    c.enviar({"pedir": "ola"})
    c.ler(2)
    n = srv.n_clientes
    try:
        c.crus(b"x" * (protocolo.MAX_LINHA + 4096))
    except OSError:
        pass
    checa("quem manda linha gigante é desligado", esperar(lambda: srv.n_clientes == n - 1),
          list(srv.desligados))
    checa("pelo motivo certo", any("linha longa" in m for m in srv.desligados),
          list(srv.desligados))
    c.fechar()

    print("-- o cliente que NÃO lê: a regra que protege o Jarvis --")
    a.fechar()
    b.fechar()
    checa("fechar do lado do cliente é percebido", esperar(lambda: srv.n_clientes == 0))
    lento = Conexao(caminho)
    lento.enviar({"pedir": "ola"})
    esperar(lambda: srv.n_clientes == 1)
    grande = "x" * 2000
    tempos, maior_fila = [], 0
    for i in range(60000):
        ev = ({"ev": "nivel", "v": 0.5} if i % 2 else
              {"ev": "jarvis_disse", "texto": grande, "acao": None, "perguntando": False})
        t0 = time.perf_counter()
        srv.receber(ev)
        tempos.append(time.perf_counter() - t0)
        if i % 250 == 0:
            with srv._trava:
                for cl in srv._clientes.values():
                    maior_fila = max(maior_fila, len(cl.fila))
        if srv.n_clientes == 0:
            break
    checa("o cliente que não lê é desligado", esperar(lambda: srv.n_clientes == 0, 5),
          list(srv.desligados))
    checa("por não ler, e não por outro motivo", any("não lê" in m for m in srv.desligados),
          list(srv.desligados))
    tempos.sort()
    p999 = tempos[int(len(tempos) * 0.999)] * 1000
    maximo = tempos[-1] * 1000
    print(f"          receber(): {len(tempos)} chamadas até ele cair · "
          f"p99,9 {p999:.3f} ms · máximo {maximo:.3f} ms · maior fila {maior_fila}")
    checa("receber() não bloqueia: p99,9 abaixo de 1 ms", p999 < 1.0, f"{p999:.3f} ms")
    checa("nem no pior caso: máximo abaixo de 50 ms", maximo < 50.0, f"{maximo:.3f} ms")
    checa("a fila nunca passou do teto de 256", maior_fila <= 256, maior_fila)
    lento.fechar()

    print("-- quem lê não paga por quem não lê --")
    lento2 = Conexao(caminho)
    lento2.enviar({"pedir": "ola"})
    rapido = Conexao(caminho)
    rapido.enviar({"pedir": "ola"})
    checa("o cliente rápido recebe a sessão antes da enxurrada",
          [e["ev"] for e in rapido.ler(2)] == ["sessao", "estado"])
    esperar(lambda: srv.n_clientes == 2)
    caidos_antes = sum("não lê" in m for m in srv.desligados)
    recebidos, parar = [], threading.Event()

    def ler_rapido():
        while not parar.is_set():
            recebidos.extend(rapido.ler(1000, timeout=0.2))

    leitor = threading.Thread(target=ler_rapido)
    leitor.start()
    enviados = []
    for i in range(3000):
        if i % 2:
            srv.receber({"ev": "nivel", "v": 0.1})
        else:
            texto = f"{i:05d}" + "y" * 2000
            srv.receber({"ev": "jarvis_disse", "texto": texto, "acao": None,
                         "perguntando": False})
            enviados.append(texto)
        time.sleep(0.001)
    esperar(lambda: sum(e.get("ev") == "jarvis_disse" for e in recebidos) >= len(enviados), 8)
    parar.set()
    leitor.join()
    falas = [e["texto"] for e in recebidos if e.get("ev") == "jarvis_disse"]
    checa("o cliente que lê recebe TODAS as falas, em ordem", falas == enviados,
          f"{len(falas)} de {len(enviados)}")
    checa("e o que não lê caiu de novo",
          esperar(lambda: sum("não lê" in m for m in srv.desligados) > caidos_antes, 3))
    lento2.fechar()

    print("-- kill -9 num cliente de verdade --")
    codigo = (f"import sys; sys.path.insert(0, {str(RAIZ)!r})\n"
              f"from jarvis.ponte.cliente import Cliente\n"
              f"c = Cliente({str(caminho)!r}, 'vitima'); c.conectar()\n"
              f"for _ in c.eventos(): pass\n")
    n0 = srv.n_clientes
    proc = subprocess.Popen([sys.executable, "-c", codigo])
    checa("o processo cliente conecta", esperar(lambda: srv.n_clientes == n0 + 1, 5))
    proc.kill()
    proc.wait()
    erro = None
    try:
        for i in range(300):
            srv.receber({"ev": "estado", "estado": protocolo.ESTADOS[i % 5]})
            time.sleep(0.003)
    except Exception as e:  # noqa: BLE001
        erro = e
    checa("depois do kill -9 o servidor segue emitindo, sem exceção", erro is None, erro)
    checa("e percebe que o cliente morreu", esperar(lambda: srv.n_clientes == n0, 3),
          srv.n_clientes)
    rapido.fechar()

    print("-- a classe Cliente, que a interface vai usar --")
    cli = Cliente(caminho, quem="interface")
    cli.conectar()
    cli._sock.settimeout(3)
    primeiro = next(cli.eventos())
    checa("Cliente.conectar manda ola e recebe a sessão", primeiro.get("ev") == "sessao", primeiro)
    cli.enviar_texto("que horas são?")
    checa("Cliente.enviar_texto chega na fila do servidor",
          esperar_texto(srv) == "que horas são?")
    cli.fechar()
    srv.encerrar()

    print("-- socket que sobrou de um Jarvis morto --")
    velho = base / "velho.sock"
    morto = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    morto.bind(str(velho))
    morto.close()  # o arquivo fica e ninguém escuta: é o que sobra de um kill -9
    srv2 = Servidor(velho, fila_max=256, sessao=SESSAO)
    try:
        srv2.iniciar()
        abriu = True
    except Exception as e:  # noqa: BLE001
        abriu = repr(e)
    checa("sobe por cima de um socket morto", abriu is True, abriu)
    x = Conexao(velho)
    x.enviar({"pedir": "ola"})
    r = x.ler(1)
    checa("e responde nele", bool(r) and r[0].get("ev") == "sessao", r)

    print("-- outro Jarvis vivo no mesmo socket --")
    srv3 = Servidor(velho, fila_max=256, sessao=SESSAO)
    try:
        srv3.iniciar()
        resultado = "subiu"
    except ServidorOcupado:
        resultado = "ocupado"
    except Exception as e:  # noqa: BLE001
        resultado = repr(e)
    checa("recusa com ServidorOcupado em vez de roubar", resultado == "ocupado", resultado)
    x.enviar({"pedir": "ola"})
    r = x.ler(1)
    checa("e o Jarvis que já estava lá continua respondendo",
          bool(r) and r[0].get("ev") == "sessao", r)
    srv3.encerrar()
    checa("encerrar o que foi recusado não apaga o socket do que está vivo",
          os.path.lexists(velho))

    print("-- caminho que existe e não é socket --")
    arquivo = base / "arquivo.sock"
    arquivo.write_text("não sou socket")
    srv4 = Servidor(arquivo, fila_max=256, sessao=SESSAO)
    try:
        srv4.iniciar()
        r4 = "subiu"
    except ServidorOcupado:
        r4 = "ocupado"
    except OSError:
        r4 = "oserror"
    checa("recusa com erro", r4 == "oserror", r4)
    checa("e NÃO apaga o arquivo", arquivo.exists() and arquivo.read_text() == "não sou socket")
    srv4.encerrar()

    print("-- encerrar --")
    srv2.encerrar()
    checa("encerrar apaga o socket", not os.path.lexists(velho))
    checa("e o cliente conectado recebe fim de conexão", x.fim_de_conexao(3))
    x.fechar()

    print("-- encerrar não apaga o socket de OUTRO Jarvis --")
    d = base / "d.sock"
    srv_a = Servidor(d, fila_max=256, sessao=SESSAO)
    srv_a.iniciar()
    os.unlink(d)
    srv_b = Servidor(d, fila_max=256, sessao=SESSAO)
    srv_b.iniciar()
    srv_a.encerrar()
    checa("o socket do segundo sobrevive ao encerrar do primeiro", os.path.lexists(d))
    z = Conexao(d)
    z.enviar({"pedir": "ola"})
    r = z.ler(1)
    checa("e o segundo continua respondendo", bool(r) and r[0].get("ev") == "sessao", r)
    z.fechar()
    srv_b.encerrar()


def rodar_historico(base: Path) -> None:
    """A conversa que já existia, e a regra da apresentação.

    Servidor próprio: o anel do outro já teria falas das seções anteriores, e o
    teste ficaria contando o que não interessa.
    """
    caminho = base / "h.sock"
    srv = Servidor(caminho, fila_max=256, sessao=SESSAO)
    srv.iniciar()

    print("-- quem não se apresentou não recebe nada --")
    calado = Conexao(caminho)
    esperar(lambda: srv.n_clientes == 1)
    srv.receber({"ev": "estado", "estado": "ouvindo"})
    srv.receber({"ev": "voce_disse", "texto": "antes de tudo", "origem": "voz"})
    checa("sem ola, nenhum evento chega", calado.ler(1, timeout=0.4) == [],
          "recebeu evento sem se apresentar")
    calado.enviar({"pedir": "ola"})
    checa("depois do ola, a sessão e o estado chegam",
          [e["ev"] for e in calado.ler(2)] == ["sessao", "estado"])
    calado.fechar()

    print("-- o histórico pedido junto do ola --")
    # Estas falas acontecem com NINGUÉM conectado: é para isso que o anel existe.
    esperar(lambda: srv.n_clientes == 0)
    srv.receber({"ev": "jarvis_disse", "texto": "Abri o Loft.", "acao": "abrir:loft",
                 "perguntando": False})
    srv.receber({"ev": "voce_disse", "texto": "e agora?", "origem": "texto"})

    a = Conexao(caminho)
    a.enviar({"pedir": "ola", "quem": "interface", "historico": 10})
    ev = a.ler(3)
    checa("vem depois da sessão e do estado",
          [e["ev"] for e in ev] == ["sessao", "estado", "historico"], [e["ev"] for e in ev])
    falas = ev[2]["falas"] if len(ev) == 3 else []
    checa("com as três falas da sessão, na ordem",
          [f["texto"] for f in falas] == ["antes de tudo", "Abri o Loft.", "e agora?"],
          falas)
    checa("a sua fala leva a origem", falas and falas[0].get("origem") == "voz", falas[:1])
    checa("a dele leva ação e pergunta pendente",
          falas[1].get("acao") == "abrir:loft" and falas[1].get("perguntando") is False,
          falas[1:2])
    checa("todas carimbadas com o relógio do assistente",
          all(isinstance(f.get("quando"), (int, float)) for f in falas), falas)

    print("-- pedir mais do que existe --")
    b = Conexao(caminho)
    b.enviar({"pedir": "ola", "historico": 500})
    ev = b.ler(3)
    checa("devolve o que TEM, sem prometer o número pedido",
          len(ev) == 3 and len(ev[2]["falas"]) == 3, ev[-1:])

    print("-- não pedir --")
    c = Conexao(caminho)
    c.enviar({"pedir": "ola"})
    ev = c.ler(3, timeout=0.6)
    checa("sem 'historico' no ola, nenhum histórico vem",
          [e["ev"] for e in ev] == ["sessao", "estado"], [e["ev"] for e in ev])
    c.crus(b'{"pedir":"ola","historico":"muitas"}\n')
    r = c.ler(1)
    checa("'historico' que não é inteiro vira erro",
          len(r) == 1 and r[0].get("ev") == "erro", r)

    print("-- o teto do anel --")
    for i in range(protocolo.MAX_HISTORICO + 40):
        srv.receber({"ev": "voce_disse", "texto": f"fala {i}", "origem": "voz"})
    d = Conexao(caminho)
    d.enviar({"pedir": "ola", "historico": protocolo.MAX_HISTORICO})
    ev = d.ler(3, timeout=5)
    guardadas = ev[2]["falas"] if len(ev) == 3 else []
    checa(f"guarda no máximo {protocolo.MAX_HISTORICO} falas",
          len(guardadas) == protocolo.MAX_HISTORICO, len(guardadas))
    checa("e as que ficam são as ÚLTIMAS",
          bool(guardadas) and guardadas[-1]["texto"] == f"fala {protocolo.MAX_HISTORICO + 39}",
          guardadas[-1:] if guardadas else [])

    for x in (a, b, c, d):
        x.fechar()
    srv.encerrar()


# ---------------------------------------------------------------------------
# a segunda parte: processos de verdade
# ---------------------------------------------------------------------------


class Processo:
    """Um processo com a saída lida numa thread, para esperar por um texto."""

    def __init__(self, args):
        self.p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  stdin=subprocess.PIPE, text=True, cwd=RAIZ)
        self.linhas: list[str] = []
        threading.Thread(target=self._ler, daemon=True).start()

    def _ler(self):
        for linha in self.p.stdout:
            self.linhas.append(linha.rstrip("\n"))

    def esperar(self, trecho, timeout=6.0, desde=0):
        fim = time.monotonic() + timeout
        while time.monotonic() < fim:
            for i, linha in enumerate(self.linhas[desde:], start=desde):
                if trecho in linha:
                    return i + 1
            time.sleep(0.02)
        return 0

    def escrever(self, texto):
        self.p.stdin.write(texto + "\n")
        self.p.stdin.flush()

    def matar(self):
        if self.p.poll() is None:
            self.p.send_signal(signal.SIGKILL)
            self.p.wait()


ASSISTENTE_FALSO = r'''
import sys, time
sys.path.insert(0, {raiz!r})
from jarvis.ponte.servidor import Servidor
srv = Servidor({caminho!r}, fila_max=256, sessao={{"v": 1, "nome": "Jarvis", "log": {rotulo!r}}})
srv.iniciar()
print("PRONTO", flush=True)
estados = ["dormindo", "ouvindo"]
i = 0
while True:
    srv.receber({{"ev": "estado", "estado": estados[i % 2]}})
    i += 1
    texto = srv.proximo_texto()
    if texto is not None:
        print("PEDIDO", texto, flush=True)
    time.sleep(0.2)
'''


def rodar_processos(base: Path) -> None:
    caminho = str(base / "p.sock")
    py = sys.executable
    processos = []
    try:
        # O Léo achou este caso testando a passada 2 à mão, e ele não estava na
        # lista: a interface vai ser aberta sem ninguém se importar se o Jarvis
        # já está rodando. É propriedade, não acidente — por isso vira teste.
        print("-- o cliente aberto ANTES de o assistente existir --")
        c = Processo([py, "-u", "-m", "jarvis.ponte.cliente", "--socket", caminho])
        processos.append(c)
        espera = c.esperar("desconectado — esperando o Jarvis")
        checa("sobe desconectado e fica esperando", espera > 0, c.linhas)
        checa("sem socket nenhum no caminho ainda", not os.path.lexists(caminho))
        a = Processo([py, "-u", "-c", ASSISTENTE_FALSO.format(
            raiz=str(RAIZ), caminho=caminho, rotulo="primeiro")])
        processos.append(a)
        checa("o assistente sobe depois", a.esperar("PRONTO") > 0, a.linhas)
        n = c.esperar("  conectado", desde=espera)
        checa("e o cliente conecta sozinho, sem ser reaberto", n > 0, c.linhas)
        checa("recebendo a sessão do assistente", c.esperar("primeiro", desde=n) > 0,
              c.linhas[n:])

        print("-- o assistente morre com kill -9 --")
        a.matar()
        caiu = c.esperar("a conexão caiu", desde=n)
        checa("o cliente percebe que caiu", caiu > 0, c.linhas[n:])
        espera2 = c.esperar("desconectado — esperando o Jarvis", desde=caiu)
        checa("e diz que está esperando", espera2 > 0, c.linhas[caiu:])
        checa("o socket morto ficou para trás, como num travamento de verdade",
              os.path.lexists(caminho))
        time.sleep(2.5)
        checa("avisa UMA vez, e não a cada tentativa",
              sum("desconectado" in l for l in c.linhas[caiu:]) == 1, c.linhas[caiu:])

        print("-- outro assistente sobe no mesmo lugar --")
        b = Processo([py, "-u", "-c", ASSISTENTE_FALSO.format(
            raiz=str(RAIZ), caminho=caminho, rotulo="segundo")])
        processos.append(b)
        checa("o segundo sobe por cima do socket morto", b.esperar("PRONTO") > 0, b.linhas)
        volta = c.esperar("  conectado", desde=espera2)
        checa("o cliente reconecta sozinho", volta > 0, c.linhas[espera2:])
        checa("e recebe a sessão do SEGUNDO", c.esperar("segundo", desde=volta) > 0,
              c.linhas[volta:])
        c.escrever("abre o loft")
        checa("e o texto digitado chega no assistente novo",
              b.esperar("PEDIDO abre o loft") > 0, b.linhas)
    finally:
        for p in processos:
            p.matar()


def rodar_janela(base: Path) -> None:
    """Os pedidos da janela grande (v3): conversas, cérebro e troca de conversa."""
    caminho = base / "j.sock"
    srv = Servidor(caminho, fila_max=256, sessao=SESSAO)
    srv.provedor_conversas = lambda: [{"id": "a1b2c3d4", "titulo": "Teste", "quando": 1.0,
                                       "criada": 1.0, "origem": "voz"}]
    srv.provedor_conversa = lambda sessao: [{"quem": "voce", "texto": "oi " + sessao}]
    feitos = []
    srv.provedor_renomear = lambda sessao, titulo: feitos.append(("renomear", sessao, titulo))
    srv.provedor_apagar = lambda sessao: feitos.append(("apagar", sessao))
    srv.iniciar()
    print("-- janela: conversas e cérebro --")
    srv.receber({"ev": "cerebro", "modelo": "auto", "esforco": "medium", "persona": "jarvis"})
    srv.receber({"ev": "uso", "cinco_horas": {"uso": 0.5, "volta_em": 1}, "semana": {"uso": 0.7, "volta_em": 2}})
    srv.receber({"ev": "conversa_atual", "id": "feedbeef-1", "falas": [
        {"quem": "voce", "texto": "antiga", "origem": "voz"},
        {"quem": "atividade", "texto": "Bash"},
        {"quem": "jarvis", "texto": "resposta", "acao": None, "perguntando": False}]})
    janela = Conexao(caminho)
    janela.enviar({"pedir": "ola", "historico": 10})
    evs = janela.ler(5)
    checa("o ola traz o cérebro, o uso e o id da conversa",
          [e["ev"] for e in evs] == ["sessao", "cerebro", "uso", "conversa_atual", "historico"],
          str([e["ev"] for e in evs]))
    checa("o histórico é o da conversa retomada, sem a atividade",
          [f["texto"] for f in evs[-1].get("falas", [])] == ["antiga", "resposta"])
    celular = Conexao(caminho)
    celular.enviar({"pedir": "ola", "voz": True})
    evs_cel = [e["ev"] for e in celular.ler(4, timeout=0.6)]
    checa("o celular não recebe a conversa inteira nem o uso",
          "conversa_atual" not in evs_cel and "uso" not in evs_cel, str(evs_cel))
    janela.enviar({"pedir": "conversas"})
    r = janela.ler(1)
    checa("conversas: a lista volta só para quem pediu",
          r and r[0]["ev"] == "conversas" and r[0]["lista"][0]["titulo"] == "Teste")
    janela.enviar({"pedir": "abrir", "id": "a1b2c3d4"})
    r = janela.ler(1)
    checa("abrir: as falas da conversa", r and r[0].get("falas") == [{"quem": "voce", "texto": "oi a1b2c3d4"}])
    janela.enviar({"pedir": "abrir", "id": "../etc"})
    r = janela.ler(1)
    checa("abrir com id torto: erro", r and r[0]["ev"] == "erro")
    janela.enviar({"pedir": "nova"})
    janela.enviar({"pedir": "continuar", "id": "a1b2c3d4"})
    janela.enviar({"pedir": "cerebro", "esforco": "high"})
    janela.enviar({"pedir": "parar"})
    pedidos = []
    esperar(lambda: pedidos.append(srv.proximo_pedido()) or len([x for x in pedidos if x]) >= 4)
    pedidos = [x for x in pedidos if x]
    checa("nova, continuar, cerebro e parar vão para a fila, em ordem",
          [(x.tipo, x.valor) for x in pedidos] == [("nova", ""), ("continuar", "a1b2c3d4"),
                                                   ("cerebro", '{"esforco": "high"}'), ("parar", "")],
          str([(x.tipo, x.valor) for x in pedidos]))
    janela.enviar({"pedir": "renomear", "id": "a1b2c3d4", "titulo": "  Meu nome  "})
    r = janela.ler(1)
    checa("renomear: chama o provedor e devolve a lista", r and r[0]["ev"] == "conversas"
          and feitos[-1] == ("renomear", "a1b2c3d4", "Meu nome"))
    janela.enviar({"pedir": "apagar", "id": "feedbeef-1"})
    r = janela.ler(1)
    checa("apagar a conversa de agora: erro, e nada foi apagado",
          r and r[0]["ev"] == "erro" and not any(f[0] == "apagar" for f in feitos))
    janela.enviar({"pedir": "apagar", "id": "a1b2c3d4"})
    r = janela.ler(1)
    checa("apagar outra: chama o provedor", r and r[0]["ev"] == "conversas"
          and feitos[-1] == ("apagar", "a1b2c3d4"))
    srv.avisar(pedidos[0].cliente, "espera")
    r = janela.ler(1)
    checa("avisar: o erro chega só para quem pediu", r and r[0] == {"ev": "erro", "motivo": "espera"})
    checa("e o celular não vê", celular.ler(1, timeout=0.4) == [])
    srv.receber({"ev": "conversa_atual", "id": "novinha", "falas": []})
    janela.ler(1)
    nova = Conexao(caminho)
    nova.enviar({"pedir": "ola", "historico": 10})
    evs = nova.ler(4, timeout=1.0)
    checa("conversa nova: histórico vazio", any(e["ev"] == "historico" and e["falas"] == [] for e in evs)
          or not any(e["ev"] == "historico" for e in evs))
    for c in (janela, celular, nova):
        c.fechar()
    srv.encerrar()


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="jarvis-ponte-",
                                 dir=os.environ.get("XDG_RUNTIME_DIR") or None))
    try:
        rodar(base)
        rodar_historico(base)
        rodar_janela(base)
        rodar_processos(base)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print(f"\n  {ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
