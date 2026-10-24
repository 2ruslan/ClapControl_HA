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
        self.audio_time = 0.0
        self.threshold = 0.0
        self.last_analysis = None
        self.analysis_changed = False
        self.candidate = None
        self.blocked_until = 0
        self.window = np.hanning(FRAME_SAMPLES)
        self.high_bins = np.fft.rfftfreq(FRAME_SAMPLES, 1 / SAMPLE_RATE) >= 1800

    def process(self, pcm, now):
        self.analysis_changed = False
        if len(pcm) != FRAME_BYTES:
            raise ValueError("Expected one 10 ms mono s16le frame")
        x = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 32768
        x -= x.mean()
        rms = float(np.sqrt(np.mean(x * x)))
        self.level = rms
        self.peak = float(np.max(np.abs(x)))
        self.frames += 1
        # PCM duration is independent of pipe buffering and process scheduling.
        # Keep the arrival argument for callers, but never use it for DSP timing.
        self.audio_time = (self.frames - 1) * FRAME_SAMPLES / SAMPLE_RATE
        now = self.audio_time
        threshold = max(0.008 + 0.025 * (1 - self.sensitivity),
                        self.noise * (3 + 5 * (1 - self.sensitivity)))
        self.threshold = threshold
        detected = False
        # At high sensitivity, allow room reverberation and a microphone with
        # reduced treble. Keep spectrum and duration gates at every setting.
        high_min = 0.44 - 0.32 * self.sensitivity
        flat_min = 0.18 - 0.12 * self.sensitivity
        max_duration = 0.09 + 0.18 * max(0, self.sensitivity - 0.5)
        if self.candidate is not None:
            start, peak, high_ratio, flatness = self.candidate
            duration = now - start
            # A clap can start partway through a frame. Measure the strongest
            # attack frame, rather than freezing the weak first frame forever.
            if duration <= 0.031 and rms > peak:
                peak = rms
                high_ratio, flatness = self.spectrum(x)
                self.candidate = (start, peak, high_ratio, flatness)
            if rms < max(threshold * 0.65, peak * 0.22):
                reason = ("duration" if not 0.009 <= duration <= max_duration else
                          "spectrum" if high_ratio <= high_min else
                          "tonal" if flatness <= flat_min else "accepted")
                detected = reason == "accepted"
                self.report(reason, duration, peak, high_ratio, flatness)
                self.candidate = None
                self.blocked_until = now + 0.18
            elif duration > max_duration:
                self.report("duration", duration, peak, high_ratio, flatness)
                self.candidate = None
                self.blocked_until = now + 0.18
        elif (self.frames > 50 and now >= self.blocked_until and rms > threshold
              and rms > max(self.previous, self.noise) * (1.8 + 1.5 * (1 - self.sensitivity))):
            high_ratio, flatness = self.spectrum(x)
            self.candidate = (now, rms, high_ratio, flatness)
        elif (self.frames > 50 and now >= self.blocked_until and rms > threshold
              and (self.last_analysis is None or now - self.last_analysis["audio_time"] >= 1)):
            self.report("onset", 0, rms, None, None)
        # Cap sudden impulses so they do not raise the noise floor excessively.
        if self.candidate is None:
            alpha = 0.04 if self.frames <= 50 else 0.008
            target = min(rms, self.noise * 2) if self.frames > 50 else rms
            self.noise = max(0.0003, self.noise + alpha * (target - self.noise))
        self.previous = max(rms, 0.0003)
        return detected

    def spectrum(self, x):
        power = np.abs(np.fft.rfft(x * self.window)) ** 2 + 1e-12
        return (float(power[self.high_bins].sum() / power.sum()),
                float(np.exp(np.mean(np.log(power[1:]))) / np.mean(power[1:])))

    def report(self, reason, duration, rms, high_ratio, flatness):
        self.last_analysis = dict(reason=reason, duration_ms=round(duration * 1000),
                                  rms=round(rms, 5), threshold=round(self.threshold, 5),
                                  high_ratio=round(high_ratio, 3) if high_ratio is not None else None,
                                  flatness=round(flatness, 3) if flatness is not None else None,
                                  audio_time=self.audio_time)
        self.analysis_changed = True
