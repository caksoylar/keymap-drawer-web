"""Simple streamlit app for interactive parsing and drawing."""

from importlib.metadata import version
from urllib.error import HTTPError
from typing import Any

import yaml
from code_editor import code_editor  # type: ignore

import streamlit as st
from streamlit import session_state as state

from .utils import (
    dump_config,
    handle_exception,
    decode_permalink_param,
    get_about,
    get_default_config,
    get_example_yamls,
    get_permalink,
    parse_zmk_url_to_yaml,
    svg_to_png,
)
from .kd_interface import (
    read_keymap_yaml,
    draw,
    parse_config,
    parse_qmk_to_yaml,
    parse_zmk_to_yaml,
)
from .constants import REPO_REF


EDITOR_BUTTONS = [
    {
        "name": "Settings",
        "feather": "Settings",
        "alwaysOn": True,
        "commands": ["showSettingsMenu"],
        "style": {"top": "0rem", "right": "0.4rem"},
    },
    {
        "name": "Shortcuts",
        "feather": "Type",
        "class": "shortcuts-button",
        "hasText": True,
        "commands": ["toggleKeyboardShortcuts"],
        "style": {"top": "10.0rem", "right": "0.4rem"},
    },
    {
        "name": "Run",
        "feather": "Play",
        "primary": True,
        "hasText": True,
        "alwaysOn": True,
        "showWithIcon": True,
        "commands": ["submit"],
        "style": {"bottom": "0.44rem", "right": "0.4rem", "background-color": "#80808050"},
    },
]


@st.dialog("About this tool", width="large")
def display_about():
    """Display a dialog about the app."""
    st.write(get_about())
    if st.button("Close"):
        st.rerun()


def setup_page():
    """Set page config and style, show header row, set up initial state."""
    st.set_page_config(page_title="Keymap Drawer live demo", page_icon=":keyboard:", layout="wide")
    st.html('<style>textarea[class^="st-"] { font-family: monospace; font-size: 14px; }</style>')

    c1, c2 = st.columns(2, vertical_alignment="center", gap="medium")
    c1.html(
        '<h1 align="center"><img alt="keymap-drawer logo" src="https://caksoylar.github.io/keymap-drawer/logo.svg"></h1>'
    )
    c2.subheader("A visualizer for keyboard keymaps", anchor=False)
    c2.caption(
        "Check out the documentation and Python CLI tool in the "
        "[GitHub repo](https://github.com/caksoylar/keymap-drawer)!"
    )
    c2.caption(
        f"`keymap-drawer` version: [{REPO_REF}](https://github.com/caksoylar/keymap-drawer/releases/tag/{REPO_REF})"
    )
    if c2.button("What is this tool?"):
        display_about()

    examples = get_example_yamls()
    if "kd_config" not in state:
        state.kd_config = get_default_config()
    if "keymap_yaml" not in state:
        state.keymap_yaml = examples[list(examples)[0]]
    if "code_id" not in state:
        state.code_id = ""

    if state.get("user_query", True):
        if query_yaml := st.query_params.get("keymap_yaml"):
            state.keymap_yaml = decode_permalink_param(query_yaml)
            st.query_params.clear()
        state.example_yaml = st.query_params.get("example_yaml", list(examples)[0])
        state.qmk_cols = int(st.query_params.get("num_cols", "0"))
        state.zmk_cols = int(st.query_params.get("num_cols", "0"))
        state.zmk_url = st.query_params.get("zmk_url", "")

    return examples


