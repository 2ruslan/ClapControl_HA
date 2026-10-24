import json
import os
import tempfile
from pathlib import Path


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class State:
    def __init__(self, path):
        self.path = Path(path)
        self.value = {"scenes": [], "index": -1, "last_scene": None, "last_trigger": None}
        if self.path.exists():
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(value, dict) or not isinstance(value.get("scenes"), list)
                    or type(value.get("index")) is not int
                    or not -1 <= value["index"] < len(value["scenes"])
                    or any(not isinstance(s, str) or not s.startswith("scene.")
                           for s in value["scenes"])):
                raise ValueError("Invalid saved cycle state; restore or remove state.json")
            self.value.update(value)

    def next_index(self, scenes):
        if not scenes:
            return None
        if self.value["scenes"] == scenes:
            return (self.value["index"] + 1) % len(scenes)
        # Preserve last scene on reorder; start at first if it was removed.
        last = self.value["last_scene"]
        return (scenes.index(last) + 1) % len(scenes) if last in scenes else 0

    def commit(self, scenes, index, timestamp):
        value = {"scenes": list(scenes), "index": index,
                 "last_scene": scenes[index], "last_trigger": timestamp}
        atomic_json(self.path, value)
        self.value = value
