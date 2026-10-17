"""Pure Windows plugin-root policy for the app's raster Widgets UI."""


def select_plugin_roots(family, entries):
    """Keep stock-validated (source, destination) tuples except four roots.

    Select roots before native dependency closure, not dependent Qt libraries
    afterwards. Never inspect SDK files or alter kept tuples/order.
    """
    optional = {'imageformats': {'qpdf.dll', 'qsvg.dll'},
                'iconengines': {'qsvgicon.dll'},
                'platforminputcontexts': {'qtvirtualkeyboardplugin.dll'}}
    excluded = optional.get(family.replace('\\', '/').casefold(), ())
    return [entry for entry in entries
            if str(entry[0]).replace('\\', '/').rsplit('/', 1)[-1].casefold() not in excluded]
