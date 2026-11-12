# Kolizja strażników nagłówka UIC dla nazw formularzy z kropkami

[English](README.md) | **Polski**

Minimalna reprodukcja pokazująca, jak kropki w nazwach wyjściowych plików `.ui` powodują kolizję strażników `#ifndef` w narzędziu `uic` z Qt 5.15.

## Odtworzenie kolizji

Gdy `AUTOUIC` lub własna reguła budowania generuje `ui_<nazwa>.h` z plików zawierających kropki (`panel.alpha.ui`, `panel.beta.ui`):

```sh
uic panel.alpha.ui -o ui_panel.alpha.h
uic panel.beta.ui -o ui_panel.beta.h
```

Narzędzie `uic` w Qt 5.15 ucina nazwę na pierwszej kropce przy wyznaczaniu makra osłonowego i zapisuje `#ifndef UI_PANEL_H` w **obu** nagłówkach (zobacz [`observed-guards.json`](observed-guards.json)). Jednostka translacji dołączająca oba pliki po cichu pomija deklarację `Ui::BetaPanel` z drugiego nagłówka.

## Zalecane rozwiązanie

Zamień kropki na podkreślenia w nazwach formularzy lub generowanych nagłówków:

```sh
uic panel.alpha.ui -o ui_alpha_panel.h   # -> UI_ALPHA_PANEL_H
uic panel.beta.ui -o ui_beta_panel.h     # -> UI_BETA_PANEL_H
```

Nie włączaj globalnie `AUTOUIC_OPTIONS "-p"` (wyłączającego strażników `#ifndef`) dla całych targetów — pozostaw `-p` wyłącznie jako wąski wyjątek dla pojedynczych generowanych formularzy, gdy zewnętrzny kontrakt nazewniczy nie pozwala na zmianę nazw plików.
