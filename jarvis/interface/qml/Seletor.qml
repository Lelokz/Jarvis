import QtQuick
import QtQuick.Controls.Basic

// Um seletor da barra de escrever (persona, cérebro, esforço): o botãozinho
// com o que está escolhido e, ao clicar, o menu com as opções e uma linha
// explicando cada uma.
Item {
    id: raiz
    property var tema
    property string rotulo: ""          // o título do menu ("Cérebro")
    property var opcoes: []             // [{valor, nome, descricao, habilitado}]
    property string valor: ""
    property string icone: ""
    property bool iconeCheio: false
    property color corDaBola: "transparent"
    property bool paraCima: true
    property bool alinharDireita: false
    signal escolhido(string valor)

    readonly property var atual: {
        for (var i = 0; i < opcoes.length; i++)
            if (opcoes[i].valor === valor) return opcoes[i];
        return { nome: valor, descricao: "" };
    }

    width: botao.width
    height: 32

    Rectangle {
        id: botao
        width: linha.width + 22
        height: 32
        radius: 9
        color: area.containsMouse ? raiz.tema.superficie2 : raiz.tema.lateral
        border.width: 1
        border.color: menu.opened ? raiz.tema.persona : raiz.tema.traco
        Behavior on color { ColorAnimation { duration: raiz.tema.rapido } }

        Row {
            id: linha
            anchors.centerIn: parent
            spacing: 7
            Rectangle {
                visible: raiz.corDaBola !== Qt.color("transparent")
                anchors.verticalCenter: parent.verticalCenter
                width: 8; height: 8; radius: 4
                color: raiz.corDaBola
            }
            Icone {
                visible: raiz.icone !== ""
                anchors.verticalCenter: parent.verticalCenter
                caminho: raiz.icone
                cheio: raiz.iconeCheio
                cor: raiz.tema.textoMedio
                tamanho: 14
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: raiz.atual.nome
                color: raiz.tema.textoMedio
                font.family: raiz.tema.familia
                font.pixelSize: 13
            }
            Icone {
                anchors.verticalCenter: parent.verticalCenter
                caminho: raiz.tema.icones.seta
                cor: raiz.tema.muitoFraco
                tamanho: 12
                rotation: menu.opened ? 180 : 0
                Behavior on rotation { NumberAnimation { duration: raiz.tema.rapido } }
            }
        }
        MouseArea {
            id: area
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: menu.opened ? menu.close() : menu.open()
        }
    }

    Popup {
        id: menu
        y: raiz.paraCima ? -height - 8 : botao.height + 8
        x: raiz.alinharDireita ? botao.width - width : 0
        width: 300
        padding: 6
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 120 } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 100 } }
        background: Rectangle {
            color: raiz.tema.superficie2
            radius: 14
            border.width: 1
            border.color: raiz.tema.tracoForte
        }
        contentItem: Column {
            spacing: 2
            Text {
                leftPadding: 12; topPadding: 8; bottomPadding: 4
                text: raiz.rotulo.toUpperCase()
                color: raiz.tema.muitoFraco
                font.family: raiz.tema.familia
                font.pixelSize: 11
                font.weight: Font.DemiBold
                font.letterSpacing: 0.8
            }
            Repeater {
                model: raiz.opcoes
                Rectangle {
                    required property var modelData
                    readonly property bool habilitada: modelData.habilitado !== false
                    readonly property bool escolhida: modelData.valor === raiz.valor
                    width: 288
                    height: textos.height + 18
                    radius: 9
                    color: escolhida ? raiz.tema.realce
                         : areaOpcao.containsMouse && habilitada ? raiz.tema.superficie : "transparent"
                    opacity: habilitada ? 1.0 : 0.45
                    Column {
                        id: textos
                        anchors.verticalCenter: parent.verticalCenter
                        x: 12
                        width: parent.width - 48
                        spacing: 2
                        Text {
                            text: modelData.nome
                            color: raiz.tema.texto
                            font.family: raiz.tema.familia
                            font.pixelSize: 14
                            font.weight: Font.Medium
                        }
                        Text {
                            visible: !!modelData.descricao
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: modelData.descricao || ""
                            color: raiz.tema.textoFraco
                            font.family: raiz.tema.familia
                            font.pixelSize: 12
                        }
                    }
                    Icone {
                        visible: escolhida
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        caminho: raiz.tema.icones.certo
                        cor: raiz.tema.persona
                        tamanho: 16
                    }
                    MouseArea {
                        id: areaOpcao
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: habilitada
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            menu.close();
                            if (!escolhida)
                                raiz.escolhido(modelData.valor);
                        }
                    }
                }
            }
        }
    }
}
