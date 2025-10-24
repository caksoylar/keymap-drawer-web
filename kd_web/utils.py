"""Helper module containing utils for streamlit app."""

import base64
import fnmatch
import gzip
import io
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError
from urllib.parse import quote_from_bytes, unquote_to_bytes, urlsplit
from urllib.request import urlopen

import yaml
from cairosvg import svg2png  # type: ignore
from lxml import etree  # type: ignore
from west.app.main import main as west_main
from keymap_drawer.config import Config, ParseConfig

import streamlit as st

from .kd_interface import parse_zmk_to_yaml
from .constants import APP_URL, REPO_REF


class PathyBytesIO(io.BytesIO):
    """A BytesIO variant which can include a file path as attribute and can be read multiple times."""

    path: Path

    def read(self, *args, **kwargs):
        self.seek(0)
        return super().read(*args, **kwargs)

    def close(self):
        pass


@st.cache_data
def get_about() -> str:
    """Read about text and return it as a string."""
    with open(Path(__file__).parent.parent / "resources" / "about.md", "r", encoding="utf-8") as f:
        return f.read()


@st.cache_data(max_entries=16)
def svg_to_png(svg_string: str, background_color: str, scale: float = 1.0) -> bytes:
    """
    Convert SVG string in SVG/XML format to PNG using cairosvg, removing the unsupported stroke style for layer headers.
    """
    # remove outline from layer headers and footer, they cause rendering issues
    input_svg = re.sub("</style>", "text.label, text.footer { stroke: none; }</style>", svg_string)

    # force text font to DejaVu Sans Mono, since cairosvg does not properly use font-family attribute
    input_svg = input_svg.replace("font-family: ", "font-family: DejaVu Sans Mono,")

    root = etree.XML(input_svg)

    # remove relative font size specifiers since cairosvg can't handle them
    for node in root.xpath(  # type: ignore
        r"//*[re:match(@style, 'font-size: \d+(\.\d+)?%')]", namespaces={"re": "http://exslt.org/regular-expressions"}
    ):
        del node.attrib["style"]  # type: ignore

    # remove links, e.g. from the footer text
    if text_nodes := root.xpath('/*[name()="svg"]/*[name()="text"]'):
        etree.strip_tags(text_nodes[-1], "{http://www.w3.org/2000/svg}a")  # type: ignore

    return svg2png(bytestring=etree.tostring(root, encoding="utf-8"), background_color=background_color, scale=scale)


@st.cache_data
def get_example_yamls() -> dict[str, str]:
    """Return mapping of example keymap YAML names to contents."""
    repo_zip = _download_zip("caksoylar", "keymap-drawer", REPO_REF)
    with zipfile.ZipFile(io.BytesIO(repo_zip)) as zipped:
        files = zipped.namelist()
        example_paths = sorted([Path(path) for path in files if fnmatch.fnmatch(path, "*/examples/*.yaml")])
        if not example_paths:
            raise RuntimeError("Retrying examples failed, please refresh the page :(")
        return {path.name: zipped.read(path.as_posix()).decode("utf-8") for path in example_paths}


