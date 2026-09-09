# Publishing the class notes site

This repo (`isa-notes-taker` on GitHub) publishes its own notes website via
GitHub Pages, served from the `docs/` folder on the default branch. No
second repo, no manual copy step, for the normal workflow.

## What gets built where

| What | Where |
|---|---|
| Source of truth for one class | `sessions/classNN/out/notes.qmd` |
| That class's site page (plus images, optional PDF) | `notes_site/classNN/index.qmd` |
| Quarto's own render output (not committed) | `notes_site/_site/` |
| The rendered site (committed; a fresh copy of `_site/` every publish) | `docs/` |
| Optional mirror elsewhere (rare) | wherever `--deploy DIR` points |

`notes_site/class*/` is committed in this repo as the source of the site.
`docs/` is also committed; it is the deployed site itself, not a build
artifact to ignore.

## Per-class commands

```sh
python isa_notes/session.py sessions/class03
python isa_notes/session.py sessions/class03 --answer
python isa_notes/session.py sessions/class03 --publish --pdf
```

The first two write and refine the notes. The third lands the page in
`notes_site/class03/`, renders the whole site, rebuilds `docs/` from
that render, and (with `--pdf`) adds a downloadable PDF, best effort.

## Commit and push

In this repo:

```sh
git add notes_site docs
git commit -m "Publish class 03 notes"
git push
```

## GitHub Pages setup (once)

In the `isa-notes-taker` repo on GitHub: Settings, Pages, Source: "Deploy
from a branch", Branch: `main`, Folder: `/docs`. Save. After the first
push with a `docs/` folder, the site is live within a few minutes.

## The URL instructors get

- All sessions: `https://fmegahed.github.io/isa-notes-taker/`
- One session: `https://fmegahed.github.io/isa-notes-taker/class03/`

## What deploy never touches

Nothing outside `isa401/fall2026/notes/`-style targets is touched by
`--deploy`; it is not part of the normal flow. See "optional: mirror
elsewhere" below for what it does and does not do when used.

## Preview locally

```sh
quarto preview notes_site
```

This renders and serves the site at a local URL, rebuilding on save. It
writes to `notes_site/_site/` (not committed), not `docs/`; run
`--publish` when the preview looks right to rebuild `docs/` for real.

## Removing a session from the site

`docs/` is rebuilt from scratch on every publish, from whatever
`notes_site/_site/` contains at that moment; it is never merged with
whatever was there before. So: delete `notes_site/classNN/`, then
publish any other session (`--publish`, no need to touch the deleted
one) and that class disappears from `docs/` too. Commit and push as
usual.

## Optional: mirror elsewhere

`--deploy DIR` copies the rendered `docs/` into another folder, for
example a second site that already exists at some other URL:

```sh
python isa_notes/session.py sessions/class03 --publish --pdf --deploy "C:\Users\megahefm\Dropbox\Miami\Code\GitHub\fmegahed.github.io\isa401\fall2026\notes"
```

This is not needed for the normal GitHub Pages flow above; it exists for
mirroring to a place like the example path, a separate repo the user
commits and pushes by hand. Deploy only overwrites files `docs/` has; it
never deletes anything already in the target that `docs/` does not.
`docs/` must already exist (run with `--publish` first, in the same
command or an earlier one) or `--deploy` refuses. It also refuses a
target that resolves inside this project.
