"""Grid -> tela, com perspectiva falsa opcional. Não depende do pygame."""


class Projection:
    """Converte posições do grid em pixels de tela.

    A projeção "plana" vem do manifest (quantos px na tela vale um passo em gx e em gy).
    Com perspectiva > 0, cada ponto é encolhido em direção ao centro da tela por uma escala
    que vai de 1 - perspectiva (linha do fundo) até 1 (linha da frente), e o y acumula as
    alturas já encolhidas, então as bordas do tabuleiro convergem como numa câmera de verdade.
    """

    def __init__(self, man, n, perspective=0.0):
        self.ax, self.ay = man.axis_gx
        self.bx, self.by = man.axis_gy
        self.mid = (n - 1) / 2
        self.perspective = perspective
        corners = [self.flat(x, y) for x in (0, n - 1) for y in (0, n - 1)]
        y_back = min(c[1] for c in corners)
        y_front = max(c[1] for c in corners)
        span = (y_front - y_back) or 1.0
        # escala(yf) = a + k * yf: vale 1 - perspectiva em y_back e 1 em y_front
        self.k = perspective / span
        self.a = 1 - perspective * y_front / span
        self.center = (0.0, 0.0)    # ponto da tela onde fica o centro do tabuleiro
        self.zoom = 1.0             # < 1 afasta a câmera (arenas grandes precisam caber na tela)

    def flat(self, gx, gy):
        """Posição sem perspectiva, em px, relativa ao centro do tabuleiro."""
        dx, dy = gx - self.mid, gy - self.mid
        return dx * self.ax + dy * self.bx, dx * self.ay + dy * self.by

    def scale_at(self, yf):
        return self.a + self.k * yf

    def warp_y(self, yf):
        """Soma das alturas encolhidas do centro do tabuleiro até yf (integral da escala)."""
        return self.a * yf + self.k * yf * yf / 2

    def screen(self, xf, yf):
        """Ponto plano -> (x, y, escala) na tela."""
        s = self.scale_at(yf) * self.zoom
        return self.center[0] + xf * s, self.screen_y(yf), s

    def screen_y(self, yf):
        return self.center[1] + self.warp_y(yf) * self.zoom

    def project(self, gx, gy):
        """Posição no grid (pode ser fracionária) -> (x, y, escala) na tela."""
        return self.screen(*self.flat(gx, gy))