def dump_config(cfg: Config) -> str:
    """Convert config to yaml representation."""

    def cfg_str_representer(dumper, in_str):
        if "\n" in in_str:  # use '|' style for multiline strings
            return dumper.represent_scalar("tag:yaml.org,2002:str", in_str, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", in_str)

    yaml.representer.SafeRepresenter.add_representer(str, cfg_str_representer)
    return yaml.safe_dump(cfg.dict(), sort_keys=False, allow_unicode=True)


@st.cache_data
def get_default_config() -> str:
    """Get and dump default config."""
    with open(Path(__file__).parent.parent / "resources" / "default_config.yaml", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)

    return dump_config(Config(**config_dict))


def _get_zmk_ref(owner: str, repo: str, head: str) -> str:
    try:
        with urlopen(f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{head}") as resp:
            sha = json.load(resp)["object"]["sha"]
    except HTTPError:
        # assume we are provided with a reference directly, like a commit SHA
        sha = head
    return sha


@st.cache_data(ttl=1800, max_entries=64)
def _download_zip(owner: str, repo: str, sha: str) -> bytes:
    """Use `sha` only used for caching purposes to make sure we are fetching from the same repo state."""
    zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{sha}"
    with urlopen(zip_url) as f:
        return f.read()


def _extract_zip_and_parse(
    zip_bytes: bytes, keymap_path: PurePosixPath, config: ParseConfig, num_cols: int, layout: str
) -> tuple[str, str, PathyBytesIO | None]:
    log = []
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zipped:
            zipped.extractall(tmpdir)

        repo_path = next((path for path in Path(tmpdir).iterdir() if path.is_dir()), None)
        assert repo_path is not None

        keyboard_name = keymap_path.stem

        keymap_file = repo_path / keymap_path
        if not keymap_file.exists():
            raise ValueError(f"Could not find '{keymap_path}' in the repo, please check URL")

        config_manifest = repo_path / "config" / "west.yml"
        if config_manifest.exists():
            st.toast("Found config/west.yml, fetching modules")
            subprocess.run(
                ["west", "init", "--local", str(config_manifest.parent)],
                capture_output=True,
                check=False,
                cwd=repo_path,
            )
            subprocess.run(
                ["west", "config", "--local", "manifest.project-filter", " -zmk,-zephyr"], check=False, cwd=repo_path
            )
            out = subprocess.run(
                ["west", "update", "--fetch-opt=--filter=tree:0"],
                capture_output=True,
                text=True,
                check=False,
                cwd=repo_path,
            )
            if out.stderr:
                log.append(out.stderr)
            if include_paths := list(repo_path.glob("**/include/")):
                for path in include_paths:
                    st.toast(
                        f"Found include folder at {path.relative_to(repo_path)}, adding it to zmk_additional_includes"
                    )
                    config.zmk_additional_includes.append(str(path))

        override_buffer = None
        if json_path := next(repo_path.glob(f"**/{keyboard_name}.json"), None):
            st.toast(f"Found physical layout at {json_path.relative_to(repo_path)}, setting Layout Override")
            with open(json_path, "rb") as f:
                override_buffer = PathyBytesIO(f.read())
            override_buffer.path = json_path.relative_to(repo_path)
        elif dts_path := next(repo_path.glob(f"**/{keyboard_name}-layout*.dtsi"), None):
            st.toast(f"Found physical layout at {dts_path.relative_to(repo_path)}, setting Layout Override")
            with open(dts_path, "rb") as f:
                override_buffer = PathyBytesIO(f.read())
            override_buffer.path = dts_path.relative_to(repo_path)

        keymap, parse_log = parse_zmk_to_yaml(keymap_file, config, num_cols, layout)
        log.append(parse_log)
        return keymap, "\n".join(log), override_buffer


def parse_zmk_url_to_yaml(
    zmk_url: str, config: ParseConfig, num_cols: int, layout: str
) -> tuple[str, str, PathyBytesIO | None]:
    """
    Parse a given ZMK keymap URL on Github into keymap YAML. Normalize URL, extract owner/repo/head name,
    get reference (not cached), download contents from reference (cached) and parse keymap (cached).
    """
    if not zmk_url.startswith("https") and not zmk_url.startswith("//"):
        zmk_url = "//" + zmk_url
    split_url = urlsplit(zmk_url, scheme="https")
    path = PurePosixPath(split_url.path)
    assert split_url.netloc.lower() == "github.com", "Please provide a Github URL"
    assert path.parts[3] == "blob", "Please provide URL for a file"
    assert path.parts[-1].endswith(".keymap"), "Please provide URL to a .keymap file"

    owner, repo, head = path.parts[1], path.parts[2], path.parts[4]
    keymap_path = PurePosixPath(*path.parts[5:])

    sha = _get_zmk_ref(owner, repo, head)
    zip_bytes = _download_zip(owner, repo, sha)
    return _extract_zip_and_parse(zip_bytes, keymap_path, config, num_cols, layout)


def get_permalink(keymap_yaml: str) -> str:
    """Encode a keymap using a compressed base64 string and place it in query params to create a permalink."""
    b64_bytes = base64.b64encode(gzip.compress(keymap_yaml.encode("utf-8"), mtime=0), altchars=b"-_")
    return f"{APP_URL}?keymap_yaml={quote_from_bytes(b64_bytes)}"


def decode_permalink_param(param: str) -> str:
    """Get a compressed base64 string from query params and decode it to keymap YAML."""
    return gzip.decompress(base64.b64decode(unquote_to_bytes(param), altchars=b"-_")).decode("utf-8")


def handle_exception(container, message: str, exc: Exception):
    """Display exception in given container."""
    exc_str = str(exc).replace("\n", "  \n")
    body = message + "\n\n" + f"**{type(exc).__name__}**: {exc_str}"
    container.error(icon="❗", body=body)
