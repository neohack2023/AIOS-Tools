from __future__ import annotations

import json

from aios_tools.runner import invoke


def main() -> None:
    receipt = invoke(
        "browser.profile.replay",
        {"profile_id": "SITE_PROFILE_SUNO_TRACK_HARVEST_01"},
        scope="global-working-memory",
        mode="READ_ONLY",
        requested_by={"type": "CI", "id": "browser-activation-replay"},
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    output = receipt.get("output", {})
    if receipt.get("status") != "COMPLETED":
        raise SystemExit(1)
    if output.get("terminal_status") != "SUCCEEDED":
        raise SystemExit(2)
    if output.get("fresh_session") is not True:
        raise SystemExit(3)
    if output.get("final_origin_match") is not True:
        raise SystemExit(4)
    if output.get("final_path_digest_match") is not True:
        raise SystemExit(5)
    if output.get("authority_transfer") is not False:
        raise SystemExit(6)


if __name__ == "__main__":
    main()
