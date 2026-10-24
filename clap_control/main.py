import json
import logging
import os
from pathlib import Path
import queue
import signal
import threading
import time
from datetime import datetime, timezone

from .audio import Audio
from .detector import Detector
from .diagnostics import Diagnostics
from .scenes import HomeAssistant, SceneCycle, APIError
from .sequence import Sequence
from .settings import Settings, load_settings
from .state import State, atomic_json
from .web import serve

LOG = logging.getLogger("clap_control")


class Application:
    def __init__(self, directory, api):
        self.directory = Path(directory)
        self.settings, self.baseline = load_settings(self.directory)
        self.api = api
        self.state = State(self.directory / "state.json")
        self.cycle = SceneCycle(api, self.state)
        self.diagnostics = Diagnostics()
        self.diagnostics.update(last_scene=self.state.value["last_scene"],
                                last_trigger=self.state.value["last_trigger"],
                                scene_number=self.state.value["index"] + 1)
        self.stop = threading.Event()
        self.restart = threading.Event()
        self.busy = threading.Event()
        self.operation = threading.Lock()
        self.triggers = queue.Queue(maxsize=1)
        self.generation = 0
        self.audio_generation = -1
        self.audio_epoch = 0
        self.last_diagnostic = 0
        self.last_audio_log = 0
        self.last_save = float("-inf")
        self.audio = Audio(self.stop, self.restart, lambda: self.settings.audio_source,
                           self.on_frame, self.on_audio_status)

    def on_audio_status(self, status, error):
        self.diagnostics.update(audio_status=status, audio_error=error)
        if status != "connected":
            self.audio_epoch += 1  # Discard an incomplete series across capture interruptions.
        if error and time.monotonic() - self.last_audio_log > 30:
            LOG.warning("Audio unavailable: %s; retrying", error)
            self.last_audio_log = time.monotonic()

    def on_frame(self, frame, now):
        settings = self.settings
        generation = (self.generation, self.audio_epoch)
        if generation != self.audio_generation:
            self.detector = Detector(settings.sensitivity)
            self.sequence = Sequence(settings.clap_count, settings.max_interval_ms / 1000,
                                     settings.cooldown_seconds)
            self.audio_generation = generation
        detected = self.detector.process(frame, now)
        if now - self.last_diagnostic >= 0.25:
            self.diagnostics.update(level=round(self.detector.level, 5),
                                    noise=round(self.detector.noise, 5), peak=round(self.detector.peak, 5))
            self.last_diagnostic = now
        if not settings.enabled or self.busy.is_set():
            self.sequence.pending = 0
            return
        if detected:
            self.diagnostics.increment("claps")
            LOG.debug("Clap: level=%.4f noise=%.4f", self.detector.level, self.detector.noise)
            if self.sequence.clap(now):
                self.diagnostics.increment("sequences")
                timestamp = datetime.now(timezone.utc).isoformat()
                self.diagnostics.update(last_trigger=timestamp)
                if not settings.test_mode:
                    try:
                        self.triggers.put_nowait((self.generation, now))
                    except queue.Full:
                        pass

    def activate(self, generation, detected_at):
        with self.operation:
            if generation != self.generation or time.monotonic() - detected_at > 1:
                return
            self.busy.set()
            try:
                result = self.cycle.trigger(self.settings)
                if result:
                    self.diagnostics.increment("activations")
                    self.diagnostics.update(last_scene=result["scene"],
                                            scene_number=result["scene_number"], error=None,
                                            event_error=None)
                    LOG.info("Activated %s (%d/%d)", result["scene"], result["scene_number"],
                             result["total_scenes"])
                    if self.settings.emit_event:
                        try:
                            self.api.request("POST", "/events/clap_control_triggered", result)
                        except APIError as exc:
                            self.diagnostics.update(event_error=str(exc))
                            LOG.warning("Scene activated, event failed: %s", exc)
            except (APIError, OSError) as exc:
                self.diagnostics.update(error=str(exc))
                LOG.error("Activation failed: %s", exc)
            finally:
                self.busy.clear()

    def worker(self):
        while not self.stop.is_set():
            try:
                generation, detected_at = self.triggers.get(timeout=0.25)
            except queue.Empty:
                continue
            self.activate(generation, detected_at)

    def save_settings(self, values):
        settings = Settings.parse(values)
        with self.operation:
            if time.monotonic() - self.last_save < 1:
                raise ValueError("Please wait one second between saves")
            if settings.scenes != self.settings.scenes:
                available = {s["entity_id"] for s in self.api.scenes()}
                missing = set(settings.scenes) - available
                if missing:
                    raise ValueError("Scenes do not exist: " + ", ".join(sorted(missing)))
            atomic_json(self.directory / "settings.json",
                        {"supervisor_options": self.baseline, "settings": settings.to_dict()})
            self.settings = settings
            self.generation += 1
            self.last_save = time.monotonic()
            self.restart.set()
            logging.getLogger().setLevel(settings.log_level)

    def status(self):
        data = self.diagnostics.snapshot()
        data["detector_status"] = ("disabled" if not self.settings.enabled else
                                   "error" if data["audio_status"] != "connected" or data["error"]
                                   else "running")
        data["test_mode"] = self.settings.test_mode
        data["total_scenes"] = len(self.settings.scenes)
        data["busy"] = self.busy.is_set()
        return data

    def run(self):
        server = serve(self)
        threads = [threading.Thread(target=self.audio.run, name="audio"),
                   threading.Thread(target=self.worker, name="actions"),
                   threading.Thread(target=server.serve_forever, name="ingress")]
        for thread in threads:
            thread.start()
        LOG.info("Clap Control started; test mode=%s", self.settings.test_mode)
        try:
            while not self.stop.wait(30):
                status = self.status()
                LOG.info("Detector=%s audio=%s level=%.4f noise=%.4f claps=%d sequences=%d",
                         status["detector_status"], status["audio_status"], status["level"],
                         status["noise"], status["claps"], status["sequences"])
                if any(not thread.is_alive() for thread in threads):
                    raise RuntimeError("Background worker stopped")
        finally:
            self.stop.set()
            server.shutdown()
            server.server_close()
            for thread in threads:
                thread.join(timeout=16)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise SystemExit("SUPERVISOR_TOKEN missing; run as a Home Assistant app")
    app = Application(Path("/data"), HomeAssistant(token))
    logging.getLogger().setLevel(app.settings.log_level)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: app.stop.set())
    app.run()


if __name__ == "__main__":
    main()
