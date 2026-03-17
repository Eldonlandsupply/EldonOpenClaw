"""
src/config/__init__.py

DEPRECATED — this package is no longer the authoritative config system.

The canonical runtime config is src/openclaw/config.AppConfig.
Use that for all new code, tests, and tooling.

This package (src/config/schema.py + loader.py) remains for reference
but is not used by the live runtime or CI.
"""
# Re-export nothing. Import from openclaw.config instead.
