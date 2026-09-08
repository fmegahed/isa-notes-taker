"""ask_user_input polls stdin for a prompt answer without blocking the agent.
On Windows, select() only accepts sockets, so console input has to be polled
with msvcrt instead; this covers both the unattended (no terminal) path that
every platform hits and the Windows-only polling logic."""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import notes_tools as NT   # noqa: E402

# No terminal available: this is the exact situation of an unattended run,
# e.g. the MCP subprocess whose stdin is the protocol stream (a pipe). We
# feed an empty pipe rather than os.devnull: on Windows the NUL device is a
# character device, the same file type as a console, so the CRT's isatty()
# reports NUL as a terminal (returns True) even though no one is there to
# type into it. A closed/empty pipe reports isatty() == False on every
# platform and matches the real subprocess scenario.
code = (
    "import sys; sys.path.insert(0, %r)\n"
    "import notes_tools\n"
    "print(repr(notes_tools.ask_user_input('p: ')))\n"
) % str(HERE)

proc = subprocess.run(
    [sys.executable, "-c", code],
    input=b"",
    capture_output=True,
    timeout=20,
)
assert proc.returncode == 0, proc.stderr.decode(errors="replace")
assert proc.stdout.decode(errors="replace").strip() == "''", proc.stdout
print("no terminal available: ask_user_input returns '' without dying")

if os.name != "nt":
    print("skipping Windows-only msvcrt polling checks (not on Windows)")
else:
    import msvcrt

    class FakeStdin:
        def isatty(self):
            return True

        def readline(self):
            return "hello\n"

    real_stdin = sys.stdin
    real_kbhit = msvcrt.kbhit
    try:
        sys.stdin = FakeStdin()
        msvcrt.kbhit = lambda: True
        result = NT.ask_user_input("p: ")
        assert result == "hello", result
        print("msvcrt reports a key ready: returns the typed line")

        msvcrt.kbhit = lambda: False
        result = NT.ask_user_input("p: ", should_abort=lambda: True)
        assert result is None, result
        print("should_abort fires before any key: returns None")
    finally:
        sys.stdin = real_stdin
        msvcrt.kbhit = real_kbhit
