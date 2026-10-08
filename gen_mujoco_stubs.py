import os
import shutil
import subprocess
import sys

force_regen = True


current_dir = os.getcwd()
stubs_dir = os.path.join(current_dir, "stubs")
# PEP 561 stub package picked up by type checkers from site-packages:
package_dir = os.path.join(current_dir, "mujoco-stubs")

modules = [
    "mujoco._callbacks",
    "mujoco._constants",
    "mujoco._enums",
    "mujoco._errors",
    "mujoco._functions",
    "mujoco._render",
    "mujoco._specs",
    "mujoco._structs",
    "mujoco.rendering.classic.gl_context",
    "mujoco.rendering.classic.renderer",
    "mujoco.viewer",
]
# mujoco.gl_context and mujoco.renderer are deprecated re-export shims onto
# mujoco.rendering.classic; stubgen cannot analyze them and nothing imports
# them. Add them back here if that changes.

# stubgen emits a circular re-export for these; they are plain Exception
# subclasses defined in the compiled mujoco module.
errors_pyi = """class FatalError(Exception): ...
class UnexpectedError(Exception): ...
"""

# __init__.pyi mirrors the star-imports of the real mujoco/__init__.py so
# that mujoco.X and mujoco._sub.X name the same symbols.
init_pyi = '''"""Generated .pyi stubs for MuJoCo (see gen_mujoco_stubs.py)."""

import typing

from mujoco import _specs, _structs
from mujoco._callbacks import *
from mujoco._constants import *
from mujoco._enums import *
from mujoco._errors import *
from mujoco._functions import *
from mujoco._specs import *
from mujoco._structs import *
from mujoco._renderer import *

# runtime module attributes set in mujoco/__init__.py:
__version__: str
PLUGIN_HANDLES: list[typing.Any]
'''

# ty only honors star-imports in a PEP 561 stub package __init__.pyi, so
# Renderer is re-exported through this shim to avoid star-polluting mujoco.
renderer_shim = "from mujoco.rendering.classic.renderer import Renderer as Renderer\n"


def module_pyi(module):
    # mujoco.rendering.classic.renderer -> rendering/classic/renderer.pyi
    return os.path.join(stubs_dir, *module.split(".")) + ".pyi"


def split_params(param_str):
    parts, depth, current = [], 0, ""
    for ch in param_str:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current)
    return parts


def fix_param_order(text):
    # nanobind allows required args after defaulted ones; Python defs do not,
    # so stubgen emits invalid signatures. Make params keyword-only instead.
    out = []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("def ") and "(" in stripped:
            open_i = line.index("(")
            close_i = line.rindex(")")
            params = split_params(line[open_i + 1 : close_i])
            if not any(p.strip().startswith("*") for p in params):
                defaults_seen = False
                invalid_order = False
                for p in params[1:]:
                    if "=" in p:
                        defaults_seen = True
                    elif defaults_seen:
                        invalid_order = True
                        break
                if invalid_order and len(params) > 1:
                    line = (
                        line[: open_i + 1]
                        + params[0]
                        + ", *, "
                        + ",".join(params[1:])
                        + line[close_i:]
                    )
        out.append(line)
    return "".join(out)


# stubgen mis-transcriptions it cannot get right; applied to each generated
# module file in place.
fixups = [
    ("import mujoco._structs.MjVisual\n", "from mujoco._structs import MjVisual\n"),
    ("def compile(self, vfs: MjVfs | None = ...) -> object:", "def compile(self, vfs: MjVfs | None = ...) -> MjModel:"),
]

# renderer.pyi's bare `import mujoco` creates a cycle with __init__.pyi that
# checkers resolve to an unbound Renderer; point its annotations at the
# defining submodules instead.
renderer_fixups = [
    ("import mujoco\n", "import mujoco._enums\nimport mujoco._structs\n"),
    ("mujoco.MjModel", "mujoco._structs.MjModel"),
    ("mujoco.MjData", "mujoco._structs.MjData"),
    ("mujoco.MjvScene", "mujoco._structs.MjvScene"),
    ("mujoco.mjtFontScale", "mujoco._enums.mjtFontScale"),
]

# 1. Generate stub files
if force_regen or not os.path.exists(stubs_dir):
    if os.path.exists(stubs_dir):
        shutil.rmtree(stubs_dir)
    print("Generating stub files...")
    stubgen = os.path.join(os.path.dirname(sys.executable), "stubgen")
    for module in modules:
        subprocess.run(
            [stubgen, "-m", module, "-o", stubs_dir, "--include-docstrings"],
            check=True,
        )

    # 2. Apply fixups to generated module files in place
    for module in modules:
        path = module_pyi(module)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        for old, new in fixups:
            text = text.replace(old, new)
        if module == "mujoco.rendering.classic.renderer":
            for old, new in renderer_fixups:
                text = text.replace(old, new)
        text = fix_param_order(text)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    # 3. Hand-written files
    with open(module_pyi("mujoco._errors"), "w", encoding="utf-8") as f:
        f.write(errors_pyi)
    with open(module_pyi("mujoco._renderer"), "w", encoding="utf-8") as f:
        f.write(renderer_shim)
    init_pyi_path = os.path.join(stubs_dir, "mujoco", "__init__.pyi")
    with open(init_pyi_path, "w", encoding="utf-8") as f:
        f.write(init_pyi)

    # Stub subpackages need __init__.pyi markers for checkers to descend.
    for pkg in ("rendering", "rendering/classic"):
        marker = os.path.join(stubs_dir, "mujoco", pkg, "__init__.pyi")
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as f:
            f.write("")

    # 4. Sync into the PEP 561 stub package (installed into site-packages).
    # mujoco is a package, so its stubs live as __init__.pyi + per-submodule
    # .pyi files inside mujoco-stubs/, mirroring the package layout.
    print("Syncing stubs into mujoco-stubs/...")
    if os.path.exists(package_dir):
        shutil.rmtree(package_dir)
    shutil.copytree(os.path.join(stubs_dir, "mujoco"), package_dir)

print(f"Stub files successfully generated at {os.path.join(stubs_dir, 'mujoco')}!")
