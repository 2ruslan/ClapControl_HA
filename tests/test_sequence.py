import unittest
from clap_control.sequence import Sequence


class SequenceTests(unittest.TestCase):
    def test_one(self):
        self.assertTrue(Sequence(1).clap(1))

    def test_two(self):
        s = Sequence(2)
        self.assertFalse(s.clap(1))
        self.assertTrue(s.clap(1.6))

    def test_timeout(self):
        s = Sequence(2)
        self.assertFalse(s.clap(1))
        self.assertFalse(s.clap(1.81))
        self.assertTrue(s.clap(2.2))

    def test_three(self):
        s = Sequence(3)
        self.assertEqual([s.clap(t) for t in (1, 1.5, 2)], [False, False, True])

    def test_echo(self):
        s = Sequence(2)
        self.assertEqual([s.clap(t) for t in (1, 1.05, 1.1, 1.5)], [False, False, False, True])

    def test_cooldown(self):
        s = Sequence(2)
        self.assertEqual([s.clap(t) for t in (1, 1.4, 2, 2.4, 4.5, 5)],
                         [False, True, False, False, False, True])

    def test_exact_interval(self):
        s = Sequence(2, interval=0.5)
        self.assertFalse(s.clap(1))
        self.assertTrue(s.clap(1.5))
