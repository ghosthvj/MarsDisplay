"""Pure frozen-DATA selection; never inspect or modify the installed SDK."""
import re


def select_runtime_data(entries):
    """Keep TOC tuples/order except known installer and root typing metadata.

    Apply to Analysis.datas, not merely initial collect_data_files results:
    pinned Playwright hooks also add DATA entries during Analysis.
    """
    prefix = 'playwright/driver/package/.local-browsers/'
    typing_markers = {'playwright/py.typed', 'pyside6/py.typed', 'shiboken6/py.typed',
                      'pil/py.typed', 'pyee/py.typed', 'greenlet/py.typed'}
    selected = []
    for entry in entries:
        destination = entry[0].replace('\\', '/')
        if entry[2] == 'DATA' and destination.casefold() in typing_markers:
            continue
        if entry[2] == 'DATA' and destination.startswith(prefix):
            relative = destination[len(prefix):]
            if (relative.startswith('.links/')
                    or re.fullmatch(r'[a-z][a-z0-9_]*-[0-9]+/(INSTALLATION_COMPLETE|DEPENDENCIES_VALIDATED)', relative)):
                continue
        selected.append(entry)
    return selected
