"""Connect to the board relay (via adb forward), print NDJSON lines and the rate per second."""

import argparse
import json
import socket
import sys
import time
from collections import Counter


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7700)
    ap.add_argument(
        "--seconds", type=float, default=0.0, help="stop after N s (0 = run until Ctrl-C)"
    )
    ap.add_argument("--save", help="also write every received line to this file")
    ap.add_argument("--send", help="send this JSON line once after connecting")
    ap.add_argument("--quiet", action="store_true", help="print only the per-second summary")
    args = ap.parse_args()

    try:
        sock = socket.create_connection((args.host, args.port), timeout=3)
    except OSError as e:
        hint = "is `adb forward tcp:7700 tcp:7700` set?"
        print(f"cannot connect to {args.host}:{args.port}: {e} ({hint})")
        return 1
    sock.settimeout(1.0)
    if args.send:
        sock.sendall((json.dumps(json.loads(args.send), separators=(",", ":")) + "\n").encode())
    save = open(args.save, "w") if args.save else None  # noqa: SIM115  closed in finally
    buf = b""
    window: Counter[str] = Counter()
    start = tick = time.monotonic()
    try:
        while not args.seconds or time.monotonic() - start < args.seconds:
            try:
                chunk = sock.recv(65536)
                if not chunk:
                    print("connection closed by board")
                    return 1
                buf += chunk
            except TimeoutError:
                pass
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if save:
                    save.write(line.decode(errors="replace") + "\n")
                try:
                    msg = json.loads(line)
                    kind = str(msg.get("k", "?"))
                except (json.JSONDecodeError, AttributeError):
                    kind = "malformed"
                    msg = line[:80]
                window[kind] += 1
                if not args.quiet:
                    print(msg if kind != "imu" else f"imu: {len(msg['d'])} ints")
            now = time.monotonic()
            if now - tick >= 1.0:
                rates = ", ".join(
                    f"{k}={n / (now - tick):.1f}/s" for k, n in sorted(window.items())
                )
                print(f"[{now - start:5.1f}s] {rates or 'no lines'}", flush=True)
                window.clear()
                tick = now
    except KeyboardInterrupt:
        pass
    finally:
        if save:
            save.close()
        sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
