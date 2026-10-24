"""10 ms PCM frames; adaptive floor, onset, spectrum and pulse duration gates."""
import numpy as np


SAMPLE_RATE = 16000
FRAME_SAMPLES = 160
FRAME_BYTES = FRAME_SAMPLES * 2


class Detector:
    def __init__(self, sensitivity=50):
        self.sensitivity = sensitivity / 100
        self.noise = 0.002
        self.level = 0.0
        self.peak = 0.0
        self.previous = 0.002
        self.frames = 0
        self.candidate = None
        self.blocked_until = 0
        self.window = np.hanning(FRAME_SAMPLES)
        self.high_bins = np.fft.rfftfreq(FRAME_SAMPLES, 1 / SAMPLE_RATE) >= 1800

    def process(self, pcm, now):
        if len(pcm) != FRAME_BYTES:
            raise ValueError("Expected one 10 ms mono s16le frame")
        x = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 32768
        x -= x.mean()
        rms = float(np.sqrt(np.mean(x * x)))
        self.level = rms
        self.peak = float(np.max(np.abs(x)))
        self.frames += 1
        threshold = max(0.008 + 0.025 * (1 - self.sensitivity),
                        self.noise * (3 + 5 * (1 - self.sensitivity)))
        detected = False
        if self.candidate is not None:
            start, peak, high_ratio, flatness = self.candidate
            duration = now - start
            if rms < max(threshold * 0.65, peak * 0.22):
                detected = 0.009 <= duration <= 0.09 and high_ratio > 0.28 and flatness > 0.12
                self.candidate = None
                self.blocked_until = now + 0.18
            elif duration > 0.09:
                self.candidate = None
                self.blocked_until = now + 0.18
        elif (self.frames > 50 and now >= self.blocked_until and rms > threshold
              and rms > max(self.previous, self.noise) * (1.8 + 1.5 * (1 - self.sensitivity))):
            power = np.abs(np.fft.rfft(x * self.window)) ** 2 + 1e-12
            high_ratio = float(power[self.high_bins].sum() / power.sum())
            flatness = float(np.exp(np.mean(np.log(power[1:]))) / np.mean(power[1:]))
            self.candidate = (now, rms, high_ratio, flatness)
        # Cap sudden impulses so they do not raise the noise floor excessively.
        if self.candidate is None:
            alpha = 0.04 if self.frames <= 50 else 0.008
            target = min(rms, self.noise * 2) if self.frames > 50 else rms
            self.noise = max(0.0003, self.noise + alpha * (target - self.noise))
        self.previous = max(rms, 0.0003)
        return detected
