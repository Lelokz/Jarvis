#!/usr/bin/env bash
# compilar.sh — gera o APK do app do Jarvis (app/build/outputs/apk/debug/).
#
# As ferramentas (JDK, SDK do Android, Gradle e o cache dele) moram no HD,
# não no SSD: são ~3 GB. Ver ESCOPO §4, "O celular".
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
F="/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/Arquivo/Android-Ferramentas"
export JAVA_HOME="$F/jdk" ANDROID_HOME="$F/sdk" GRADLE_USER_HOME="$F/gradle-cache"
echo "sdk.dir=$ANDROID_HOME" > local.properties
exec ./gradlew --console=plain "${@:-assembleDebug}"
