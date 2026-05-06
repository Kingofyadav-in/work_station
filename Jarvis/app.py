#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from message_bus import MessageBus  # noqa: E402


def main() -> None:
    bus = MessageBus(actor="Jarvis")

    req = bus.send_request(
        intent="hi_get_workflow",
        target="Kingofyadav",
        payload={
            "text": "workflow",
            "args": {}
        },
        meta={"origin": "Jarvis.app"}
    )

    print("[Jarvis] request sent")
    print(json.dumps(req, indent=2))

    resp = bus.wait_for_response(req["request_id"], timeout=10)

    if resp is None:
        print("[Jarvis] no response")
        return

    print("[Jarvis] response received")
    print(json.dumps(resp, indent=2))


if __name__ == "__main__":
    main()
