# B34ST (B34KER/STAR) Package
# Runtime Authentication Tool for FBR34KER

"""
B34ST provides deterministic physical validation and bridge verification
for A12/A13 iPhone hardware bring-up with evidence-based maturity enforcement.

This is the main package for the B34ST validation framework.
"""

from typing import TYPE_CHECKING, Any

from b34st.version import __version__, __release_name__

if TYPE_CHECKING:
    from b34st.api import B34STApi

__all__ = ["B34STApi", "__version__", "__release_name__"]


def __getattr__(name: str) -> Any:
    if name == "B34STApi":
        from b34st.api import B34STApi

        return B34STApi
    raise AttributeError(name)