def examples_parse_row(examples):
    """Show column with examples and parsing boxes, in order to set up initial keymap."""
    st.subheader(
        "Quick start",
        help="Use one of the options below to generate an initial keymap YAML that you can start editing.",
        anchor=False,
    )
    col_ex, col_qmk, col_zmk = st.columns(3, gap="medium")
    error_placeholder = st.empty()
    with col_ex:
        with st.popover("Example keymaps", use_container_width=True):
            with st.form("example_form", border=False):
                st.selectbox(label="Load example", options=list(examples), index=0, key="example_yaml")
                example_submitted = st.form_submit_button(label="Show!", use_container_width=True)
                if example_submitted or state.get("user_query", True) and "example_yaml" in st.query_params:
                    if example_submitted:
                        st.query_params.clear()
                        st.query_params.example_yaml = state.example_yaml
                    state.keymap_yaml = examples[state.example_yaml]
    with col_qmk:
        with st.popover("Parse from QMK keymap", use_container_width=True):
            with st.form("qmk_form", border=False):
                num_cols = st.number_input(
                    "Number of columns in keymap (optional)", min_value=0, max_value=20, key="qmk_cols"
                )
                qmk_file = st.file_uploader(label="Import QMK `keymap.json`", type=["json"])
                qmk_submitted = st.form_submit_button(label="Parse!", use_container_width=True)
                if qmk_submitted:
                    if not qmk_file:
                        st.error(icon="❗", body="Please upload a keymap file")
                    else:
                        try:
                            state.keymap_yaml = parse_qmk_to_yaml(
                                qmk_file, parse_config(state.kd_config).parse_config, num_cols
                            )
                        except Exception as err:
                            handle_exception(error_placeholder, "Error while parsing QMK keymap", err)
    with col_zmk:
        with st.popover("Parse from ZMK keymap", use_container_width=True):
            with st.form("zmk_form", border=False):
                num_cols = st.number_input(
                    "Number of columns in keymap (optional)", min_value=0, max_value=20, key="zmk_cols"
                )
                zmk_file = st.file_uploader(label="Import a ZMK `<keyboard>.keymap` file", type=["keymap"])
                zmk_file_submitted = st.form_submit_button(label="Parse from file!", use_container_width=True)
                if zmk_file_submitted:
                    if not zmk_file:
                        st.error(icon="❗", body="Please upload a keymap file")
                    else:
                        try:
                            state.keymap_yaml = parse_zmk_to_yaml(
                                zmk_file,
                                parse_config(state.kd_config).parse_config,
                                num_cols,
                                st.query_params.get("layout", ""),
                            )
                        except Exception as err:
                            handle_exception(error_placeholder, "Error while parsing ZMK keymap", err)

                st.text_input(
                    label="or, input GitHub URL to keymap",
                    placeholder="https://github.com/caksoylar/zmk-config/blob/main/config/hypergolic.keymap",
                    key="zmk_url",
                )
                zmk_url_submitted = st.form_submit_button(label="Parse from URL!", use_container_width=True)
                if zmk_url_submitted or state.get("user_query", True) and "zmk_url" in st.query_params:
                    if zmk_url_submitted:
                        st.query_params.clear()
                        st.query_params.zmk_url = state.zmk_url
                    if not state.zmk_url:
                        st.error(icon="❗", body="Please enter a URL")
                    else:
                        try:
                            state.keymap_yaml = parse_zmk_url_to_yaml(
                                state.zmk_url,
                                parse_config(state.kd_config).parse_config,
                                num_cols,
                                st.query_params.get("layout", ""),
                            )
                        except HTTPError as err:
                            handle_exception(
                                error_placeholder,
                                "Could not get repo contents, make sure you use a branch name"
                                " or commit SHA and not a tag in the URL",
                                err,
                            )
                        except Exception as err:
                            handle_exception(error_placeholder, "Error while parsing ZMK keymap from URL", err)

                st.caption("Please check and if necessary correct the `layout` field after parsing")


