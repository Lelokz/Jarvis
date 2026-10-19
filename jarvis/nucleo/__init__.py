"""As mãos do Jarvis: o pouco de código que mexe direto no PC.

Até out/2026 isto era o núcleo que decidia tudo (roteador + 11 ferramentas).
O cérebro agora é o Claude Code inteiro (`jarvis/agente/`), e daqui ficou só
o que o corpo usa sem perguntar a ele: mídia e volume (os reflexos de 0 s),
o WhatsApp (ponte, avisos, envio), o relógio falado e o `normalizar` do texto.

A regra continua, verificada pelo `verificar_linha.py`:

    nenhum módulo de jarvis/nucleo/ importa sounddevice, microfone, vad, stt,
    tts ou wakeword.
"""
