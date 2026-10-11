"""A interface (Etapa 6): o segundo cliente do núcleo, em processo separado.

Aqui não existe núcleo, nem microfone, nem Whisper. Existe uma janela que
mostra o que a ponte conta e manda texto de volta. Se este processo morrer, o
Jarvis não sente — foi por isso que o Léo escolheu dois processos.
"""
