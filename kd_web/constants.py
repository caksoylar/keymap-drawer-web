"""Constants used for the web app."""

from importlib.metadata import version

APP_URL = "https://caksoylar.github.io/keymap-drawer"
REPO_REF = "dev"

DRAW_TIMEOUT = 10
PARSE_TIMEOUT = 30

LAYOUT_PREAMBLE = """\
# FILL IN below field with a value like {qmk_keyboard: ferris/sweep}
# or {ortho_layout: {split: true, rows: 3, columns: 5, thumbs: 2}}
# see https://github.com/caksoylar/keymap-drawer/blob/main/KEYMAP_SPEC.md#layout
#layout:
"""
