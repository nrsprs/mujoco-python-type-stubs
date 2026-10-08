# mujoco-stubs

PEP 561 type stubs for MuJoCo, generated from the installed MuJoCo with
`stubgen` (mypy). Type checkers (ty, pyright) and IDE completion read them
from `site-packages/mujoco-stubs/`.

## Install (this repo)

`uv sync` installs this package non-editable as a dev dependency
(see `pyproject.toml`). Do not use `pip install -e .`: checkers discover
stub packages by scanning `site-packages` for a real `mujoco-stubs/`
directory, which an editable install does not create.

## Regenerating after a MuJoCo version change

```bash
cd mujoco-stubs
uv run python gen_mujoco_stubs.py
uv sync --reinstall-package mujoco-stubs
```

The script runs `stubgen` against the venv's `mujoco`, applies fixups for
stubgen artifacts (nanobind parameter ordering, `MjSpec.compile` return
type, runtime-only module attributes), and syncs the result into the
`mujoco-stubs/` stub package.

If generation fails with "Critical error during semantic analysis", a
broken stub set in `site-packages` is poisoning `stubgen`'s import
analysis: `uv pip uninstall mujoco-stubs`, regenerate, then `uv sync`.

## Layout notes

- `mujoco-stubs/__init__.pyi` mirrors the star-imports of the real
  `mujoco/__init__.py` so `mujoco.X` and `mujoco._sub.X` name the same
  symbols. ty only honors star-imports in a stub package `__init__.pyi`;
  `Renderer` is re-exported through the `_renderer.pyi` shim.
- `mujoco.gl_context` and `mujoco.renderer` (deprecated shims) are not
  stubbed; the real modules live under `mujoco.rendering.classic`.
