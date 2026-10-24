from threading import Lock


class Diagnostics:
    def __init__(self):
        self.lock = Lock()
        self.data = dict(audio_status="connecting", detector_status="starting", level=0,
                         noise=0, peak=0, claps=0, sequences=0, activations=0,
                         last_trigger=None, last_scene=None, scene_number=0,
                         error=None, event_error=None, audio_error=None, threshold=0)

    def update(self, **values):
        with self.lock:
            self.data.update(values)

    def increment(self, name):
        with self.lock:
            self.data[name] += 1

    def snapshot(self):
        with self.lock:
            return dict(self.data)
