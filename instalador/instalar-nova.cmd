@echo off
rem instalar-nova.cmd - o que o convidado baixa pelo site no Windows (o irmao do
rem instalar-nova.sh). Pequeno de proposito: baixa o uv (Astral, oficial) e o codigo
rem da NOVA (GitHub), e abre a janela do instalador. Nada de administrador, nada no
rem sistema. Precisa do Windows 10 (1809) ou mais novo, que ja traz o curl e o tar.
rem
rem Este e o MODELO que fica no git (publico): VOZES_DRIVE vazio. A copia que vai
rem no convite tem o endereco do pacote de vozes preenchido e nunca entra no git.
rem So ASCII aqui dentro: o cmd do Windows 10 le acento errado.
setlocal

set "VOZES_DRIVE="
set "CODIGO=https://github.com/Lelokz/Jarvis/archive/refs/heads/main.tar.gz"
set "PASTA=%LOCALAPPDATA%\nova-instalador"
set "UV=%PASTA%\uv\uv.exe"

echo Preparando o instalador da NOVA. Na primeira vez demora um pouco...
if not exist "%PASTA%" mkdir "%PASTA%"

if exist "%UV%" goto temuv
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:UV_INSTALL_DIR = $env:PASTA + '\uv'; $env:UV_NO_MODIFY_PATH = '1'; irm https://astral.sh/uv/install.ps1 | iex" >nul || goto erro
:temuv

if exist "%PASTA%\codigo" rmdir /s /q "%PASTA%\codigo"
mkdir "%PASTA%\codigo"
curl.exe -LsSf "%CODIGO%" -o "%PASTA%\codigo.tar.gz" || goto erro
tar -xzf "%PASTA%\codigo.tar.gz" -C "%PASTA%\codigo" --strip-components=1 || goto erro
del "%PASTA%\codigo.tar.gz"

rem O Python e a biblioteca da janela (PySide6), so para o instalador.
set "UV_CACHE_DIR=%PASTA%\uv-cache"
set "UV_PYTHON_INSTALL_DIR=%PASTA%\python"
"%UV%" venv --python 3.12 --allow-existing -q "%PASTA%\janela" || goto erro
"%UV%" pip install -q --python "%PASTA%\janela\Scripts\python.exe" pyside6-essentials==6.11.2 numpy==2.5.2 || goto erro

rem A janela abre sozinha (pythonw: sem terminal) e este terminal fecha.
set "NOVA_VOZES_DRIVE=%VOZES_DRIVE%"
set "NOVA_UV=%UV%"
start "" /d "%PASTA%\codigo\instalador" "%PASTA%\janela\Scripts\pythonw.exe" -m nova_instalador
exit /b 0

:erro
echo.
echo Algo deu errado ao preparar o instalador. Confere a internet e abre de novo.
pause
exit /b 1
