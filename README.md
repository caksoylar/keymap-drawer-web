# keymap-drawer-web

This repo contains the source code for the Streamlit web app associated with
[`keymap-drawer`](https://github.com/caksoylar/keymap-drawer) hosted at
https://caksoylar.github.io/keymap-drawer.

To run locally, install the dependencies specified in `packages.txt` (via `apt` on Ubuntu),
then either `pip` install `streamlit` and `-r requirements.txt`, or follow the
[instructions](https://github.com/caksoylar/keymap-drawer#development) in the main repo
and `poetry install --with streamlit`.

After dependencies are installed, run with `streamlit run app.py`.
