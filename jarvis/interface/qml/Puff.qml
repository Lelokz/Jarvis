import QtQuick

// O "puff" da troca de tela (11/11/2026, pedido do Léo, como no app do
// Claude): a tela nova aparece rapidinho, sem teleportar. Um sopro de
// transparência e um quase nada de zoom.
ParallelAnimation {
    property Item alvo
    NumberAnimation { target: alvo; property: "opacity"; from: 0; to: 1; duration: 200; easing.type: Easing.OutCubic }
    NumberAnimation { target: alvo; property: "scale"; from: 0.985; to: 1; duration: 260; easing.type: Easing.OutCubic }
}
