from dataclasses import asdict, dataclass, field, replace
import json
import re
from pathlib import Path
from .state import atomic_json


@dataclass(frozen=True)
class Settings:
    enabled: bool = True
    clap_count: int = 2
    sensitivity: int = 50
    max_interval_ms: int = 800
    cooldown_seconds: float = 3
    scenes: list[str] = field(default_factory=list)
    audio_source: str = ""
    log_level: str = "INFO"
    test_mode: bool = False
    emit_event: bool = True

    @classmethod
    def parse(cls, data):
        if not isinstance(data, dict) or set(data) - set(cls.__dataclass_fields__):
            raise ValueError("Unknown settings or invalid object")
        s = cls(**data)
        for name in ("enabled", "test_mode", "emit_event"):
            if type(getattr(s, name)) is not bool:
                raise ValueError(f"{name}: expected boolean")
        for name, low, high in (("clap_count", 1, 3), ("sensitivity", 1, 100),
                                ("max_interval_ms", 250, 2000)):
            value = getattr(s, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name}: expected integer {low}..{high}")
        if type(s.cooldown_seconds) not in (int, float) or not 0.5 <= s.cooldown_seconds <= 60:
            raise ValueError("cooldown_seconds: expected 0.5..60")
        if not isinstance(s.scenes, list) or any(
            not isinstance(x, str) or not re.fullmatch(r"scene\.[a-z0-9_]+", x) for x in s.scenes
        ):
            raise ValueError("scenes: expected list of scene.entity_id")
        if not isinstance(s.audio_source, str) or len(s.audio_source) > 256 or any(
            ord(c) < 32 for c in s.audio_source
        ):
            raise ValueError("Invalid PulseAudio source")
        if s.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            raise ValueError("Invalid log level")
        return s

    def to_dict(self):
        return asdict(self)


def load_settings(directory: Path):
    """Migrate 1.0 options once, then use only the Ingress settings file."""
    saved_path = directory / "settings.json"
    saved = json.loads(saved_path.read_text(encoding="utf-8")) if saved_path.exists() else None
    options_path = directory / "options.json"
    options = json.loads(options_path.read_text(encoding="utf-8")) if options_path.exists() else {}
    log_level = Settings.parse({"log_level": options.get("log_level", "INFO")}).log_level
    if saved is not None and saved.get("version") == 2:
        return replace(Settings.parse(saved["settings"]), log_level=log_level)
    baseline = Settings.parse(options).to_dict()
    if saved is not None and (not (set(options) - {"log_level"}) or saved.get("supervisor_options") == baseline):
        settings = Settings.parse(saved["settings"])
    else:
        settings = Settings.parse(baseline)
    settings = replace(settings, log_level=log_level)
    atomic_json(saved_path, {"version": 2, "settings": settings.to_dict()})
    return settings
