"""Approved wording for patient messages.

Public interface (SPEC section 7):

    render(template_id, language, slots) -> Rendered
    reword(text, language, tone, slots) -> Reworded
    list_templates() -> list[dict]

Rules decide, templates speak. `render` is deterministic and is the default everywhere.
`reword` is optional (env WORDING_PROVIDER) and falls back to the template text on any problem.
This package imports nothing from app.engine, app.api or app.db and does nothing at import time.
"""
from .core import (
    Rendered,
    TemplateError,
    MissingSlotError,
    UnknownTemplateError,
    UnsupportedLanguageError,
    get_template,
    list_templates,
    render,
    teach_back,
)
from .reword import Reworded, reword
from .validator import validate

__all__ = [
    "Rendered", "Reworded", "TemplateError", "MissingSlotError", "UnknownTemplateError",
    "UnsupportedLanguageError", "get_template", "list_templates", "render", "reword", "teach_back", "validate",
]
