"""
serve.py
Start the API on BOTH loopback addresses, so every spelling of "localhost" works.

Why this exists: on Windows, `localhost` usually resolves to the IPv6 address
::1, while `uvicorn --host 127.0.0.1` binds IPv4 only. The server is then up and
healthy, and the browser still reports a connection error -- with nothing in the
log, because the request never arrives. `--host ::` inverts the problem: ::1
works and 127.0.0.1 stops. Neither single bind covers both, because Windows
defaults IPV6_V6ONLY to on, so an IPv6 socket does not accept IPv4 traffic.

The fix is two loopback sockets in one process, which uvicorn accepts directly.
That keeps the service reachable at both spellings while staying bound to
loopback -- nothing is exposed to the network.

    cd backend
    python scripts/serve.py                 # http://localhost:8000 and http://127.0.0.1:8000
    python scripts/serve.py --port 9000
    python scripts/serve.py --reload        # single-address dev mode, auto-restart
    python scripts/serve.py --host 0.0.0.0  # share on the LAN (see the warning it prints)
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn  # noqa: E402

LOOPBACK = (
    (socket.AF_INET, "127.0.0.1"),
    (socket.AF_INET6, "::1"),
)


def loopback_sockets(port: int) -> list[socket.socket]:
    """One listening socket per loopback family. IPv6 is optional, not fatal."""
    sockets: list[socket.socket] = []
    for family, address in LOOPBACK:
        try:
            sock = socket.socket(family, socket.SOCK_STREAM)
            if family == socket.AF_INET6:
                # Keep this socket to IPv6 only; the IPv4 socket covers the rest.
                # Without it, Linux would bind both and then the IPv4 bind fails.
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((address, port))
            sock.listen(128)
            sock.set_inheritable(True)
            sockets.append(sock)
        except OSError as e:
            for s in sockets:
                s.close()
            if family == socket.AF_INET6:
                # An IPv4-only machine is fine; carry on with what bound.
                print(f"note: could not bind [{address}]:{port} ({e}); IPv4 only.")
                continue
            raise SystemExit(
                f"Could not bind {address}:{port} ({e}).\n"
                f"Something else is probably already using port {port} -- "
                "stop it, or pass --port."
            ) from e
    return sockets


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument(
        "--host",
        default=None,
        help="Bind one specific address instead of both loopbacks (e.g. 0.0.0.0 for the LAN).",
    )
    ap.add_argument(
        "--reload",
        action="store_true",
        help="Auto-restart on code changes. Binds a single address (uvicorn's reloader "
        "cannot inherit pre-bound sockets).",
    )
    args = ap.parse_args()

    if args.host or args.reload:
        host = args.host or "127.0.0.1"
        if host not in {"127.0.0.1", "::1", "localhost"}:
            print(
                f"warning: binding {host} exposes this API to your whole network. "
                "On shared or venue wifi, prefer the default loopback bind."
            )
        print(f"  http://{host}:{args.port}/docs")
        uvicorn.run(
            "repurpose_api.main:app", host=host, port=args.port, reload=args.reload
        )
        return 0

    sockets = loopback_sockets(args.port)
    families = ", ".join(
        f"[{a}]" if f == socket.AF_INET6 else a
        for (f, a), _ in zip(LOOPBACK, sockets)
    )
    print(f"RepurposeAI API listening on {families} port {args.port}")
    print(f"  http://localhost:{args.port}/docs")
    print(f"  http://127.0.0.1:{args.port}/docs")

    server = uvicorn.Server(uvicorn.Config("repurpose_api.main:app"))
    server.run(sockets=sockets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
