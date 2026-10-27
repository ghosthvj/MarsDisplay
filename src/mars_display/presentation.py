"""Scoped Qt Widgets theme; no persistence, application-wide style or I/O."""


def window_stylesheet(dark: bool) -> str:
    """Return a complete palette so switching back never inherits dark colors."""
    colors = ({
        "background": "#202b31", "foreground": "#eaf3f7", "muted": "#a4c0ce",
        "border": "#465f6b", "field": "#202b31", "panel": "#1b252b",
        "accent": "#70d3e0", "disabled": "#35444c", "subtle": "#243d45",
        "success": "#85d4b0", "success_background": "#234739",
        "warning": "#ffcf83", "error": "#ffb4ab",
    } if dark else {
        "background": "#ffffff", "foreground": "#163344", "muted": "#526f83",
        "border": "#ccdde3", "field": "#ffffff", "panel": "#f5f8f9",
        "accent": "#14798b", "disabled": "#e3eaee", "subtle": "#e9f4f6",
        "success": "#216e53", "success_background": "#e8f4ed",
        "warning": "#865b16", "error": "#a92e36",
    })
    return """
        QDialog#statusWindow, QDialog#previewWindow, QDialog#logsWindow, QWidget#body {
            background: %(background)s;
        }
        QWidget {
            color: %(foreground)s;
            font-family: "Segoe UI";
            font-size: 12px;
        }
        QLabel { background: transparent; }
        QLabel#muted, QLabel#hint { color: %(muted)s; }
        QLabel#windowHeading { font-size: 21px; font-weight: 700; }
        QLabel#sectionHeading, QLabel#frames { font-weight: 600; }
        QLabel#runtimeValue { font-size: 17px; font-weight: 700; }
        QPushButton {
            background: %(field)s;
            border: 1px solid %(border)s;
            border-radius: 7px;
            padding: 8px 14px;
        }
        QPushButton:hover { border-color: %(accent)s; }
        QPushButton:focus { border: 2px solid %(accent)s; }
        QPushButton:disabled {
            background: %(disabled)s;
            color: %(muted)s;
        }
        QPushButton#themeSwitch { color: %(accent)s; }
        QLineEdit {
            background: %(field)s;
            border: 1px solid %(border)s;
            border-radius: 4px;
            padding: 8px;
            selection-background-color: %(accent)s;
            selection-color: %(background)s;
        }
        QComboBox {
            background: %(field)s;
            color: %(foreground)s;
            border: 1px solid %(border)s;
            border-radius: 4px;
            padding: 8px;
        }
        QComboBox:disabled { color: %(muted)s; background: %(disabled)s; }
        QComboBox QAbstractItemView {
            background: %(field)s;
            color: %(foreground)s;
            border: 1px solid %(border)s;
            selection-background-color: %(accent)s;
            selection-color: %(field)s;
        }
        QLineEdit:focus { border: 1px solid %(accent)s; }
        QLineEdit[readOnly="true"] { background: %(panel)s; }
        QScrollArea { border: none; background: transparent; }
        QFrame#lifecycleCard {
            background: %(subtle)s;
            border: 1px solid %(border)s;
            border-radius: 8px;
        }
        QFrame#deviceCard {
            background: %(panel)s;
            border: 1px solid %(border)s;
            border-radius: 8px;
        }
        QFrame#footer {
            background: %(panel)s;
            border-top: 1px solid %(border)s;
        }
        QFrame#separator { background: %(border)s; border: none; }
        QLabel#sourceBadge {
            background: %(panel)s;
            border-radius: 4px;
            padding: 5px 8px;
        }
        QLabel[tone="success"] { color: %(success)s; }
        QLabel#sourceBadge[tone="success"] { background: %(success_background)s; }
        QLabel[tone="active"] { color: %(accent)s; }
        QLabel[tone="muted"] { color: %(muted)s; }
        QLabel[tone="warning"] { color: %(warning)s; }
        QLabel[tone="error"] { color: %(error)s; }
    """ % colors
