"""A bounded control process that invokes the actual nested kernel launcher."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from tests.acceptance.rl00a.rl00a_cgroup import Group, save
from tests.acceptance.rl00bc import rl00bc_kernel


def _execute(args: argparse.Namespace, group: Group) -> dict[str, object]:
    argv = args.payload[1:] if args.payload and args.payload[0] == "--" else args.payload
    native_environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/nonexistent"),
        "LANG": "C.UTF-8",
    }
    try:
        result = rl00bc_kernel.execute(
            group,
            [sys.executable, str(Path(__file__).with_name("rl00bc_nested_payload.py")), *argv],
            args.repo,
            native_environment,
            args.output,
            memory_mib=args.memory_mib,
            tasks=args.tasks,
            native_seconds=120,
            ancestor_deadline_ns=args.deadline,
            payload_deadline_ns=args.payload_deadline,
        )
    except (ValueError, TimeoutError) as error:
        return {"success": False, "raised": f"{type(error).__name__}: {error}"}
    else:
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group-fd", type=int, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--memory-mib", type=int, required=True)
    parser.add_argument("--tasks", type=int, required=True)
    parser.add_argument("--deadline", type=int, required=True)
    parser.add_argument("--payload-deadline", type=int, required=True)
    parser.add_argument("payload", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    group = Group(args.group_fd, Path(f"/proc/self/fd/{args.group_fd}").readlink())
    try:
        save(args.result, _execute(args, group))
    finally:
        os.close(group.fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
