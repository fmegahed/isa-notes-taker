# notes_site

This is the Quarto website for the ISA 401 class notes. It renders to its
own `_site/` (not committed); `isa_notes/session.py --publish` then
rebuilds the project root's `docs/` from that `_site/` from scratch,
since `docs/` is what GitHub Pages serves from this repo's default
branch.

The `class*/` folders are written by `isa_notes/session.py --publish`; do
not edit their `index.qmd` files by hand, since the next publish overwrites
them.
