#!/usr/bin/env bash
# compilar.sh — gera os APKs do Jarvis: o do celular (app/build/outputs/apk/debug/)
# e o do relógio (relogio/build/outputs/apk/debug/).
#
# As ferramentas (JDK, SDK do Android, Gradle e o cache dele) moram no HD,
# não no SSD: são ~3 GB. Ver ESCOPO §4, "O celular".
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
F="/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/Arquivo/Android-Ferramentas"
export JAVA_HOME="$F/jdk" ANDROID_HOME="$F/sdk" GRADLE_USER_HOME="$F/gradle-cache"
echo "sdk.dir=$ANDROID_HOME" > local.properties
# Os modelos do "hey Jarvis" e do VAD são os do PC (baixados, fora do git).
mkdir -p app/src/main/assets
for m in melspectrogram embedding_model hey_jarvis_v0.1 silero_vad; do
  cp -u "../modelos-wakeword/$m.onnx" app/src/main/assets/
done
exec ./gradlew --console=plain "${@:-assembleDebug}"
