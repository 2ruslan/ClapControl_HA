import unittest
import numpy as np
from clap_control.detector import Detector, FRAME_SAMPLES


def pcm(samples):
    return (np.clip(samples, -0.999, 0.999) * 32767).astype('<i2').tobytes()


def signal(claps=(), seconds=3, background=0.001):
    rng = np.random.default_rng(42)
    x = rng.normal(0, background, int(seconds * 16000))
    for start, amplitude in claps:
        count = 640
        burst = rng.normal(0, amplitude, count) * np.exp(-np.arange(count) / 150)
        offset = int(start * 16000)
        x[offset:offset + count] += burst
    return x


def run(x, sensitivity=50):
    d = Detector(sensitivity)
    hits = []
    for offset in range(0, len(x) - FRAME_SAMPLES + 1, FRAME_SAMPLES):
        if d.process(pcm(x[offset:offset + FRAME_SAMPLES]), offset / 16000):
            hits.append(offset / 16000)
    return hits, d


class DetectorTests(unittest.TestCase):
    def test_single_impulse(self):
        self.assertEqual(len(run(signal([(1, .3)]))[0]), 1)

    def test_echo_not_double_counted(self):
        self.assertEqual(len(run(signal([(1, .3), (1.08, .18), (1.14, .12)]))[0]), 1)

    def test_separate_claps(self):
        self.assertEqual(len(run(signal([(1, .3), (1.5, .3), (2, .3)]))[0]), 3)

    def test_silence_and_noise(self):
        for level in (0, .001, .03, .1):
            self.assertEqual(run(signal(background=level))[0], [])

    def test_low_frequency_knock(self):
        x = signal()
        t = np.arange(1200) / 16000
        x[16000:17200] += .5 * np.sin(2*np.pi*180*t) * np.exp(-t*55)
        self.assertEqual(run(x)[0], [])

    def test_sustained_noise_burst(self):
        x = signal()
        x[16000:24000] += np.random.default_rng(4).normal(0,.15,8000)
        self.assertEqual(run(x)[0], [])

    def test_tonal_speech_surrogate(self):
        t = np.arange(48000)/16000
        x = signal() + .2*(np.sin(2*np.pi*200*t)+.3*np.sin(2*np.pi*600*t))*np.maximum(0,np.sin(2*np.pi*3*t))
        self.assertEqual(run(x)[0], [])

    def test_noise_floor_adapts(self):
        _, d = run(signal(background=.02,seconds=8))
        self.assertGreater(d.noise, .015)

    def test_frame_contract(self):
        with self.assertRaises(ValueError):
            Detector().process(b'bad', 1)
