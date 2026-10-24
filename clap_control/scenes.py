from datetime import datetime, timezone
import json
import urllib.error
import urllib.request


class APIError(Exception):
    pass


class HomeAssistant:
    def __init__(self, token, base="http://supervisor/core/api", timeout=5):
        self.token = token
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, method, path, data=None):
        request = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise APIError(f"Home Assistant API: HTTPError (HTTP {code})") from None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            # Never include headers or token in errors.
            code = getattr(exc, "code", None)
            raise APIError(f"Home Assistant API: {type(exc).__name__}" +
                           (f" (HTTP {code})" if code else "")) from None

    def scenes(self):
        return [{"entity_id": x["entity_id"],
                 "name": x.get("attributes", {}).get("friendly_name", x["entity_id"]),
                 "available": x["state"] != "unavailable"}
                for x in self.request("GET", "/states") if x["entity_id"].startswith("scene.")]

    def activate(self, entity_id):
        state = self.request("GET", "/states/" + entity_id)
        # An unactivated HA scene can legitimately have state 'unknown'.
        if state.get("state") == "unavailable":
            raise APIError(f"Scene unavailable: {entity_id}")
        self.request("POST", "/services/scene/turn_on", {"entity_id": entity_id})


class SceneCycle:
    def __init__(self, api, state):
        self.api, self.state = api, state
        self.persistence_failed = False

    def trigger(self, settings):
        if settings.test_mode or not settings.enabled or not settings.scenes:
            return None
        if self.persistence_failed:
            raise APIError("State persistence failed; repair storage and restart before activating")
        index = self.state.next_index(settings.scenes)
        scene = settings.scenes[index]
        self.api.activate(scene)
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            self.state.commit(settings.scenes, index, timestamp)
        except OSError:
            self.persistence_failed = True
            raise
        return dict(clap_count=settings.clap_count, timestamp=timestamp,
                    scene=scene, scene_number=index + 1, total_scenes=len(settings.scenes))
