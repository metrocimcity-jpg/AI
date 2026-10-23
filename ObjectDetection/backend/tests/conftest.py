"""Keep tests off the developer database and off the network."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_DATA = Path(tempfile.mkdtemp(prefix="siteguard-test-"))
os.environ["SITEGUARD_DATA_DIR"] = str(_DATA)
os.environ["SITEGUARD_AUTH_REQUIRED"] = "false"
os.environ["SITEGUARD_AUTOSTART"] = "false"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FACE_RECOGNITION_ENABLED"] = "false"
