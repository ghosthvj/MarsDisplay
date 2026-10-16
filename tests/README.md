# Isolated loopback browser fixtures

T8/S14 adds test-owned traffic attribution to the existing T7/S13 fixture.
It does not accept pending T3 capture source, change the capture implementation, or establish
retrospective provenance for historical unexpected `GET /` requests.

## Run the independent helper slice

```sh
.venv/bin/python -m unittest discover -s tests -p test_browser_fixture.py -v
```

`browser_fixture.py`, `test_browser_fixture.py` and this document require only
Python's standard library, not MarsDisplay, Qt, Playwright or the HTML fixture.
These three files form the standard-library test-only slice.
`test_browser_trace.py` adds a public Playwright/bundled-Chromium regression with
no application imports; it is also independent of unaccepted T3 source.
`test_browser.py` remains integration work beside that source.

## Public helper contract

- `BrowserFixture(case, html, before_response=None)` is a single-use context
  manager (or `start()` / `close()`). Each instance owns a fresh IPv4 loopback
  listener, OS-assigned port, generation, HTML, counts and trace. `html` is a
  lock-protected per-instance property; `url` and `port` exist after start.
- `own(session)` retains each distinct session, including replaced sessions.
  Cleanup closes them in reverse ownership order before stopping the listener,
  interrupting socket reads and joining every non-daemon fixture thread.
  Session `close()` must be synchronous and bounded by its implementation.
  A cleanup error is reported, never disguised as successful disposal.
- `request_headers` returns a fresh dictionary containing an opaque, unique
  per-instance `X-MarsDisplay-Test-Case` marker. Explicit fixture HTTP clients
  merge it with their own headers. It is test attribution, not authentication
  or evidence of a client PID; neither paths nor User-Agent imply ownership.
- `snapshot()` atomically returns frozen counts/events and resource state.
  `counts` still includes every parsed GET, including unsolicited `/` traffic.
  `owned_counts` contains exact matching-marker traffic on **every** path;
  `foreign_counts` contains missing, wrong and other-fixture markers. Per path,
  raw `counts == owned_counts + foreign_counts`. There is no reset, suppression
  or request-filter API. Unexpected owned `/` requests still fail exact counts.
  The disabled endpoint returns HTTP 302 with `Location: /`; all other GET paths
  serve current HTML.
- `before_response(fixture, path)` runs after recording/counting a request.
  This internal test seam must use bounded Event waits and honor `stopping`;
  it must not wait indefinitely. Tests use it to hold an old handler while a
  new case serves requests, and to release a handler during exceptional cleanup.
- Socket reads time out after 0.5 seconds, listener polling uses 0.01 seconds,
  and handler joins share a 1.5-second deadline. No sleeps, retries or daemon
  abandonment substitute for cleanup. A deadline violation fails cleanup.

## Read provenance without overclaiming

HTTP handler start/end events carry case/generation, lock-ordered monotonic
timestamps, request ID, method/path, peer host/port, immutable header pairs and
explicit `ownership` (`owned` or `foreign`). Counters and handler-start events
are updated under the same lock; every raw request remains observable.
Completion events also report status or exception type. A snapshot is stable
even while another handler is active; use it as assertion diagnostics.

`instrument(Page, Route)` temporarily wraps test-supplied API classes. On first
`goto`, it installs a page-scoped last-added fallback route that merges the test
marker with original request headers, preserving pre-existing routing. Scoped
`Route.fetch` and `Route.continue_` wrappers use the same default-only tagging
when forwarding explicit header overrides, preserving methods, options and
redirect limits. Existing identities are preserved case-insensitively, including
wrong or other-case markers: these remain foreign at the receiving fixture.
A default identity is added only when absent. Differently-cased duplicate marker
keys collapse to the last caller override without changing unrelated headers.
Only pages navigated in the scope are tagged; app source, global environment,
page/context extra-header settings and unrelated clients are untouched.

It adds Page request, response and frame-navigation listeners on first `goto`. Listeners
remain attached through later requests, reads, viewport changes and transitions;
subsequent `goto` calls update the page's navigation ID without double attachment.
Navigation IDs correlate these API observations with `Route.fetch` begin/end,
including redirect status/location. Request metadata is cached when first seen
through public properties, avoiding teardown-time queries of dead resources.
Results and exceptions are preserved. Forwarded headers differ only by the
reserved test marker; all unrelated header values/options are preserved.
Page request/response and route-fetch events are marked `owned` as controlled
API observations, even if the Page event precedes route tagging. Socket events
independently classify the marker actually received, not cached API metadata.

Explicit listener ownership wraps each observed page/context/browser's public
`close` method for the instrumentation scope. Listeners detach before the owner
closes its live connection, including after setup or capture errors. The tagging
route is removed without disturbing existing routes. Scope exit also detaches
remaining listeners and restores all wrapped methods, even on
exceptions. Owned sessions must close their browser before stopping its driver;
direct driver termination without owner cleanup is not the supported lifecycle.
Socket requests always count without filtering. This is scoped test
instrumentation, not a change to capture code.

Socket events deliberately say **client process unknown**. API events identify
an observed API operation, not the process that opened a socket. Time, URL and
headers can aid comparison but do not create a proven socket-to-API link:
`Route.fetch` forwards intercepted headers, so User-Agent and Sec-Fetch do not
establish client PID or browser-process identity.

## Browser integration verification

With already-installed bundled Chromium and Qt dependencies:

```sh
export QT_QPA_PLATFORM=offscreen PLAYWRIGHT_BROWSERS_PATH=0 PYTHONPATH=src:tests
.venv/bin/python -m unittest discover -s tests -p test_browser_trace.py -v
.venv/bin/python -m unittest discover -s tests -p test_browser.py -v
.venv/bin/python -m unittest discover -s tests -v
```

The public trace regression injects a known foreign `GET /`, navigates through
`Route.fetch`, changes viewport, awaits a browser `fetch('/')` and screenshots.
Exact owned counts stay `/display: 1, /: 1` despite foreign traffic; a second
owned `/` must change them to `/display: 1, /: 2`. It reconciles all raw counts
against all handler-start events and both partitions, checks late Page events,
and verifies custom page/context/route headers and options. After scope exit,
existing routes/listeners/headers still work and a new fetch is foreign.
Cleanup leaves zero fixture resources. Failures include full immutable snapshots;
no unknown request is silently discarded.

All ten original scenarios remain: both geometries/colors, persistent capture
without per-frame navigation, metadata/error/login/freshness checks, font/layout
readiness, transitions, redirect prohibition and owned-browser cleanup. Strict
owned request counts still include the extra reads and browser close. Raw and
foreign observations remain visible in failure diagnostics. Fresh fixture
identity prevents delayed old-case traffic from being attributed to a new case;
it does not prove the historical extra root request's origin or fix production.
