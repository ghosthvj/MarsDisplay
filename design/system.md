# MarsDisplay design baseline

Observed Qt styles, synchronized for settings mockups. Not a replacement theme.

## Colors
Source: `src/mars_display/presentation.py:6–18`.

| Role | Light | Dark |
|---|---|---|
| background | `#ffffff` | `#202b31` |
| foreground | `#163344` | `#eaf3f7` |
| muted | `#526f83` | `#a4c0ce` |
| border | `#ccdde3` | `#465f6b` |
| field | `#ffffff` | `#202b31` |
| panel | `#f5f8f9` | `#1b252b` |
| accent | `#14798b` | `#70d3e0` |
| disabled | `#e3eaee` | `#35444c` |
| subtle | `#e9f4f6` | `#243d45` |
| success | `#216e53` | `#85d4b0` |
| success_background | `#e8f4ed` | `#234739` |
| warning | `#865b16` | `#ffcf83` |
| error | `#a92e36` | `#ffb4ab` |

Brand icon: #218a9b (`src/mars_display/tray.py:78`).

## Typography
Source: `src/mars_display/presentation.py:23–32`.
Segoe UI, 12px base; title 21px/700; runtime 17px/700; section labels and frame count weight 600. HTML uses system-ui/sans-serif fallback. No source line-height or tracking token.

## Spacing and geometry
Source: `src/mars_display/tray.py:146–324`.
Window 650px wide, height min(760px, available height − 48px). Content margins 22/8/22/8px, vertical gap 3px. Lifecycle margins 14/6/14/6px; device margins 10/6/10/6px. Detail gaps 20px horizontal, 3px vertical. USB row gap 12px. Footer margins 22/8/22/8px, action gap 6px, extra 10px before Save. Slider width 320px; brand mark 22px; separator 1px.

## Components
Source: `src/mars_display/presentation.py:33–97`.
Buttons: field fill, 1px border, 7px radius, 8px 14px padding; accent hover, 2px accent focus. Inputs: field fill, 1px border, 4px radius, 8px padding; read-only panel fill. Disabled: disabled fill, muted text. Lifecycle: subtle fill; device: panel fill; both 8px radius. Footer: panel fill and top border. Source badge: panel or success_background, 4px radius, 5px 8px padding. No shadows.

## Mockup proposals, not existing Qt behavior
Only the observed palette and system font stack are used. Primary Save, 44px targets, stronger muted control borders, 1.5 line-height, 14px section spacing, responsive stacking and task navigation are proposed changes. HTML does not claim pixel-identical native Qt rendering. All state and save feedback is simulated: no network, hardware, storage or OS startup changes. Running freezes configuration; error offers retry or Stop to edit. Linux hides Windows login controls. Startup and running brightness are immediate actions, independent of Save. Preserve host-completion versus panel-acknowledgement distinction.
