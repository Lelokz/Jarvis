"""O organizador de tudo (08/11/2026; nasceu em ~/Projetos/Organizador em 19/10).

Chegou coisa nova (Downloads, prints do Flameshot, gravação do OBS) ou o Léo
pediu "organiza isso": um Claude à parte ANALISA O CONTEÚDO (abre a imagem,
tira quadros do vídeo, lê o PDF, lista o zip), escreve um relatório para si e
decide a pasta e o nome pelo que a coisa É. Move direto e avisa; pasta nova,
ele conta. Sem certeza, pergunta ao Léo, e a resposta vira linha do mapa.

Nunca apaga: só move, e tudo fica no diário (dá para desfazer).

    python -m jarvis.organizador organizar <caminho>   organiza um item agora
    python -m jarvis.organizador mover <item> <pasta> <nome>   move com a resposta do Léo
    python -m jarvis.organizador pendentes             o que espera resposta
    python -m jarvis.organizador lista                 as últimas 20 coisas movidas
    python -m jarvis.organizador desfazer ultimo|hoje  devolve para onde estava

As regras gerais: regras.md (aqui). O mapa do Léo: organizador-mapa.md na casa
do Jarvis (~/.local/share/jarvis/casa).
"""
