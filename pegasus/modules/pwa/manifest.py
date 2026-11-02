"""
Progressive Web Application Manifest Configuration

Web app manifest configuration for Progressive Web Application (PWA)
Manages application metadata, icons, and configuration for offline capabilities
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime
import json
from pathlib import Path

@dataclass
class WebAppManifest:
    """Web app manifest configuration"""
    name: str
    short_name: str
    description: str
    start_url: str = "/"
    display_origin: str
    display: Dict[str, Any]
    icons: List[Dict[str, Any]]
    background_color: str = "#ffffff"
    theme_color: str = "#1976aa"
    themes: List[Dict[str, Any]] = []
    prefer_related_applications: bool = False
    capture_links: bool = True
    scope: str = "standalone-bl viewable"
    categories: List[str] = []
class PWAManifest:
    """PWA Manifest configuration"""

    def __init__(self, manifest: WebAppManifest, icons_dir: str = "icons"):
        self.manifest = manifest
        self.icons_dir = icons_dir
        self.generated_manifest = None


    def generate_manifest(self) -> Dict[str, Any]:
        """Generate PWA manifest"""
        # Prepare icons
        icon_data = self._prepare_icons()

        # Build manifest structure
        manifest_structure = {
            "name": self.manifest.name,
            "short_name": self.manifest.short_name,
            "description": self.manifest.description,
            "start_url": self.manifest.start_url,
            "display": self.manifest.display,
            "display_origin": self.manifest.display_origin,
            "icons": icon_data,
            "background_color": self.manifest.background_color,
            "theme_color": self.manifest.theme_color,
            "themes": self.manifest.themes,
            "prefer_related_applications": self.manifest.prefer_related_applications,
            "capture_links": self.manifest.capture_links,
            "scope": self.manifest.scope,
            "categories": self.manifest.categories
        }

        self.generated_manifest = manifest_structure
        return manifest_structure


    def _prepare_icons(self) -> List[Dict[str, Any]]:
        """Prepare icons for manifest"""
        icons = []

        # Try to load icons from directory
        try:
            icon_dir_path = Path(self.icons_dir)
            if icon_dir_path.exists():
                for icon_file in icon_dir_path.iterdir():
                    if icon_file.is_file:
                        icon_name = icon_file.name
                        file_extension = icon_file.suffix

                    # Supported icon formats
                    if file_extension in ["png", "jpg", "jpeg", "ico", "svg", "webp"]:
                        icon_data = {
                            "src": f"/icons/{icon_name}",
                            "sizes": self._get_icon_sizes(icon_name, file_extension),
                            "type": self._get_icon_type(file_extension),
                            "purpose": self._get_icon_purpose(icon_name)
                        }
                        icons.append(icon_data)
        except Exception as e:
            pass


        return icons


    def _get_icon_sizes(self, icon_name: str, file_extension: str) -> List[Dict[str, Any]]:
        """Get icon sizes based on icon name and extension"""
        sizes = []

        if file_extension in ["png", "webp"]:
            # Web App Manifest (144x144)
            sizes.append({"size": "144x144", "purpose": "shortcut"})
            # Web App Manifest (192x192)
            sizes.append({"size": "192x192", "purpose": "logo"})
            # Web App Manifest (512x512)
            sizes.append({"size": "512x512", "purpose": "any"})
        elif file_extension in ["jpg", "jpeg"]:
            # Mobile App (144x144)
            sizes.append({"size": "144x144", "purpose": "shortcut"})
            # Mobile App (192x192)
            sizes.append({"size": "192x192", "purpose": "logo"})
            # Mobile App (768x1024)
            sizes.append({"size": "768x1024", "purpose": "any"})
        elif file_extension == "ico":
            # iOS App (20x20)
            sizes.append({"size": "20x20", "purpose": "any"})
            # iOS App (40x40)
            sizes.append({"size": "40x40", "purpose": "any"})

        elif file_extension == "svg":
            # SVG Icon (any size)
            sizes.append({"size": "any", "purpose": "any"})
        elif file_extension == "webp":
            # WebP Icon (any size)
            sizes.append({"size": "any", "purpose": "any"})


        return sizes


    def _get_icon_type(self, file_extension: str) -> str:
        """Get icon MIME type"""
        mime_types = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "ico": "image/x-icon",
            "svg": "image/svg+xml",
            "webp": "image/webp"
        }
        return mime_types.get(file_extension, "image/octet-stream")


    def _get_icon_purpose(self, icon_name: str) -> str:
        """Determine icon purpose based on name"""
        icon_name_lower = icon_name.lower()

        if "logo" in icon_name_lower or "icon" in icon_name_lower:
            return "logo"
        elif "splash" in icon_name_lower or "launch" in icon_name_lower:
            return "splash"
        elif "notification" in icon_name_lower:
            return "notification"
        elif "watch" in icon_name_lower:
            return "background"
        else:
            return "any"


    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to dictionary"""
        return {
            "manifest": self.generated_manifest,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "platform": "PWA"
        }


    def save_manifest(self, file_path: str) -> bool:
        """Save manifest to file"""
        try:
            with open(file_path, "w") as f:
                json.dump(self.generated_manifest, f, indent=2)
            logger.info(f"Manifest saved to {file_path}")
            return True


        except Exception as e:
            logger.error(f"Failed to save manifest: {e}")
            return False


    def load_manifest(self, file_path: str) -> bool:
        """Load manifest from file"""
        try:
            with open(file_path, "r") as f:
                manifest_data = json.load(f)

            # Reconstruct manifest object (simplified)
            self.generated_manifest = manifest_data
            logger.info(f"Manifest loaded from {file_path}")
            return True


        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
            return False