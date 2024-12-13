"""Helper module containing functions that interface with keymap-drawer."""

import io
import json
from pathlib import Path

import timeout_decorator  # type: ignore
import yaml

from keymap_drawer.config import Config, ParseConfig
from keymap_drawer.draw import KeymapDrawer
from keymap_drawer.parse import QmkJsonParser, ZmkKeymapParser

import streamlit as st

from .constants import DRAW_TIMEOUT, PARSE_TIMEOUT, LAYOUT_PREAMBLE


@timeout_decorator.timeout(DRAW_TIMEOUT, use_signals=False)
def read_keymap_yaml(yaml_str: str) -> dict:
    """Read yaml into dict and assert certain elements are in it."""
    assert yaml_str, "Keymap YAML is empty, nothing to draw"
    yaml_data = yaml.safe_load(yaml_str)
    assert "layers" in yaml_data, 'Keymap needs to be specified via the "layers" field in keymap YAML'
    return yaml_data


@timeout_decorator.timeout(DRAW_TIMEOUT, use_signals=False)
def draw(keymap_data: dict, config: Config, layout_override: dict | None = None, **draw_args) -> str:
    """Given a YAML keymap string, draw the keymap in SVG format to a string."""

    if custom_config := keymap_data.get("draw_config"):
        config.draw_config = config.draw_config.model_copy(update=custom_config)

    with io.StringIO() as out:
        drawer = KeymapDrawer(
            config=config,
            out=out,
            layers=keymap_data["layers"],
            layout=layout_override if layout_override is not None else keymap_data["layout"],
            combos=keymap_data.get("combos", []),
        )
        drawer.print_board(**draw_args)
        return out.getvalue()


@st.cache_data(max_entries=16)
def parse_config(config: str) -> Config:
    """Parse config from YAML format."""
    return Config.parse_obj(yaml.safe_load(config))


@timeout_decorator.timeout(PARSE_TIMEOUT, use_signals=False)
def parse_qmk_to_yaml(qmk_keymap_buf: io.BytesIO, config: ParseConfig, num_cols: int) -> str:
    """Parse a given QMK keymap JSON (buffer) into keymap YAML."""
    parsed = QmkJsonParser(config, num_cols).parse(io.TextIOWrapper(qmk_keymap_buf, encoding="utf-8"))
    return yaml.safe_dump(parsed, width=160, sort_keys=False, default_flow_style=None, allow_unicode=True)


@timeout_decorator.timeout(PARSE_TIMEOUT, use_signals=False)
def parse_zmk_to_yaml(zmk_keymap: Path | io.BytesIO, config: ParseConfig, num_cols: int, layout: str) -> str:
    """Parse a given ZMK keymap file (file path or buffer) into keymap YAML."""
    with (
        open(zmk_keymap, encoding="utf-8")
        if isinstance(zmk_keymap, Path)
        else io.TextIOWrapper(zmk_keymap, encoding="utf-8")
    ) as keymap_buf:
        parsed = ZmkKeymapParser(config, num_cols).parse(keymap_buf)
    if layout:  # assign or override layout field if provided in app
        parsed["layout"] = json.loads(layout)  # pylint: disable=unsupported-assignment-operation

    out = yaml.safe_dump(parsed, width=160, sort_keys=False, default_flow_style=None, allow_unicode=True)
    if "layout" not in parsed:  # pylint: disable=unsupported-membership-test
        return LAYOUT_PREAMBLE + out
    return out
