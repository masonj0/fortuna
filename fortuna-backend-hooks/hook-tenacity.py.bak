"""
PyInstaller hook for tenacity.

Tenacity uses dynamic imports for async support and retry strategies that
PyInstaller cannot automatically detect. This hook ensures all tenacity
submodules are collected into the bundle.

This is especially critical for tenacity 8.2.3+ which includes async retry support.
"""

from PyInstaller.utils.hooks import collect_submodules

# Collect all tenacity submodules recursively
hiddenimports = collect_submodules('tenacity')

# Explicitly add critical submodules that might be missed
# These are the modules tenacity dynamically imports for retry strategies and async support
critical_submodules = [
    'tenacity.retry',
    'tenacity.stop',
    'tenacity.wait',
    'tenacity.retry_if_result',
    'tenacity.retry_if_exception',
    'tenacity.before_sleep',
    'tenacity.after',
    'tenacity.before',
    'tenacity.retry_error',
    'tenacity.compat',
    'tenacity.future',
    'tenacity.asyncio',  # Critical for async retry support
]

# Merge and deduplicate
hiddenimports = list(set(hiddenimports + critical_submodules))
