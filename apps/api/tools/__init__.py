"""Tools for the resume optimization workflow."""

__all__ = [
    "exa_search",
    "exa_get_contents",
    "exa_find_similar",
    "ExaSearchParams",
    "ExaContentParams",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name in __all__:
        from tools.exa_tool import (
            exa_search,
            exa_get_contents,
            exa_find_similar,
            ExaSearchParams,
            ExaContentParams,
        )
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