def keymap_draw_row(need_rerun: bool):
    """Show the main row with keymap YAML and visualization columns."""
    keymap_col, draw_col = st.columns(2, gap="medium")
    with keymap_col:
        c1, c2 = st.columns([0.75, 0.25], vertical_alignment="bottom")
        c1.subheader(
            "Keymap YAML",
            help=(
                "This is a representation of your keymap to be visualized. Edit below (following the linked keymap "
                'spec) and press "Run" (or press Ctrl+Enter) to update the visualization!'
            ),
            anchor=False,
        )
        c2.link_button(
            label="Keymap Spec :material/open_in_new:",
            url=f"https://github.com/caksoylar/keymap-drawer/blob/{REPO_REF}/KEYMAP_SPEC.md",
            use_container_width=True,
        )
        response_dict = code_editor(
            code=state.keymap_yaml,
            lang="yaml",
            height="800px",
            allow_reset=True,
            buttons=EDITOR_BUTTONS,
            key="keymap_editor",
            options={"wrap": True, "tabSize": 2},
            response_mode=["default", "blur"],
        )
        if response_dict["type"] in ("submit", "blur") and response_dict["id"] != state.code_id:
            state.keymap_yaml = response_dict["text"]
            state.code_id = response_dict["id"]
            need_rerun = True

        st.download_button(label="Download keymap", data=state.keymap_yaml, file_name="my_keymap.yaml")
        permabutton = st.button(label="Get permalink to keymap")
        if permabutton:
            st.code(get_permalink(state.keymap_yaml), language=None)

    with draw_col:
        try:
            cfg = parse_config(state.kd_config)
            draw_cfg = cfg.draw_config
            keymap_data = read_keymap_yaml(state.keymap_yaml)
            layer_names = list(keymap_data["layers"])

            draw_opts: dict[str, Any] = {}

            header_col, layout_col, opts_col = st.columns([0.55, 0.25, 0.2], vertical_alignment="bottom")
            with header_col:
                st.subheader(
                    "Keymap visualization",
                    help="This is the visualization of your keymap YAML from the left column, "
                    'using the settings in the "Configuration" dialog. '
                    'Iterate on the YAML until you are happy with it, then use the "Export" dialog below.',
                    anchor=False,
                )
            with layout_col:
                active_icon = ":warning: " if state.get("qmk_layout_file") else ""
                with st.popover(active_icon + "Layout override", use_container_width=True):
                    st.write(
                        "You can override the physical layout spec description in Keymap YAML with a custom layout "
                        "description file here, similar to `qmk_info_json` or `dts_layout` options mentioned in the "
                        "[docs](https://github.com/caksoylar/keymap-drawer/blob/main/KEYMAP_SPEC.md#layout)."
                    )
                    st.caption("Note: If there are multiple layouts in the file, the first one will be used.")
                    st.file_uploader(
                        label="QMK `info.json` or ZMK devicetree format layout description",
                        type=["json", "dtsi", "overlay", "dts"],
                        key="qmk_layout_file",
                    )
            with opts_col:
                with st.popover("Draw filters", use_container_width=True):
                    draw_opts["draw_layers"] = st.segmented_control(
                        "Layers to show", options=layer_names, selection_mode="multi", default=layer_names
                    )
                    draw_opts["keys_only"] = st.checkbox("Show only keys")
                    draw_opts["combos_only"] = st.checkbox("Show only combos")
                    try:
                        draw_opts["ghost_keys"] = [
                            int(v)
                            for v in st.text_input(
                                "`ghost` keys",
                                help="Space-separated zero-based key position indices to add `type: ghost`",
                            ).split()
                        ]
                    except ValueError as err:
                        handle_exception(st, "Values must be space-separated integers", err)

            layout_override = None
            if override_file := state.get("qmk_layout_file"):
                override_file.name
                layout_override = {"qmk_info_json" if override_file.name.endswith(".json") else "dts_layout": state.qmk_layout_file}

            svg = draw(keymap_data, cfg, layout_override, **draw_opts)

            st.image(svg)

            with st.expander("Export", icon=":material/ios_share:"):
                svg_col, png_col = st.columns(2)
                with svg_col:
                    st.subheader("SVG", anchor=False)
                    bg_override = st.checkbox("Override background", value=False)
                    bg_color = st.color_picker("SVG background color", disabled=not bg_override, value="#FFF")
                    if bg_override:
                        draw_cfg = draw_cfg.copy(
                            update={
                                "svg_extra_style": draw_cfg.svg_extra_style
                                + f"\nsvg.keymap {{ background-color: {bg_color}; }}"
                            }
                        )
                        export_svg = draw(keymap_data, cfg, layout_override, **draw_opts)
                    else:
                        export_svg = svg
                    st.download_button(label="Download", data=export_svg, file_name="my_keymap.svg")

                with png_col:
                    st.subheader("PNG", anchor=False)
                    st.caption(
                        "Note: Export might not render emojis and unicode characters as well as your browser, "
                        "uses a fixed text font and does not support auto dark mode"
                    )
                    bg_color = st.color_picker("PNG background color", value="#FFF")
                    st.download_button(label="Export", data=svg_to_png(svg, bg_color), file_name="my_keymap.png")

        except yaml.YAMLError as err:
            handle_exception(st, "Could not parse keymap YAML, please check for syntax errors", err)
        except Exception as err:
            handle_exception(st, "Error while drawing SVG from keymap YAML", err)
    return need_rerun


