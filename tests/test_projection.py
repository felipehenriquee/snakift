import unittest
from types import SimpleNamespace

from cobra.scenery import make_fence, make_props, outside_distance
from cobra.projection import Projection

N = 11
MAN_34 = SimpleNamespace(axis_gx=(96, 0), axis_gy=(0, 68))


class TestProjection(unittest.TestCase):
    def test_without_perspective_is_the_flat_grid(self):
        p = Projection(MAN_34, N, 0.0)
        x0, y0, s = p.project(0, 0)
        x1, y1, _ = p.project(3, 2)
        self.assertEqual(s, 1.0)
        self.assertEqual((x1 - x0, y1 - y0), (3 * 96, 2 * 68))

    def test_row_scale_matches_formula(self):
        persp = 0.15
        p = Projection(MAN_34, N, persp)
        for gy in range(N):
            self.assertAlmostEqual(p.project(4, gy)[2], 1 - persp * (1 - gy / (N - 1)))

    def test_rows_touch_without_gaps(self):
        """A distância entre linhas vizinhas é a média das alturas (já escaladas) das duas."""
        p = Projection(MAN_34, N, 0.15)
        for gy in range(N - 1):
            _, ya, sa = p.project(0, gy)
            _, yb, sb = p.project(0, gy + 1)
            self.assertAlmostEqual(yb - ya, 68 * (sa + sb) / 2)

    def test_columns_converge_to_the_center(self):
        p = Projection(MAN_34, N, 0.15)
        back_w = p.project(N - 1, 0)[0] - p.project(0, 0)[0]
        front_w = p.project(N - 1, N - 1)[0] - p.project(0, N - 1)[0]
        self.assertAlmostEqual(back_w / front_w, 0.85)


class TestZoom(unittest.TestCase):
    def test_zoom_scales_distances_and_sprites(self):
        p = Projection(MAN_34, N, 0.15)
        x0, y0, s0 = p.project(1, 2)
        x1, y1, s1 = p.project(4, 7)
        p.zoom = 0.5
        a0, b0, z0 = p.project(1, 2)
        a1, b1, z1 = p.project(4, 7)
        self.assertAlmostEqual(z0, s0 * 0.5)
        self.assertAlmostEqual(a1 - a0, (x1 - x0) * 0.5)
        self.assertAlmostEqual(b1 - b0, (y1 - y0) * 0.5)


class TestScenery(unittest.TestCase):
    def test_fence_surrounds_the_board(self):
        for on_edge in (True, False):
            fence = make_fence(N, on_edge)
            self.assertEqual(len(fence), 4 * N + 4)
            for (gx, gy), _ in fence:
                inside = 0 <= gx <= N - 1 and 0 <= gy <= N - 1
                self.assertFalse(inside, (gx, gy))

    def test_fence_corners(self):
        cell = {f.pos: f.piece for f in make_fence(N, on_edge=False)}
        self.assertEqual(cell[(-1, -1)], 'canto_ES')
        self.assertEqual(cell[(N, N)], 'canto_WN')
        edge = {f.pos: f.piece for f in make_fence(N, on_edge=True)}
        self.assertEqual(edge[(-0.5, -0.5)], 'poste')
        self.assertEqual(edge[(3, -0.5)], 'reta_x')
        self.assertEqual(edge[(N - 0.5, 3)], 'reta_y')

    def test_props_only_outside_the_fence(self):
        cells = [(x, y) for x in range(-6, N + 6) for y in range(-6, N + 6)]
        for on_edge in (True, False):
            fence_cells = {f.pos for f in make_fence(N, on_edge)}
            props = make_props(N, cells, on_edge, density=0.5)
            self.assertTrue(props)
            for p in props:
                self.assertGreater(outside_distance(N, p.cell), 1)      # 1 anel livre em volta da cerca
                self.assertNotIn(p.cell, fence_cells)

    def test_props_do_not_depend_on_screen_size(self):
        small = [(x, y) for x in range(-3, N + 3) for y in range(-3, N + 3)]
        big = [(x, y) for x in range(-9, N + 9) for y in range(-9, N + 9)]
        props_big = set(make_props(N, big))
        self.assertTrue(set(make_props(N, small)) <= props_big)

    def test_density_controls_amount(self):
        cells = [(x, y) for x in range(-10, N + 10) for y in range(-10, N + 10)]
        outside = sum(1 for c in cells if outside_distance(N, c) > 0)
        frac = len(make_props(N, cells, density=0.2)) / outside
        self.assertAlmostEqual(frac, 0.2, delta=0.05)


if __name__ == '__main__':
    unittest.main()
