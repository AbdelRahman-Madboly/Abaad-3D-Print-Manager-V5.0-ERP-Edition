"""
src/services/cura_service.py
============================
Cura integration service for Abaad ERP v5.0.

Two data sources (in preference order):
  1. G-code file parsing  — no external dependencies, most accurate
  2. OCR from clipboard   — requires Pillow + Tesseract (optional)

All methods are static — no instance needed.

Usage:
    from src.services.cura_service import CuraService

    result = CuraService.parse_gcode("path/to/file.gcode")
    # result = {"weight_grams": 42.5, "time_minutes": 186, "layer_height": 0.2}

    result = CuraService.extract_from_clipboard()
"""

import re
import math
import logging
from pathlib import Path
from typing import Optional, Dict

from src.utils.helpers import filament_length_to_grams

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency detection
# ---------------------------------------------------------------------------

_PILLOW_OK    = False
_TESSERACT_OK = False

try:
    from PIL import Image, ImageGrab, ImageFilter, ImageEnhance  # type: ignore
    _PILLOW_OK = True
except ImportError:
    pass

try:
    import pytesseract   # type: ignore
    import shutil, os

    # Try PATH first, then common Windows locations
    _tess = shutil.which("tesseract")
    if not _tess:
        for _p in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"D:\Program Files\Tesseract-OCR\tesseract.exe",
        ]:
            if os.path.exists(_p):
                _tess = _p
                break

    if _tess:
        pytesseract.pytesseract.tesseract_cmd = _tess
        _TESSERACT_OK = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# CuraService
# ---------------------------------------------------------------------------

