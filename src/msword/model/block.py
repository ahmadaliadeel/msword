"""Block model stub for unit-10 ``io-msdoc``.

The full block tree model (Block base class, registry, paragraph-iter
protocol) lands in unit 5 (`model-blocks-schema`). Until then, this module
provides only the constant the file format needs: ``BLOCKS_SCHEMA_VERSION``.

When unit 5 lands, it owns this file and is expected to keep
``BLOCKS_SCHEMA_VERSION`` exported here (incrementing it as the block schema
evolves).
"""

from __future__ import annotations

# Bumped whenever the on-disk shape of any block JSON changes.
# Read by `io.msdoc` to gate `read_msdoc` against forward-incompatible files.
BLOCKS_SCHEMA_VERSION: int = 1

__all__ = ["BLOCKS_SCHEMA_VERSION"]
