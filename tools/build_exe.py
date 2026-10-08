"""Gera os executáveis do jogo com o PyInstaller (cada um é um arquivo só, com os assets dentro).

    python tools/build_exe.py            # os dois
    python tools/build_exe.py normal     # só o jogo normal
    python tools/build_exe.py robo       # só a versão com robô

No Windows saem dist/Snakift.exe e dist/Snakift Robo.exe (com os ícones de assets/icones, que aparecem no
arquivo, nos atalhos e na barra de tarefas); no Linux, os mesmos nomes sem o .exe. O PyInstaller só gera
executável para o sistema em que roda: para o .exe, rode no Windows (build_windows.bat faz tudo).
Os dados do jogador (recordes, elo, configurações) ficam fora do executável, na pasta de dados do usuário
(no Windows, %APPDATA%\\cobra-presentes), então trocar o .exe por uma versão nova não apaga nada.
"""
import importlib.util
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILDS = {   # nome do executável, script de entrada, ícone
    'normal': ('Snakift', 'main.py', 'snakift'),
    'robo': ('Snakift Robo', 'main_robo.py', 'snakift_robo'),
}
EXCLUDE = ['numpy', 'PIL', 'tkinter', 'tests', 'tools']     # só o gerador de sprites usa


def build(key):
    import PyInstaller.__main__
    name, script, icon = BUILDS[key]
    ico = os.path.join(ROOT, 'assets', 'icones', icon + ('.ico' if sys.platform == 'win32' else '.png'))
    args = [os.path.join(ROOT, script), '--name', name, '--onefile', '--windowed', '--noconfirm', '--clean',
            '--icon', ico,
            '--add-data', f'{os.path.join(ROOT, "assets")}{os.pathsep}assets',
            '--distpath', os.path.join(ROOT, 'dist'),
            '--workpath', os.path.join(ROOT, 'build', key),
            '--specpath', os.path.join(ROOT, 'build', key)]
    for mod in EXCLUDE:
        args += ['--exclude-module', mod]
    if importlib.util.find_spec('TikTokLive'):        # modo live: o pacote tem arquivos e imports dinâmicos
        args += ['--collect-all', 'TikTokLive', '--collect-all', 'TikTokLiveProto']
    else:
        print('aviso: TikTokLive não instalado, o executável não conecta na live (pip install -r requirements-live.txt)')
    PyInstaller.__main__.run(args)


def main():
    keys = sys.argv[1:] or list(BUILDS)
    for key in keys:
        if key not in BUILDS:
            sys.exit(f'build desconhecido: {key} (use {", ".join(BUILDS)})')
    for key in keys:
        build(key)
    shutil.rmtree(os.path.join(ROOT, 'build'), ignore_errors=True)     # arquivos temporários do PyInstaller
    ext = '.exe' if sys.platform == 'win32' else ''
    print('\nPronto:')
    for key in keys:
        print('  ', os.path.join(ROOT, 'dist', BUILDS[key][0] + ext))


if __name__ == '__main__':
    main()
