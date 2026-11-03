"""Portable recipe contracts, not Docker or frozen-runtime qualification."""
import json
from pathlib import Path
import re
import subprocess
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / 'packaging' / 'linux'
BASE = 'ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852'
PYTHON_SHA256 = '93e583f243454e6e9e4588ca2c2662206ad961659863277afcdb96801647d640'


class LinuxPackagingTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((PACKAGING / 'toolchain.json').read_text(encoding='utf-8'))
        self.recipe = (PACKAGING / 'Dockerfile').read_text(encoding='utf-8')

    def test_official_source_and_target_identity(self):
        self.assertEqual(self.manifest['platform'], 'linux/amd64')
        self.assertEqual(self.manifest['base_image'], BASE)
        source = self.manifest['python']
        self.assertEqual(source['version'], '3.13.5')
        self.assertEqual(source['sha256'], PYTHON_SHA256)
        self.assertEqual(source['url'], 'https://www.python.org/ftp/python/3.13.5/Python-3.13.5.tar.xz')
        self.assertEqual(source['checksum_evidence'], source['url'] + '.spdx.json')
        self.assertEqual(source['release_url'], 'https://www.python.org/downloads/release/python-3135/')
        self.assertIn(f'FROM --platform=linux/amd64 {BASE}', self.recipe)
        for value in (source['version'], source['url'], source['sha256']):
            self.assertIn(value, self.recipe)

    def test_checksum_precedes_extraction_and_shared_nonroot_build(self):
        checksum = self.recipe.index('sha256sum -c -')
        extract = self.recipe.index('tar -xJf')
        configure = self.recipe.index('./configure')
        self.assertLess(checksum, extract)
        self.assertLess(extract, configure)
        self.assertIn('--enable-shared', self.recipe)
        self.assertIn('&&', self.recipe[checksum:extract])
        users = re.findall(r'^USER (.+)$', self.recipe, re.MULTILINE)
        self.assertEqual(users, ['builder'])
        self.assertLess(self.recipe.index('USER builder'), configure)
        self.assertIn('python -m playwright install chromium', self.recipe)
        self.assertIn('PLAYWRIGHT_BROWSERS_PATH=0', self.recipe)

    def test_context_is_explicit_and_no_sandbox_escape(self):
        copies = re.findall(r'^COPY (.+)$', self.recipe, re.MULTILINE)
        self.assertEqual(copies, [
            'packaging/linux/toolchain.json /opt/toolchain.json',
            'pyproject.toml /opt/pyproject.toml',
        ])
        for forbidden in ('--no-sandbox', '--privileged', '--security-opt',
                          '--ipc=host', 'appimagetool', 'COPY .', 'ADD '):
            self.assertNotIn(forbidden, self.recipe)
        self.assertIn('dpkg-query', self.recipe)
        self.assertIn('pip freeze --all', self.recipe)
        self.assertIn('ldd --version', self.recipe)

    def test_dependency_install_uses_current_project_pins_without_project_copy(self):
        # Execute the recipe's installer with only its external effects intercepted.
        # This checks actual argument construction, not a duplicated requirements list.
        script = self.recipe.split("RUN python - <<'INSTALL_DEPS'\n", 1)[1].split('\nINSTALL_DEPS', 1)[0]
        metadata = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
        project = tomllib.loads(metadata)
        expected = list(dict.fromkeys(project['project']['dependencies']
                        + project['project']['optional-dependencies']['build']
                        + project['build-system']['requires']))
        with patch.object(Path, 'read_text', return_value=metadata), \
                patch.object(subprocess, 'check_call') as install:
            exec(compile(script, 'Dockerfile:INSTALL_DEPS', 'exec'), {})
        arguments = install.call_args.args[0]
        self.assertEqual(arguments[1:5], ['-m', 'pip', 'install', '--no-cache-dir'])
        self.assertEqual(arguments[5:], expected)
        self.assertEqual(install.call_count, 1)
        self.assertTrue(all(re.fullmatch(r'[A-Za-z0-9_-]+==[0-9.]+', pin) for pin in expected))


if __name__ == '__main__':
    unittest.main()
