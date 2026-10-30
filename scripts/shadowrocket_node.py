#!/usr/bin/env python3
"""Read Shadowrocket's currently selected server name. Read-only, bounded.

The Group Container is a protected location: macOS can stall a caller that opens
it, so this runs as a short-lived child with a hard deadline and never writes.
"""
import json
import plistlib
import time
from pathlib import Path

SOURCE = "shadowrocket_selected_server"
PREFIX = "group.com.liguangming."
PLIST = (Path.home() / "Library/Group Containers"
         / "group.com.liguangming.Shadowrocket/Library/Preferences"
         / "group.com.liguangming.Shadowrocket.plist")


def read(path=PLIST):
    result = {"source": SOURCE, "state": "unavailable", "name": "", "uuid": "",
              "at": int(time.time())}
    try:
        with open(path, "rb") as handle:
            data = plistlib.load(handle)
        name = data.get(PREFIX + "SelectedServerName")
        uuid = data.get(PREFIX + "SelectedServerUUID")
        if isinstance(name, str) and name.strip():
            result.update(state="ok", name=name.strip()[:120], uuid=str(uuid or "")[:64])
    except (OSError, plistlib.InvalidFileException, ValueError, TypeError):
        pass
    return result


if __name__ == "__main__":
    print(json.dumps(read(), ensure_ascii=False))
