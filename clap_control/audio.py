"""Bounded, restartable parec capture. No audio files or unbounded queues."""
import os
import select
import subprocess
import time
from .detector import FRAME_BYTES


def read_frame(process, stop, restart, timeout=2):
    frame = bytearray()
    deadline = time.monotonic() + timeout
    while len(frame) < FRAME_BYTES:
        if stop.is_set() or restart.is_set():
            return None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OSError("PulseAudio stream stalled")
        ready, _, _ = select.select([process.stdout], [], [], min(0.2, remaining))
        if ready:
            data = os.read(process.stdout.fileno(), FRAME_BYTES - len(frame))
            if not data:
                raise OSError("PulseAudio stream closed")
            frame.extend(data)
    return bytes(frame)


class Audio:
    def __init__(self, stop, restart, source, on_frame, on_status,
                 factory=subprocess.Popen, reader=read_frame, retry_seconds=3):
        self.stop, self.restart, self.source = stop, restart, source
        self.on_frame, self.on_status = on_frame, on_status
        self.factory, self.reader, self.retry_seconds = factory, reader, retry_seconds

    def run(self):
        while not self.stop.is_set():
            self.restart.clear()
            process = None
            try:
                args = ["parec", "--raw", "--format=s16le", "--rate=16000", "--channels=1",
                        "--latency-msec=20", "--client-name=Clap Control"]
                source = self.source()
                if source:
                    args.append("--device=" + source)
                self.on_status("connecting", None)
                process = self.factory(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
                online = False
                while not self.stop.is_set() and not self.restart.is_set():
                    frame = self.reader(process, self.stop, self.restart)
                    if frame is None:
                        break
                    if not online:
                        self.on_status("connected", None)
                        online = True
                    self.on_frame(frame, time.monotonic())
            except (OSError, subprocess.SubprocessError) as exc:
                self.on_status("error", str(exc))
            finally:
                if process is not None:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=2)
                    if process.stdout:
                        process.stdout.close()
            if not self.restart.is_set():
                self.stop.wait(self.retry_seconds)
        self.on_status("stopped", None)
