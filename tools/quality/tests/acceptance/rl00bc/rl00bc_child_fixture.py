"""Bounded owned child: rendezvous before allocation and hold until released."""

CHILD = '''import sys
mib = int(sys.argv[1])
if not 1 <= mib <= 1536:
    raise ValueError("invalid child allocation")
print("ready", flush=True)
if sys.stdin.buffer.read(1) != b"a":
    raise ValueError("missing allocation release")
held = bytearray(mib * 1048576)
held[::4096] = bytes([1]) * len(held[::4096])
print("allocated", flush=True)
if sys.stdin.buffer.read(1) != b"x":
    raise ValueError("missing cleanup release")
'''
