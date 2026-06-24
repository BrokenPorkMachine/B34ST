# B34ST (B34KER/STAR) Package
# Runtime Authentication Tool for FBR34KER

"""
B34ST provides deterministic physical validation and bridge verification
for A12/A13 iPhone hardware bring-up with evidence-based maturity enforcement.

This is the main package for the B34ST validation framework.
"""

from b34st.api import B34STApi
from b34st.version import __version__, __release_name__

__all__ = ["B34STApi", "__version__", "__release_name__"]
