import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestGameDependencies(unittest.TestCase):
    def test_game_does_not_need_numpy(self):
        """O jogo só depende do pygame (requirements.txt); numpy é só das tools que geram os sprites.

        pygame.surfarray também exige numpy, então ele não pode aparecer no código do jogo.
        """
        folder = os.path.join(ROOT, 'cobra')
        for name in sorted(os.listdir(folder)):
            if name.endswith('.py'):
                with open(os.path.join(folder, name), encoding='utf-8') as f:
                    src = f.read()
                self.assertIsNone(re.search(r'\bnumpy\b|\bsurfarray\b', src), f'cobra/{name} usa numpy/surfarray')

    def test_requirements_only_list_pygame(self):
        with open(os.path.join(ROOT, 'requirements.txt'), encoding='utf-8') as f:
            reqs = [line.split('>=')[0].strip().lower() for line in f if line.strip() and not line.startswith('#')]
        self.assertEqual(reqs, ['pygame'])


if __name__ == '__main__':
    unittest.main()
