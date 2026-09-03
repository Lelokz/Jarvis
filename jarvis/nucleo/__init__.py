"""O núcleo do Jarvis: texto entra, decisão acontece, texto sai.

Este pacote **não sabe o que é microfone, voz, wake word nem rede** (ESCOPO §4).
Ele recebe uma frase já em texto, decide o que fazer, executa e devolve o que
dizer. Quem transforma isso em som — ou em tela de celular, um dia — é o
cliente.

A regra é simples e vale para tudo que entrar aqui:

    nenhum módulo de jarvis/nucleo/ importa sounddevice, microfone, vad, stt,
    tts ou wakeword.

Ela não é só boa intenção: há uma verificação que varre este pacote e falha se
algum desses imports aparecer. O motivo de traçar a linha antes de precisar
dela é que o Jarvis vai ganhar clientes remotos (celular, talvez relógio), e
função nascida costurada dentro do loop de voz só se separa reescrevendo.
"""
