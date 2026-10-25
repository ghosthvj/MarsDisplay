"""Local coordination and generated evidence must not be staged accidentally."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[1]


class RepositoryHygieneTests(unittest.TestCase):
    def test_private_records_and_existing_build_outputs_are_ignored(self):
        ignored = [
            'odd/tasks/local.md', '.herdr-web-ui/preview.png', '.ovis/preview.png',
            'build/output.txt', 'dist/output.zip', '.venv/marker',
            'src/__pycache__/module.pyc', 'src/cache.pyo', 'package.egg-info/PKG-INFO',
        ]
        public = [
            'docs/usb-hardware-qualification.md', 'third_party/notice.txt',
            'tools/windows-usb-probe/pattern.json', 'src/mars_display/app.py',
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
            init = subprocess.run(['git', 'init', '-q'], cwd=root, env=env,
                                  capture_output=True, text=True, timeout=10)
            self.assertEqual((init.returncode, init.stdout, init.stderr), (0, '', ''))
            (root / '.gitignore').write_bytes((ROOT / '.gitignore').read_bytes())
            names = ignored + public
            before = {}
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'keep local and public evidence')
                before[name] = path.read_bytes()
            result = subprocess.run(['git', '-c', 'core.excludesFile=' + os.devnull,
                                     'check-ignore', '--no-index', '--stdin'],
                                    input='\n'.join(names) + '\n', cwd=root, env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual((result.returncode, result.stdout, result.stderr),
                             (0, ''.join(name + '\n' for name in ignored), ''))
            self.assertEqual({name: (root / name).read_bytes() for name in names}, before)
            self.assertEqual({str(p.relative_to(root)).replace(os.sep, '/') for p in root.rglob('*')
                              if p.is_file() and '.git' not in p.relative_to(root).parts},
                             {'.gitignore', *names})
