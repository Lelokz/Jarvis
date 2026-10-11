#!/bin/bash
# A bandeja de ponta a ponta, sem depender de clique humano.
#
# A janela é identificada pela CLASSE (interface.py.Jarvis), e não pelo título:
# procurar "Jarvis" na lista de janelas casava com o VS Code, que tem o nome do
# projeto no título — os dois primeiros "PASSOU" da primeira versão estavam
# olhando para a janela errada.
#
# E nada de gnome-screenshot aqui dentro: ele trava dentro da cerca e leva o
# teste junto até o prazo estourar. A foto é tirada de fora.
RAIZ=/home/lelokz/Projetos/Jarvis
cd "$RAIZ" || exit 1
SOCK=$XDG_RUNTIME_DIR/jarvis-bandeja.sock
rm -f "$SOCK"
ok=0; falhou=0
checa () { if [ "$2" = "ok" ]; then ok=$((ok+1)); echo "  PASSOU  $1"; else falhou=$((falhou+1)); echo "  FALHOU  $1  ($3)"; fi; }
janelas () { wmctrl -l -x 2>/dev/null | grep -c "interface.py.Jarvis"; }

.venv/bin/python testes/eco_historico.py "$SOCK" > /dev/null 2>&1 &
ECO=$!
sleep 2
.venv/bin/python interface.py --socket "$SOCK" > rascunho/interface-teste.log 2>&1 &
IFACE=$!
sleep 7

[ "$(janelas)" -eq 1 ] && checa "a janela abriu" ok || checa "a janela abriu" nao "$(janelas) janelas com a classe"
grep -q "sem bandeja" rascunho/interface-teste.log \
  && checa "a bandeja subiu" nao "a interface disse 'sem bandeja'" \
  || checa "a bandeja subiu" ok

echo "-- fechando a janela pelo gerenciador de janelas --"
wmctrl -c "Jarvis" -x -F 2>/dev/null || wmctrl -i -c "$(wmctrl -l -x | awk '/interface.py.Jarvis/{print $1}')" 2>/dev/null
sleep 3
kill -0 $IFACE 2>/dev/null && checa "o processo da interface continua vivo" ok || checa "o processo da interface continua vivo" nao "morreu ao fechar"
[ "$(janelas)" -eq 0 ] && checa "a janela sumiu da tela" ok || checa "a janela sumiu da tela" nao "ainda listada"
kill -0 $ECO 2>/dev/null && checa "o assistente não sentiu nada" ok || checa "o assistente não sentiu nada" nao "morreu junto"

echo "-- abrindo a interface de novo --"
saida=$(timeout 20 .venv/bin/python interface.py --socket "$SOCK" 2>&1)
echo "$saida" | grep -q "já estava aberto" \
  && checa "a segunda tentativa não cria outra janela" ok \
  || checa "a segunda tentativa não cria outra janela" nao "${saida:-sem saída}"
sleep 2
[ "$(janelas)" -eq 1 ] && checa "e traz a janela de volta" ok || checa "e traz a janela de volta" nao "$(janelas) janelas"
# `ps -C python` lista só processos cujo executável é o python: shells, o
# `timeout` e o próprio comando de busca ficam de fora. Com `pgrep -f` a conta
# deu 3 — e é a mesma armadilha de casar com a própria linha de comando.
echo "  quem o pgrep -f enxergava:"; pgrep -af "interface.py --socket" | cut -c1-70 | sed "s/^/      /"
n=$(ps -C python -o args= 2>/dev/null | grep -c "interface.py --socket")
[ "$n" -eq 1 ] && checa "só existe um processo de interface" ok || checa "só existe um processo de interface" nao "$n processos Python"

kill $IFACE $ECO 2>/dev/null
sleep 1
echo
echo "  $ok passaram, $falhou falharam"
[ "$falhou" -eq 0 ]
