## Why?

Custom keymaps are typically used with programmable keyboards, which run firmware such as [QMK](https://qmk.fm) or [ZMK](https://zmk.dev).
Such custom keymaps can contain many "layers" of different key mappings, or use other advanced features such as "combos" that activate when
multiple keys are pressed at the same time, or dual purpose keys like hold-taps that have different functions depending on how long they are pressed.

As a result of above flexibility, keymaps can be complex and it can be useful to have a visual and abstracted representation of such keymaps.
This is a web app that helps you create such a visualization/diagram/drawing which you can use as a reference for yourself, or to share it with others.

## How?

- **Keymap YAML** column contains the abstracted representation of a keymap, in [YAML format](https://en.wikipedia.org/wiki/YAML)
  with certain fields as described in the [spec](https://github.com/caksoylar/keymap-drawer/blob/main/KEYMAP_SPEC.md).
  You can edit it in the editor window, then update the visualization by clicking the "Run" button or using the Ctrl+Enter shortcut.
- **Quick start** sidebar gives you multiple options to bootstrap the keymap YAML -- you can load an existing example, or
  parse QMK and ZMK keymap files.
- **Keymap visualization** column displays the produced drawing, as described by the keymap YAML and the settings in "Configuration".
  You can customize what will be shown with the "Draw filters" modal, and use the "Export" dialog below it to download it in
  SVG (recommended) or PNG formats.
- **Configuration** section at the bottom contains settings that affect the drawing and parsing behaviors.
  The left column contains widgets to update common settings and the right column displays the
  [full configuration](https://github.com/caksoylar/keymap-drawer/blob/main/CONFIGURATION.md) in
  YAML format that can be edited directly.

## Want something more scriptable?

This app uses the `keymap-drawer` Python library under the hood.
It also provides a CLI that you can use, check out the [Github repo](https://github.com/caksoylar/keymap-drawer) for instructions on how to install and use it!

## Questions? Feedback?

If you have any questions on usage or feedback for new or existing features, please create a [GitHub discussion](https://github.com/caksoylar/keymap-drawer/discussions)!
