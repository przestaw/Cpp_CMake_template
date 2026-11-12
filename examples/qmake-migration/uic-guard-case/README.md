# UIC Include-Guard Collision on Dotted Form Names

**English** | [Polski](README.pl.md)

Minimal reproduction showing how dotted `.ui` output filenames produce colliding `#ifndef` include guards in Qt 5.15 `uic`.

## Reproducing the Guard Collision

When `AUTOUIC` or a custom rule generates `ui_<basename>.h` from dotted `.ui` filenames (`panel.alpha.ui`, `panel.beta.ui`):

```sh
uic panel.alpha.ui -o ui_panel.alpha.h
uic panel.beta.ui -o ui_panel.beta.h
```

Qt 5.15 `uic` truncates at the first dot when deriving the macro name, emitting `#ifndef UI_PANEL_H` in **both** headers (recorded in [`observed-guards.json`](observed-guards.json)). Any translation unit that includes both headers silently skips the second `Ui::BetaPanel` declaration.

## Recommended Fix

Rename forms or generated outputs to use underscores instead of dots so `uic` derives distinct guards:

```sh
uic panel.alpha.ui -o ui_alpha_panel.h   # -> UI_ALPHA_PANEL_H
uic panel.beta.ui -o ui_beta_panel.h     # -> UI_BETA_PANEL_H
```

Avoid applying `AUTOUIC_OPTIONS "-p"` (which strips `#ifndef` header guards altogether) globally across targets; reserve `-p` strictly as an isolated per-source compatibility escape hatch when an external schema naming contract cannot be changed.
