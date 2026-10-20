"""Discovery: file types, classification, component ownership, and activation."""

from quality.discovery.activation import active_components, is_active
from quality.discovery.classify import FileRecord, Region, classify, owner, region_of
from quality.discovery.filetypes import FileKind, FileType, detect, shebang_language
from quality.discovery.inventory import Inventory, build_inventory
from quality.discovery.manifests import Manifest, ManifestError, parse_manifest
from quality.discovery.rules import RULES

__all__ = [
    "RULES",
    "FileKind",
    "FileRecord",
    "FileType",
    "Inventory",
    "Manifest",
    "ManifestError",
    "Region",
    "active_components",
    "build_inventory",
    "classify",
    "detect",
    "is_active",
    "owner",
    "parse_manifest",
    "region_of",
    "shebang_language",
]
