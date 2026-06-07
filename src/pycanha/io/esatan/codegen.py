"""Assemble the generated ``<basename>.py`` from translated imperative blocks.

The output is a standalone, editable Python module.  Each ESATAN imperative
block becomes a function taking the model; ``$SUBROUTINES`` content is emitted
at module level (v1: as commented/untranslated lines, since SUBROUTINE
definitions are a later milestone).  The model is never mutated by parsing —
this file is a template the analyst copies in whole or in part.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

# Block keyword -> (generated function name, header label). Fixed order.
_BLOCK_FUNCTIONS: tuple[tuple[str, str], ...] = (
    ("$INITIAL", "initial"),
    ("$EXECUTION", "execution"),
    ("$VARIABLES1", "variables1"),
    ("$VARIABLES2", "variables2"),
)


def emit_script(
    path: str | Path,
    source_name: str,
    translated: dict[str, list[str]],
) -> None:
    """Write ``<basename>.py`` from the per-block translated Python lines."""
    Path(path).write_text(
        _render(source_name, translated),
        encoding="utf-8",
    )


def _render(source_name: str, translated: dict[str, list[str]]) -> str:
    lines: list[str] = [
        f'"""Generated from {source_name}.d on {date.today().isoformat()}. '
        'Edit freely; copy fragments into your code."""',
        "from __future__ import annotations",
        "",
        "from pycanha.tmm import ThermalMathematicalModel",
        "",
    ]

    # $SUBROUTINES at module level.
    lines.append("# ----- $SUBROUTINES -----")
    sub_body = translated.get("$SUBROUTINES", [])
    sub_content = [ln for ln in sub_body if ln.strip()]
    if sub_content:
        lines.extend(sub_content)
    else:
        lines.append("# (none)")
    lines.append("")

    for block, func_name in _BLOCK_FUNCTIONS:
        lines.append(f"# ----- {block} -----")
        lines.append(f"def {func_name}(model: ThermalMathematicalModel) -> None:")
        body = translated.get(block, [])
        lines.extend(_function_body(body))
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def _function_body(body: list[str]) -> list[str]:
    """Indent a block body by 4 spaces; ``pass`` when empty/comment-only."""
    has_code = any(ln.strip() and not ln.lstrip().startswith("#") for ln in body)
    rendered = [("    " + ln if ln.strip() else "") for ln in body]
    if not has_code:
        rendered.append("    pass")
    return rendered