def configuration_row(need_rerun: bool):
    """Show configuration row with common and raw configuration columns."""
    with st.expander("Configuration", expanded=True, icon=":material/manufacturing:"):
        common_col, raw_col = st.columns(2, gap="medium")
        with common_col:
            st.subheader("Common configuration options", anchor=False)
            try:
                cfg = parse_config(state.kd_config)
            except Exception:
                cfg = parse_config(get_default_config())
            draw_cfg = cfg.draw_config
            cfgs: dict[str, Any] = {}
            with st.form("common_config"):
                c1, c2 = st.columns(2)
                with c1:
                    cfgs["key_w"] = st.number_input(
                        "`key_w`",
                        help="Key width, only used for ortho layouts (not QMK)",
                        min_value=1,
                        max_value=999,
                        step=1,
                        value=int(draw_cfg.key_w),
                    )
                with c2:
                    cfgs["key_h"] = st.number_input(
                        "`key_h`",
                        help="Key height, used for width as well for QMK layouts",
                        min_value=1,
                        max_value=999,
                        step=1,
                        value=int(draw_cfg.key_h),
                    )
                c1, c2 = st.columns(2)
                with c1:
                    cfgs["combo_w"] = st.number_input(
                        "`combo_w`",
                        help="Combo box width",
                        min_value=1,
                        max_value=999,
                        step=1,
                        value=int(draw_cfg.combo_w),
                    )
                with c2:
                    cfgs["combo_h"] = st.number_input(
                        "`combo_h`",
                        help="Combo box height",
                        min_value=1,
                        max_value=999,
                        step=1,
                        value=int(draw_cfg.combo_h),
                    )
                cfgs["n_columns"] = st.number_input(
                    "`n_columns`",
                    help="Number of layer columns in the output drawing",
                    min_value=1,
                    max_value=99,
                    value=draw_cfg.n_columns,
                )
                c1, c2 = st.columns(2, vertical_alignment="bottom")
                cfgs["draw_key_sides"] = c1.toggle(
                    "`draw_key_sides`", help="Draw key sides, like keycaps", value=draw_cfg.draw_key_sides
                )
                if "dark_mode" in draw_cfg.model_fields:
                    dark_mode_options = {"Auto": "auto", "Off": False, "On": True}
                    cfgs["dark_mode"] = dark_mode_options[
                        c2.radio(
                            "`dark_mode`",
                            options=list(dark_mode_options),
                            help='Turn on dark mode, "auto" adapts it to the web page or OS light/dark setting',
                            horizontal=True,
                            index=list(dark_mode_options.values()).index(draw_cfg.dark_mode),
                        )  # type: ignore
                    ]
                c1, c2 = st.columns(2, vertical_alignment="bottom")
                with c1:
                    cfgs["separate_combo_diagrams"] = st.toggle(
                        "`separate_combo_diagrams`",
                        help="Draw combos with mini diagrams rather than on layers",
                        value=draw_cfg.separate_combo_diagrams,
                    )
                with c2:
                    cfgs["combo_diagrams_scale"] = st.number_input(
                        "`combo_diagrams_scale`",
                        help="Scale factor for mini combo diagrams if `separate_combo_diagrams` is set",
                        value=draw_cfg.combo_diagrams_scale,
                    )
                cfgs["svg_extra_style"] = st.text_area(
                    "`svg_extra_style`",
                    help="Extra CSS that will be appended to the default `svg_style`",
                    value=draw_cfg.svg_extra_style,
                )
                if "footer_text" in draw_cfg.model_fields:
                    cfgs["footer_text"] = st.text_input(
                        "`footer_text`",
                        help="Footer text that will be inserted at the bottom of the drawing",
                        value=draw_cfg.footer_text,
                    )

                common_config_button = st.form_submit_button("Update config")
                if common_config_button:
                    cfg.draw_config = draw_cfg.copy(update=cfgs)
                    state.kd_config = dump_config(cfg)
                    need_rerun = True

        with raw_col:
            c1, c2 = st.columns([0.75, 0.25], gap="medium")
            c1.subheader("Raw configuration", anchor=False)
            c2.link_button(
                label="Config params :material/open_in_new:",
                url=f"https://github.com/caksoylar/keymap-drawer/blob/{REPO_REF}/CONFIGURATION.md",
                use_container_width=True,
            )
            st.text_area(label="Raw config", key="kd_config", height=700, label_visibility="collapsed")
            st.download_button(label="Download config", data=state.kd_config, file_name="my_config.yaml")
    return need_rerun


def main():
    """Lay out Streamlit elements and widgets, run parsing and drawing logic."""
    need_rerun = False

    examples = setup_page()
    examples_parse_row(examples)
    need_rerun = keymap_draw_row(need_rerun)
    need_rerun = configuration_row(need_rerun)

    state.user_query = False
    if need_rerun:  # rerun if keymap editor needs to be explicitly refreshed or config updates need to be propagated
        st.rerun()
