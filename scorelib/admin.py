"""
Compatibility layer for split admin modules.
Importing this module keeps Django admin autodiscovery intact.
"""

from .admin_actions import find_similar_names  # re-export for view workflow
from .admin_registrations import *  # noqa: F401,F403
