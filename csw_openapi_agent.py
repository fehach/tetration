#!/usr/bin/env python3
"""Backwards-compatible shim that delegates to the csw_agent package.

The original ~1900-line monolith was split into the ``csw_agent`` package.
This shim preserves the previous entry point so existing scripts keep working.
The original file is preserved as ``csw_openapi_agent.py.legacy.bak``.
"""

from __future__ import annotations

import sys
import warnings

from csw_agent.cli import main

if __name__ == "__main__":
    warnings.warn(
        "csw_openapi_agent.py is deprecated; use `csw-agent` or `python -m csw_agent`.",
        DeprecationWarning,
        stacklevel=2,
    )
    sys.exit(main())
