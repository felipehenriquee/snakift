@echo off
rem Gera os executaveis do Snakift no Windows: dist\Snakift.exe e dist\Snakift Robo.exe
rem e cria os atalhos (com os icones) na Area de Trabalho. Precisa do Python 3.10+ (python.org).
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python nao encontrado. Instale o Python 3.10 ou mais novo em https://www.python.org/downloads/
    echo e marque "Add python.exe to PATH" na instalacao. Depois rode este arquivo de novo.
    pause
    exit /b 1
)

echo == Preparando o ambiente (so demora na primeira vez) ==
if not exist .venv-win (
    py -3 -m venv .venv-win || goto erro
)
call .venv-win\Scripts\activate.bat || goto erro
python -m pip install --upgrade pip >nul
python -m pip install -r requirements-live.txt pyinstaller || goto erro

echo.
echo == Gerando os executaveis ==
python tools\build_exe.py || goto erro

echo.
echo == Criando os atalhos na Area de Trabalho ==
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $w=New-Object -ComObject WScript.Shell;" ^
  "foreach($n in 'Snakift','Snakift Robo'){ $s=$w.CreateShortcut(\"$d\$n.lnk\"); $s.TargetPath=(Resolve-Path \"dist\$n.exe\").Path;" ^
  "$s.WorkingDirectory=(Resolve-Path 'dist').Path; $s.IconLocation=$s.TargetPath+',0'; $s.Save() }"

echo.
echo Pronto! Os jogos estao na pasta dist e os atalhos na Area de Trabalho.
pause
exit /b 0

:erro
echo.
echo Algo deu errado (veja a mensagem acima).
pause
exit /b 1
