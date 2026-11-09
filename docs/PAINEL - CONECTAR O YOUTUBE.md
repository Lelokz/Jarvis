# Painel do Canal: conectar o YouTube (uma vez só)

Uns 10 minutos, no PC, com a conta Google **do canal Lelokz**. Você cria um
"projeto" no Google, que é só uma permissão pro teu PC conversar com o teu
canal. É de graça.

## 1. Criar o projeto
1. Abra https://console.cloud.google.com e entre com a conta do canal.
2. No topo, clique em **Selecionar projeto**, depois em **Novo projeto**.
   Nome: `Painel do Canal`. Clique em **Criar** e selecione o projeto.

## 2. Ligar as duas APIs do YouTube
1. Abra https://console.cloud.google.com/apis/library
2. Procure **YouTube Data API v3**, abra e clique em **Ativar**.
3. Volte, procure **YouTube Analytics API** e clique em **Ativar** também.

## 3. A tela de permissão
1. Abra https://console.cloud.google.com/auth/overview e clique em **Começar**.
2. Nome do app: `Painel do Canal`. E-mail: o teu. Público: **Externo**.
   Aceite e clique em **Criar**.
3. No menu da esquerda, abra **Público** e clique em **Publicar app**,
   depois em **Confirmar**.
   (Sem isso a autorização vence a cada 7 dias. Ninguém além de você usa o app.)

## 4. A credencial do PC
1. No menu da esquerda, abra **Clientes** e clique em **Criar cliente**.
2. Tipo: **App para computador**. Nome: `PC do Léo`. Clique em **Criar**.
3. Clique em **Baixar JSON**.
4. Renomeie o arquivo baixado para `cliente.json` e mova ele pra pasta
   `~/.local/share/jarvis/canal/`. Ou cole isto no terminal:

       mkdir -p ~/.local/share/jarvis/canal && mv ~/Downloads/client_secret_*.json ~/.local/share/jarvis/canal/cliente.json

## 5. Autorizar
No terminal:

    cd ~/Projetos/Jarvis && .venv/bin/python -m jarvis.canal conectar

Abre o navegador:
1. Escolha a conta do canal.
2. Vai aparecer **"O Google não verificou este app"**. Isso é normal, porque
   o app é só teu. Clique em **Avançado** e depois em **Acessar Painel do
   Canal (não seguro)**.
3. Marque tudo e clique em **Continuar**.

Quando aparecer "Pronto! O Painel do Canal está ligado", já pode perguntar
pro Jarvis: **"como tá o canal?"**