class CuraService:
    """Static methods for extracting print parameters from Cura output."""

    # ------------------------------------------------------------------
    # G-code parsing  (primary, no dependencies)
    # ------------------------------------------------------------------

    @staticmethod
    def parse_gcode(file_path: str) -> Optional[Dict]:
        """Parse a Cura-sliced .gcode file and extract print parameters.

        Cura embeds metadata as comment lines near the top of the file.
        We read only the first 200 lines for speed — all metadata is there.

        Extracted fields
        ----------------
        weight_grams       : float  — filament used in grams
        time_minutes       : int    — estimated print time in minutes
        layer_height       : float  — layer height in mm
        filament_length_m  : float  — filament used in metres (raw)
        nozzle_size        : float  — nozzle diameter in mm
        print_speed        : int    — print speed in mm/s

        Returns:
            Dict of extracted values, or None if the file cannot be parsed.
        """
        path = Path(file_path)
        if not path.exists():
            log.warning("G-code file not found: %s", file_path)
            return None

        try:
            lines = []
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh):
                    if i >= 300:        # metadata is always in the first ~150 lines
                        break
                    lines.append(line)
            text = "".join(lines)
        except Exception as exc:
            log.error("Error reading gcode: %s", exc)
            return None

        result: Dict = {}

        # ── Weight ────────────────────────────────────────────────────
        # ;Filament used: 12.3456m  or  ;WEIGHT:42.5
        weight = None

        m = re.search(r";WEIGHT:\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if m:
            weight = float(m.group(1))

        if weight is None:
            # Cura 5.x: ;Filament used: 12.3456m
            m = re.search(
                r";(?:Filament used|filament_used)[:\s]+(\d+(?:\.\d+)?)m",
                text, re.IGNORECASE)
            if m:
                length_m = float(m.group(1))
                result["filament_length_m"] = length_m
                weight = filament_length_to_grams(length_m)

        if weight is None:
            # Fallback: filament_amount in mm
            m = re.search(
                r";(?:Filament used|filament_amount)[:\s]+(\d+(?:\.\d+)?)mm",
                text, re.IGNORECASE)
            if m:
                length_mm = float(m.group(1))
                length_m  = length_mm / 1000
                result["filament_length_m"] = length_m
                weight = filament_length_to_grams(length_m)

        if weight is not None:
            result["weight_grams"] = round(weight, 2)

        # ── Print time ────────────────────────────────────────────────
        # ;TIME:11234  (seconds)  or  ;Print time: 3h 6m
        time_minutes = None

        m = re.search(r";TIME:\s*(\d+)", text, re.IGNORECASE)
        if m:
            time_minutes = int(m.group(1)) // 60

        if time_minutes is None:
            # ;Estimated printing time (normal quality): 3h 6m
            m = re.search(
                r";(?:Print time|Estimated printing time)[^\d]*"
                r"(?:(\d+)h\s*)?(?:(\d+)m\s*)?(?:(\d+)s)?",
                text, re.IGNORECASE)
            if m:
                h = int(m.group(1) or 0)
                mn = int(m.group(2) or 0)
                time_minutes = h * 60 + mn

        if time_minutes is not None:
            result["time_minutes"] = time_minutes

        # ── Layer height ──────────────────────────────────────────────
        m = re.search(r";Layer height:\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if not m:
            m = re.search(r";layer_height\s*=\s*(\d+(?:\.\d+)?)", text,
                          re.IGNORECASE)
        if m:
            result["layer_height"] = float(m.group(1))

        # ── Nozzle size ───────────────────────────────────────────────
        m = re.search(r";(?:nozzle_size|Machine nozzle size)\s*[=:]\s*(\d+(?:\.\d+)?)",
                      text, re.IGNORECASE)
        if m:
            result["nozzle_size"] = float(m.group(1))

        # ── Print speed ───────────────────────────────────────────────
        m = re.search(r";(?:speed_print|print_speed)\s*=\s*(\d+)",
                      text, re.IGNORECASE)
        if m:
            result["print_speed"] = int(m.group(1))

        if not result:
            log.warning("No Cura metadata found in %s", file_path)
            return None

        log.info("G-code parsed: %s", result)
        return result

    # ------------------------------------------------------------------
    # OCR  (secondary, requires Pillow + Tesseract)
    # ------------------------------------------------------------------

    @staticmethod
    def ocr_available() -> bool:
        """Return True if both Pillow and Tesseract are available."""
        return _PILLOW_OK and _TESSERACT_OK

    @staticmethod
    def get_ocr_status() -> Dict[str, bool]:
        """Return a dict describing optional dependency status."""
        return {
            "pillow":    _PILLOW_OK,
            "tesseract": _TESSERACT_OK,
            "ready":     _PILLOW_OK and _TESSERACT_OK,
        }

    @staticmethod
    def extract_from_clipboard() -> Optional[Dict]:
        """Extract time and weight from a Cura screenshot on the clipboard.

        Returns:
            Dict with ``weight_grams`` / ``time_minutes``, or None.
        Raises:
            RuntimeError: If Pillow or Tesseract are not installed.
        """
        if not _PILLOW_OK:
            raise RuntimeError(
                "Pillow is not installed.  Run: pip install Pillow")
        if not _TESSERACT_OK:
            raise RuntimeError(
                "Tesseract is not installed or not in PATH.  "
                "See README for installation instructions.")

        image = ImageGrab.grabclipboard()
        if image is None:
            return None

        if image.mode != "RGB":
            image = image.convert("RGB")

        return CuraService._extract_from_image(image)

    @staticmethod
    def extract_from_image_file(file_path: str) -> Optional[Dict]:
        """Extract time and weight from an image file via OCR.

        Args:
            file_path: Path to PNG / JPG screenshot.

        Returns:
            Dict or None.
        """
        if not CuraService.ocr_available():
            raise RuntimeError("OCR not available.  See get_ocr_status().")
        image = Image.open(file_path)
        if image.mode != "RGB":
            image = image.convert("RGB")
        return CuraService._extract_from_image(image)

    # ------------------------------------------------------------------
    # Private OCR helpers
    # ------------------------------------------------------------------

    _TIME_PATTERNS = [
        r"(\d+)\s*h\s*(\d+)\s*m",           # 4h 12m
        r"(\d+)\s*hours?\s*(\d+)\s*min",     # 4 hours 12 min
        r"(\d+):(\d+):(\d+)",                # 04:12:30
        r"(\d+)\s*h\b",                       # 4h  (hours only)
        r"(\d+)\s*m(?:in)?(?!m)\b",          # 252m or 252min (not mm)
    ]

    _WEIGHT_PATTERNS = [
        r"(\d+(?:\.\d+)?)\s*g(?:ram)?s?\b",  # 123g / 123.5 grams
        r"Weight[:\s]+(\d+(?:\.\d+)?)",       # Weight: 123
        r"Material[:\s]+(\d+(?:\.\d+)?)",     # Material: 123
        r"Filament[:\s]+(\d+(?:\.\d+)?)",     # Filament: 123
    ]

    @staticmethod
    def _extract_from_image(image) -> Optional[Dict]:
        # Optional preprocessing for better accuracy
        try:
            gray     = image.convert("L")
            enhanced = ImageEnhance.Contrast(gray).enhance(2.0)
            sharpened = enhanced.filter(ImageFilter.SHARPEN)
            text = pytesseract.image_to_string(sharpened)
        except Exception:
            text = pytesseract.image_to_string(image)

        time_minutes = CuraService._parse_time(text)
        weight_grams = CuraService._parse_weight(text)

        if time_minutes is None and weight_grams is None:
            return None

        return {
            "time_minutes": time_minutes,
            "weight_grams": weight_grams,
        }

    @staticmethod
    def _parse_time(text: str) -> Optional[int]:
        text_lower = text.lower()
        for pattern in CuraService._TIME_PATTERNS:
            m = re.search(pattern, text_lower, re.IGNORECASE)
            if not m:
                continue
            g = m.groups()
            if len(g) == 3:                        # h:m:s
                return int(g[0]) * 60 + int(g[1])
            elif len(g) == 2:                      # h + m
                return int(g[0]) * 60 + int(g[1])
            elif len(g) == 1:
                val = int(g[0])
                if "h" in pattern:
                    return val * 60
                return val
        return None

    @staticmethod
    def _parse_weight(text: str) -> Optional[float]:
        for pattern in CuraService._WEIGHT_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    w = float(m.group(1))
                    if 0.1 <= w <= 5000:
                        return round(w, 2)
                except ValueError:
                    continue
        return None