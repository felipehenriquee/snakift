"""Inicia o jogo com o robô (build "com robô"): python main_robo.py

O jogo é o mesmo do main.py, mas o robô joga todas as partidas, que contam de verdade (ranque, perfil e
recordes). Menu, configurações, skins e a live funcionam normalmente; o robô só começa ao apertar Jogar.
"""
from cobra import config

config.MODO_ROBO = True

if __name__ == '__main__':
    from cobra.app import main
    main()
