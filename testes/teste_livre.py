import numpy as np

from jarvis import personas, voz
from jarvis.nucleo import memoria_viva


def teste_personas():
    assert "livre" in personas.lista()
    personas.definir("livre")
    assert "Disclaimer" in personas.texto()


def teste_voz():
    pcm = np.sin(np.linspace(0, 3000, 16000)).astype(np.float32) * 0.4
    voz.definir("safada")
    saida = voz.aplicar(pcm, 16000)
    assert saida.dtype == np.float32 and float(np.max(np.abs(saida))) <= 1.0
    voz.definir("normal")


def teste_memoria():
    memoria_viva.gravar("teste", "o carro do vizinho é um gol branco", "teste")
    achados = memoria_viva.buscar("gol branco")
    assert any("gol branco" in a["texto"] for a in achados)