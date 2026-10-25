"""Public registry/controller/UI checks using an isolated Windows API double."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
import test_tray as f
from mars_display.settings import SettingsError

RUN = r'Software\Microsoft\Windows\CurrentVersion\Run'
OWNER = r'Software\MarsDisplay'
EXE = r'C:\My Apps\MarsDisplay\MarsDisplay.exe'


class Key:
    def __init__(self, path): self.path = path
    def __enter__(self): return self
    def __exit__(self, *args): pass


class RegistryAPI:
    HKEY_CURRENT_USER = 'HKCU'
    KEY_QUERY_VALUE, KEY_SET_VALUE, REG_SZ = 1, 2, 1

    def __init__(self):
        self.values = {(RUN, 'OtherApp'): ('other-command', 1),
                       (OWNER, 'OtherSetting'): ('keep', 1)}
        self.calls, self.writes = [], []
        self.fail_write = None
        self.fail_read = False

    def OpenKey(self, hive, path, reserved=0, access=1):
        assert hive == self.HKEY_CURRENT_USER and access in (1, 3)
        self.calls.append(('open', hive, path, access))
        return Key(path)

    def CreateKeyEx(self, hive, path, reserved=0, access=3):
        return self.OpenKey(hive, path, reserved, access)

    def QueryValueEx(self, key, name):
        if self.fail_read: raise PermissionError('private registry detail')
        try: return self.values[key.path, name]
        except KeyError: raise FileNotFoundError from None

    def mutation(self, kind, key, name):
        self.writes.append((kind, key.path, name))
        if len(self.writes) == self.fail_write: raise PermissionError('private detail')

    def SetValueEx(self, key, name, reserved, kind, value):
        self.mutation('set', key, name)
        self.values[key.path, name] = (value, kind)

    def DeleteValue(self, key, name):
        self.mutation('delete', key, name)
        del self.values[key.path, name]


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        from mars_display.windows_startup import Registry, WindowsStartup
        self.api = RegistryAPI()
        self.registry = Registry(self.api)
        self.registration = WindowsStartup(EXE, self.registry)

    def test_default_read_is_passive_and_registration_is_user_scoped(self):
        before = deepcopy(self.api.values)
        self.assertFalse(self.registration.load().enabled)
        self.assertEqual((self.api.values, self.api.writes), (before, []))
        self.assertTrue(self.registration.save(True).enabled)
        self.assertEqual(self.registry.get('run'), '"' + EXE + '"')
        self.assertEqual(self.registry.get('owner'), '"' + EXE + '"')
        self.assertEqual(self.api.values[RUN, 'OtherApp'], before[RUN, 'OtherApp'])
        self.assertTrue(all(call[1] == 'HKCU' for call in self.api.calls))
        writes = list(self.api.writes)
        self.registration.save(True)
        self.assertEqual(self.api.writes, writes)

    def test_disable_removes_only_owned_entry_and_keeps_other_settings(self):
        self.registration.save(True)
        self.assertFalse(self.registration.save(False).enabled)
        self.assertIsNone(self.registry.get('run'))
        self.assertEqual(self.registry.get('owner'), '"' + EXE + '"')
        self.assertEqual(self.api.values[RUN, 'OtherApp'], ('other-command', 1))
        self.assertEqual(self.api.values[OWNER, 'OtherSetting'], ('keep', 1))
        writes = list(self.api.writes)
        self.registration.save(False)
        self.assertEqual(self.api.writes, writes)

    def test_foreign_invalid_or_changed_entries_are_never_overwritten(self):
        for run, owner in [('foreign.exe', None), ('"'+EXE+'"', None),
                           ('foreign.exe', '"'+EXE+'"'), ('broken', 'broken')]:
            with self.subTest(run=run, owner=owner):
                self.api.values[RUN, 'MarsDisplay'] = (run, 1)
                self.api.values.pop((OWNER, 'StartupCommand'), None)
                if owner is not None: self.api.values[OWNER, 'StartupCommand'] = (owner, 1)
                before = deepcopy(self.api.values)
                for enabled in (False, True):
                    with self.assertRaises(SettingsError): self.registration.save(enabled)
                    self.assertEqual((self.api.values, self.api.writes), (before, []))
        self.api.values[RUN, 'MarsDisplay'] = ('"'+EXE+'"', 2)
        before = deepcopy(self.api.values)
        with self.assertRaises(SettingsError): self.registration.save(False)
        self.assertEqual(self.api.values, before)

    def test_malformed_owner_blocks_both_actions_without_writes(self):
        message = ('Windows startup entry is not owned by MarsDisplay; '
                   'manage it in Windows Settings.')
        markers = [('', 1), ('"relative.exe"', 1), ('"'+EXE+'"', 2),
                   ('"C:\\bad'+chr(0xD800)+'.exe"', 1)]
        for marker in markers:
            for run in (None, ('"'+EXE+'"', 1)):
                for enabled in (False, True):
                    with self.subTest(marker=marker, run=run, enabled=enabled):
                        self.setUp()
                        self.api.values[OWNER, 'StartupCommand'] = marker
                        if run is not None: self.api.values[RUN, 'MarsDisplay'] = run
                        before = deepcopy(self.api.values)
                        with self.assertRaises(SettingsError) as caught:
                            self.registration.save(enabled)
                        self.assertEqual(str(caught.exception), message)
                        self.assertEqual((self.api.values, self.api.writes), (before, []))

    def test_portable_move_is_passive_until_explicit_update(self):
        from mars_display.windows_startup import WindowsStartup
        self.registration.save(True)
        moved = WindowsStartup(r'D:\New Folder\MarsDisplay.exe', self.registry)
        before = deepcopy(self.api.values); writes = list(self.api.writes)
        self.assertTrue(moved.load().enabled)
        self.assertTrue(moved.load().needs_update)
        self.assertEqual((self.api.values, self.api.writes), (before, writes))
        self.assertFalse(moved.save(True).needs_update)
        self.assertEqual(self.registry.get('run'), '"D:\\New Folder\\MarsDisplay.exe"')
        self.assertEqual(self.registry.get('run'), self.registry.get('owner'))
        self.assertEqual(self.api.values[RUN, 'OtherApp'], before[RUN, 'OtherApp'])

    def test_failures_never_retry_and_failed_move_reports_actual_state(self):
        from mars_display.windows_startup import Registry, WindowsStartup
        for moving, count in ((False, 2), (True, 3)):
            for fail in range(1, count + 1):
                with self.subTest(moving=moving, fail=fail):
                    api = RegistryAPI(); registry = Registry(api)
                    if moving: WindowsStartup(EXE, registry).save(True)
                    api.writes.clear(); api.fail_write = fail
                    reg = WindowsStartup(r'D:\New\MarsDisplay.exe', registry)
                    with self.assertRaisesRegex(SettingsError, '^Cannot change Windows startup; check permissions and reopen Settings\\.$'):
                        reg.save(True)
                    self.assertEqual(len(api.writes), fail)
                    self.assertEqual(reg.load().enabled, moving and fail == 1)
                    self.assertEqual(api.values[RUN, 'OtherApp'], ('other-command', 1))
        self.api.fail_read = True
        with self.assertRaisesRegex(SettingsError, '^Cannot read Windows startup; check permissions\\.$'):
            self.registration.load()
        self.assertEqual(self.api.writes, [])

    def test_invalid_inputs_and_registry_drift_have_no_write_effect(self):
        from mars_display.windows_startup import WindowsStartup
        for path in ('relative.exe', '"'+EXE+'"', EXE+'\n', r'C:\tool.cmd',
                     'C:\\'+chr(0xD800)+'.exe', 'C:\\'+'x'*252+'.exe'):
            with self.assertRaises(SettingsError): WindowsStartup(path, self.registry)
        for enabled in (None, 0, 1, 'true'):
            with self.assertRaises(SettingsError): self.registration.save(enabled)
        WindowsStartup('C:\\'+'x'*251+'.exe', self.registry)  # Exactly 260 UTF-16 units with quotes.
        self.assertEqual((self.api.calls, self.api.writes), ([], []))
        self.registration.save(True)
        self.api.values[RUN, 'MarsDisplay'] = ('external-command', 1)
        before = deepcopy(self.api.values); writes = list(self.api.writes)
        with self.assertRaises(SettingsError): self.registry.delete_run('"'+EXE+'"')
        with self.assertRaises(SettingsError): self.registry.set('run', '"'+EXE+'"', None)
        self.assertEqual((self.api.values, self.api.writes), (before, writes))

    def test_nonpackaged_or_nonwindows_factory_has_no_registry_effect(self):
        from mars_display.windows_startup import create_windows_startup
        with patch('mars_display.windows_startup.sys.platform', 'linux'):
            self.assertIsNone(create_windows_startup())
        with patch('mars_display.windows_startup.sys.platform', 'win32'), patch('mars_display.windows_startup.sys.frozen', False, create=True):
            self.assertIsNone(create_windows_startup())
        with patch('mars_display.windows_startup.sys.platform', 'win32'), patch('mars_display.windows_startup.sys.frozen', True, create=True), patch('mars_display.windows_startup.sys.executable', EXE), patch('mars_display.windows_startup.Registry', return_value=self.registry):
            registration = create_windows_startup()
        self.assertEqual(registration.command, '"'+EXE+'"')
        self.assertEqual((self.api.calls, self.api.writes), ([], []))


class StartupUITests(unittest.TestCase):
    setUp = f.TrayTests.setUp
    tearDown = f.TrayTests.tearDown
    make = f.TrayTests.make

    def make_login(self, configured=True, moved=False):
        from mars_display.windows_startup import Registry, WindowsStartup
        self.api = RegistryAPI(); self.registry = Registry(self.api)
        if moved: WindowsStartup(EXE, self.registry).save(True)
        self.login = WindowsStartup(r'D:\New\MarsDisplay.exe' if moved else EXE, self.registry)
        with patch('mars_display.tray.create_windows_startup', return_value=self.login):
            return self.make(configured=configured,
                             wait_override=lambda cancel, seconds: cancel.wait(0.01))

    def test_switch_is_independent_of_config_capture_and_exit(self):
        shell = self.make_login(configured=False)
        self.assertTrue(shell.dialog.start_with_windows.isEnabled())
        self.assertFalse(shell.dialog.start_with_windows.isChecked())
        shell.dialog.start_with_windows.click()
        f.APP.processEvents()
        self.assertTrue(self.login.load().enabled)
        self.assertFalse(shell.dialog.start_on_launch.isChecked())
        self.assertFalse(self.session.opened.is_set())
        self.assertFalse(self.store.path.exists())
        writes = list(self.api.writes)
        shell.exit_action.trigger()
        shell.dialog.start_with_windows.setChecked(False)
        self.assertTrue(shell.dialog.start_with_windows.isChecked())
        self.assertEqual(self.api.writes, writes)

    def test_live_toggle_keeps_capture_and_preferences_and_read_error_is_safe(self):
        shell = self.make_login()
        before = self.store.path.read_bytes()
        self.session.allow_open.set(); self.session.allow_close.set()
        shell.start_action.trigger()
        f.until(lambda: shell.coordinator.snapshot().frames_sent > 0)
        shell.dialog.start_with_windows.click()
        self.assertTrue(shell.coordinator.snapshot().worker_alive)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertFalse(self.store.path.with_name('settings.json.startup.json').exists())
        shell.stop_action.trigger(); f.until(lambda:not shell.coordinator.snapshot().worker_alive)
        self.assertTrue(self.login.load().enabled)
        self.api.fail_read = True
        shell.show_settings()
        self.assertFalse(shell.dialog.start_with_windows.isEnabled())
        self.assertIn('Cannot read Windows startup', shell.dialog.windows_startup_hint.text())

    def test_relocation_button_and_failed_save_read_back_real_registry_state(self):
        shell = self.make_login(moved=True)
        self.assertTrue(shell.dialog.start_with_windows.isChecked())
        self.assertFalse(shell.dialog.update_startup_path.isHidden())
        self.api.writes.clear(); self.api.fail_write = 2
        shell.dialog.update_startup_path.click()
        self.assertFalse(shell.dialog.start_with_windows.isChecked())
        self.assertFalse(self.login.load().enabled)
        self.assertEqual(len(self.api.writes), 2)
        self.assertEqual(shell.dialog.message.text(), 'Cannot change Windows startup; check permissions and reopen Settings.')
        self.api.fail_write = None
        shell.dialog.start_with_windows.click()
        self.assertTrue(self.login.load().enabled)
        self.assertFalse(self.login.load().needs_update)
        self.assertTrue(shell.dialog.update_startup_path.isHidden())

    def test_unavailable_control_leaves_previous_manual_actions_unchanged(self):
        with patch('mars_display.tray.create_windows_startup', return_value=None): shell = self.make()
        self.assertFalse(shell.dialog.start_with_windows.isEnabled())
        self.assertTrue(shell.start_action.isEnabled())
        self.assertFalse(shell.stop_action.isEnabled())
        self.assertFalse(self.session.opened.is_set())
