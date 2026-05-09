"""
Sistema di logging JSON Lines per server TCP e tracker.
"""

import datetime
import json
import threading
from pathlib import Path


class JsonEventLogger:
    """Scrive eventi strutturati in system log e log giornalieri per tracker."""

    def __init__(self, base_dir="logs"):
        self.base_dir = Path(base_dir)
        self.system_log_path = self.base_dir / "system.json"
        self.lock = threading.Lock()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.system_log_path.touch(exist_ok=True)

    def log_system_event(
        self,
        level,
        event_type,
        message,
        component,
        imei=None,
        client_addr=None,
        details=None,
    ):
        event = self._build_event(
            level=level,
            event_type=event_type,
            message=message,
            component=component,
            imei=imei,
            client_addr=client_addr,
            details=details,
        )
        self._append_json_line(self.system_log_path, event)
        return event

    def log_tracker_event(
        self,
        imei,
        level,
        event_type,
        message,
        component,
        client_addr=None,
        details=None,
    ):
        event = self._build_event(
            level=level,
            event_type=event_type,
            message=message,
            component=component,
            imei=imei,
            client_addr=client_addr,
            details=details,
        )
        self._append_json_line(self.system_log_path, event)
        self._append_json_line(self._get_tracker_log_path(imei), event)
        return event

    def _build_event(
        self,
        level,
        event_type,
        message,
        component,
        imei=None,
        client_addr=None,
        details=None,
    ):
        event = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
            "level": level,
            "event_type": event_type,
            "component": component,
            "message": message,
        }

        if imei:
            event["imei"] = str(imei)

        if client_addr:
            event["client_ip"] = client_addr[0]
            event["client_port"] = client_addr[1]

        if details is not None:
            event["details"] = self._make_json_safe(details)

        return event

    def _get_tracker_log_path(self, imei):
        tracker_dir = self.base_dir / str(imei)
        tracker_dir.mkdir(parents=True, exist_ok=True)
        file_name = datetime.date.today().isoformat() + ".json"
        tracker_log_path = tracker_dir / file_name
        tracker_log_path.touch(exist_ok=True)
        return tracker_log_path

    def _append_json_line(self, path, event):
        line = json.dumps(event, ensure_ascii=True, default=str)
        with self.lock:
            with path.open("a", encoding="utf-8") as log_file:
                log_file.write(line + "\n")

    def _make_json_safe(self, value):
        if isinstance(value, dict):
            return {str(key): self._make_json_safe(val) for key, val in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._make_json_safe(item) for item in value]
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            return value.isoformat()
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value


app_logger = JsonEventLogger()
