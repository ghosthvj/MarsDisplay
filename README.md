# MarsDisplay

**Your MARS dashboard, on real hardware.** MarsDisplay renders the MARS `/display` web page in a
real browser and streams it to a small USB display panel, so the status wall shows
live data instead of a static picture.

## Why it exists

Cheap USB screens ship with vendor software that mirrors a screenshot and
gives you no control. MarsDisplay does it properly: a real Chromium engine renders
your dashboard, every frame is encoded and pushed over the panel's own USB interface,
and you decide when capture runs. No scraping, no screen capture, no vendor app.

## What it does

- **Renders your page for real.** A bundled Chromium (Playwright) draws the MARS URL you
  configure, so JavaScript, canvas and auto-refreshing charts behave like in a browser.
- **Native USB output.** 320×480 portrait and 480x320 landscape, RGB565 little-endian, 122 writes / 307,222
  bytes per frame over the panel's standard USB-serial interface — no vendor software.
- **Brightness you control.** 20 / 40 / 60 / 80 / 100 %, saved and applied at Start,
  adjustable live while the panel is running.
- **Tray-first, quiet.** Status / Settings, Start, Stop, Exit. One fixed-height window
  that scrolls, not a pile of dialogs. A single instance owns the panel at a time.
- **Opt-in automation.** Start capturing whenever the app opens, and start the app when
  you sign in to Windows. Both off by default, both one click to undo.
- **Honest state.** Live-connected and stale flags, lifetime frame count, native timing
  logs and a frame preview. Host completion is reported as host completion — never
  dressed up as an acknowledgement from the panel.

## Requirements

- Windows x64 in an interactive desktop session with a system tray
- The USB screen: SHCHV TUS-35 ("USB Screen"), VID `1A86` / PID `5722`, serial `USB35INCHIPSV2`
- The vendor application closed — it holds the same serial port
- A MARS `/display` URL served over **HTTPS** that answers directly and needs no
  interactive login. MarsDisplay never follows a redirect, so a URL that bounces to
  another address (typically `http://` → `https://`) is reported as a failed capture
  instead of being chased

## Quick start

1. Download the [latest release](https://github.com/ghosthvj/MarsDisplay/releases/latest)
   ZIP and extract the **whole archive** into a new folder.
2. Run `MarsDisplay.exe`. It waits in the tray, stopped and unconfigured.
3. Tray → **Status / Settings**: enter the **MARS URL**, click **Refresh USB identities**,
   choose your screen explicitly, then **Save**.
4. **Start.** The panel shows your dashboard and the tray reports frames and live state.

## Configuration

Everything is stored in `%LOCALAPPDATA%\MarsDisplay\settings.json`. The first save also
keeps a schema-1 backup beside it, so an older build can always read your setup back.

**MARS URL** — the final HTTPS address of the page, the one that answers with the
dashboard itself. Nothing loads until you press Start, and the app contacts only
the address you saved: a redirecting URL fails deliberately, because following it
would mean reaching a path you never approved.

**Screen selection** — Refresh lists available identities and you pick one. Missing,
duplicate or unhealthy devices are refused rather than guessed, and the saved identity
is displayed read-only afterwards.

**Brightness** — while stopped, **Enable Brightness** turns on saved brightness and
backs up your current settings first; from then on the slider sets the level at Start
and changes it live while running.

**Startup** — *Start capture when MarsDisplay opens* saves the moment you toggle it and
applies to every later launch until you turn it off (*save your configuration first*).
*Start MarsDisplay when I sign in to Windows* registers the current user only: no admin
rights, no service, no scheduled task. If you move the portable folder, use **Update
startup path** when the app offers it.

## Start, Stop and Exit

**Start** launches the owned browser and opens the panel. **Stop** cancels capture and
closes only the resources MarsDisplay created. **Exit** waits for acknowledged cleanup
before releasing the single-instance lock, so two copies can never fight over the port.
If cleanup is uncertain the app says so and refuses a new Start instead of pretending.

## From source

Python 3.13 with the pinned dependencies:

```sh
pip install -e .
python -m playwright install chromium --only-shell
python -m mars_display
```

The test suite is headless Qt plus a loopback browser fixture; it never touches USB:

```sh
QT_QPA_PLATFORM=offscreen PLAYWRIGHT_BROWSERS_PATH=0 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Hardware and protocol notes, settings and recovery guarantees, runtime behaviour and
release engineering live in [`docs/`](docs).

## License

GPL-3.0-only. MarsDisplay is an independent project, not affiliated with the panel vendor.

<p align="center">
  <a href="https://github.com/Gentleman-Programming/gentle-ai">
    <img src="https://raw.githubusercontent.com/Gentleman-Programming/gentle-ai/main/docs/assets/brand/built-with-gentle-ai.png" alt="Built with Gentle-AI" width="280">
  </a>
</p>
