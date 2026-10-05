#!/usr/bin/env python3
"""Exercise the launcher protocol and real fzf without a desktop session."""
import concurrent.futures
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import subprocess
import tempfile
import termios
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "src/fzf-popup"


class Popup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="popup ' $ test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.real_fzf = os.environ.get("REAL_FZF", shutil.which("fzf"))
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        TMPDIR=str(self.root), LOG=str(self.root / "log"),
                        FZF_DEFAULT_OPTS="", FZF_DEFAULT_COMMAND="")
        self.env.pop("FZF_POPUP_LAUNCHER", None)
        self.env.pop("FZF_DEFAULT_OPTS_FILE", None)
        self.launcher = self.bin / "launcher ' with spaces"
        self.launcher.write_text(f"#!{shutil.which('bash')}\n"
                                 'printf "%s\\n" "$FZF_POPUP_TITLE" > "$LOG.title"\n'
                                 'printf "launcher diagnostic\\n"\nexec "$@"\n')
        self.launcher.chmod(0o755)
        self.fzf = self.bin / "fzf"
        self.fzf.write_text(f"#!{shutil.which('python3')}\n" + '''
import json, os, sys, time
with open(os.environ['LOG'], 'w') as out: json.dump(sys.argv[1:], out)
time.sleep(float(os.environ.get('DELAY', '0')))
sys.stdout.buffer.write(sys.stdin.buffer.read())
sys.exit(int(os.environ.get('FZF_STATUS', '0')))
''')
        self.fzf.chmod(0o755)

    def call(self, *args, data="42\tChinese 中文\n".encode(), **kwargs):
        return subprocess.run(["bash", str(SCRIPT), *args], env=self.env,
                              input=data, capture_output=True, **kwargs)

    def test_argv_title_and_raw_rows(self):
        args = ["--delimiter=\t", "--with-nth=2..", "--preview=printf '%s' {1}",
                "--header=$(touch SHOULD-NOT-EXIST) 'quoted' `literal`"]
        result = self.call("--title", "title ' $ ` x", "--launcher", str(self.launcher), "--", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "42\tChinese 中文\n".encode())
        self.assertIn(b"launcher diagnostic", result.stderr)
        self.assertEqual(json.loads((self.root / "log").read_text()), args)
        self.assertEqual((self.root / "log.title").read_text(), "title ' $ ` x\n")
        self.assertFalse(list(self.root.glob("fzf-popup.*")))

    def test_env_default_and_cli_override(self):
        self.env['FZF_POPUP_LAUNCHER'] = '/does/not/exist'
        self.assertEqual(self.call("--launcher", str(self.launcher), "--").returncode, 0)
        self.assertNotEqual(self.call("--").returncode, 0)
        self.env['FZF_POPUP_LAUNCHER'] = str(self.launcher)
        self.assertEqual(self.call("--").returncode, 0)

    def test_status_and_cleanup(self):
        for status in (0, 1, 2, 130):
            self.env['FZF_STATUS'] = str(status)
            result = self.call("--launcher", str(self.launcher), "--", data=b"")
            self.assertEqual(result.returncode, status, result.stderr)
            self.assertEqual(result.stdout, b"")
            self.assertFalse(list(self.root.glob("fzf-popup.*")))

    def test_launcher_failure_and_no_completion(self):
        for body, expected in [('exit 7', 7), ('exit 0', 2)]:
            self.launcher.write_text(f"#!{shutil.which('bash')}\n{body}\n")
            result = self.call("--launcher", str(self.launcher), "--")
            self.assertEqual(result.returncode, expected)
            self.assertIn(b"must wait", result.stderr)
            self.assertFalse(list(self.root.glob("fzf-popup.*")))

    def test_concurrent_calls_are_independent(self):
        self.env['DELAY'] = '0.05'
        def check(i):
            data = f"{i}\trow {i}\n".encode()
            result = self.call("--launcher", str(self.launcher), "--", data=data)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, data)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(check, range(8)))
        self.assertFalse(list(self.root.glob("fzf-popup.*")))

    def test_without_launcher(self):
        result = self.call("--", "--filter=text", data=b"text\n")
        self.assertEqual(result.stdout, b"text\n")
        self.assertEqual(json.loads((self.root / 'log').read_text()), ['--filter=text'])

    def test_signal_cleanup(self):
        self.env['DELAY'] = '10'
        process = subprocess.Popen(['bash', str(SCRIPT), '--launcher', str(self.launcher), '--'],
                                   env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        process.stdin.close()
        deadline = time.monotonic() + 3
        while not (self.root / 'log').exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3)
        process.stdout.close()
        process.stderr.close()
        self.assertFalse(list(self.root.glob('fzf-popup.*')))

    def test_real_fzf_filter(self):
        self.fzf.unlink()
        self.fzf.symlink_to(self.real_fzf)
        result = self.call('--launcher', str(self.launcher), '--', '--delimiter=\t',
                           '--with-nth=2..', '--filter=second', data=b'1\tfirst\n2\tsecond\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'2\tsecond\n')

    def test_real_fzf_preview_and_enter(self):
        self.fzf.unlink()
        self.fzf.symlink_to(self.real_fzf)
        candidates = self.root / 'candidates'
        candidates.write_text('hidden\tvisible\n')
        self.env['TERM'] = 'xterm-256color'
        pid, terminal = pty.fork()
        if pid == 0:
            with candidates.open('rb') as source:
                os.dup2(source.fileno(), 0)
            os.execvpe('bash', ['bash', str(SCRIPT), '--launcher', str(self.launcher), '--',
                              '--delimiter=\t', '--with-nth=2..',
                              '--preview=printf POPUP-PREVIEW-{1}'], self.env)
        output = bytearray()
        exited = False
        try:
            import fcntl
            fcntl.ioctl(terminal, termios.TIOCSWINSZ, struct.pack('HHHH', 40, 120, 0, 0))
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if select.select([terminal], [], [], 0.1)[0]:
                    chunk = os.read(terminal, 65536)
                    output.extend(chunk)
                    if b'\x1b[6n' in chunk: os.write(terminal, b'\x1b[1;1R')
                    if b'POPUP-PREVIEW-hidden' in output: break
            self.assertIn(b'POPUP-PREVIEW-hidden', output)
            os.write(terminal, b'\r')
            while time.monotonic() < deadline:
                child, status = os.waitpid(pid, os.WNOHANG)
                if child:
                    exited = True
                    self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                    break
                time.sleep(0.02)
            self.assertTrue(exited)
        finally:
            if not exited:
                os.killpg(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            os.close(terminal)


if __name__ == '__main__':
    unittest.main()
