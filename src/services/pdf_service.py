"""
src/services/pdf_service.py
===========================
PDF generation service for Abaad ERP v5.0.

Generates:
  • Quote PDF   — estimated totals, deposit required, validity date
  • Receipt PDF — actual totals, amount received, change given

Also generates plain-text receipts for WhatsApp copy-paste.

Requires reportlab. If not installed, generate_quote() / generate_receipt()
raise RuntimeError with installation instructions.

Usage:
    from src.services.pdf_service import PdfService
    svc = PdfService(db)
    path = svc.generate_receipt(order)
    svc.open_file(path)
"""

import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.core.config import (
    APP_NAME, APP_VERSION,
    COMPANY, EXPORT_DIR, LOGO_PATH,
)
from src.utils.helpers import format_currency

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional ReportLab detection
# ---------------------------------------------------------------------------

_RL_OK = False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib import colors as rl_colors
    try:
        from reportlab.platypus import Image as _RLImage
    except ImportError:
        _RLImage = None
    _RL_OK = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Colour palette (hex strings + one helper)
# ---------------------------------------------------------------------------

_C = {
    "primary":    "#1e3a8a",
    "success":    "#10b981",
    "warning":    "#f59e0b",
    "danger":     "#ef4444",
    "text":       "#0f172a",
    "text_light": "#64748b",
    "border":     "#e2e8f0",
    "stripe":     "#f8fafc",
    "purple":     "#7c3aed",
    "yellow_bg":  "#fef3c7",
}


def _hex(h: str):
    """Convert '#rrggbb' to a ReportLab Color."""
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255
    return rl_colors.Color(r, g, b)


# ---------------------------------------------------------------------------
# PdfService
# ---------------------------------------------------------------------------

class PdfService:
    """Generates PDF documents for orders.

    Args:
        db: DatabaseManager instance used to read company / quote settings.
           Pass None to use config defaults only.
    """

    def __init__(self, db=None) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def is_available() -> bool:
        """Return True if ReportLab is installed."""
        return _RL_OK

    def generate_quote(self, order, output_path: Optional[Path] = None) -> str:
        """Generate a Quote PDF. Returns the saved file path."""
        self._require_reportlab()
        return self._build_pdf(order, "QUOTE", output_path, is_quote=True)

    def generate_receipt(self, order, output_path: Optional[Path] = None) -> str:
        """Generate a Receipt PDF. Returns the saved file path."""
        self._require_reportlab()
        return self._build_pdf(order, "RECEIPT", output_path, is_quote=False)

    def generate_text_receipt(self, order) -> str:
        """Return a plain-text receipt string for WhatsApp copy-paste."""
        c = self._load_company()
        lines = [
            f"*{c['name']} — {c['subtitle']}*",
            f"📍 {c['address']}  📞 {c['phone']}",
            "─" * 34,
            f"Order #: {order.order_number or order.id[:8]}",
            f"Customer: {order.customer_name}",
        ]
        if order.customer_phone:
            lines.append(f"Phone: {order.customer_phone}")
        lines.append(f"Date: {(order.created_date or '')[:10]}")
        if order.is_rd_project:
            lines.append("🔬 R&D Project — cost-only pricing")
        lines.append("─" * 34)
        lines.append("*Items:*")

        for item in getattr(order, "items", []):
            w = item.weight          # uses .weight property (actual or estimated)
            q = item.quantity
            r = item.rate_per_gram
            t = item.print_cost
            lines.append(f"  • {item.name} ({item.color})  "
                          f"{w:.0f}g × {q} × {r:.2f} = {t:.2f} EGP")

        lines.append("─" * 34)

        def _row(label: str, value: float, prefix: str = ""):
            lines.append(f"{prefix}{label}: {value:.2f} EGP")

        _row("Base Total (4 EGP/g)", order.subtotal)
        if order.discount_amount > 0.005:
            lines.append(f"✓ Rate Discount: -{order.discount_amount:.2f} EGP")
        if order.order_discount_amount > 0.005:
            lines.append(
                f"✓ Order Discount ({order.order_discount_percent:.1f}%): "
                f"-{order.order_discount_amount:.2f} EGP")
        if order.tolerance_discount_total > 0.005:
            lines.append(f"✓ Tolerance Discounts: -{order.tolerance_discount_total:.2f} EGP")
        if order.shipping_cost > 0.005:
            _row("🚚 Shipping", order.shipping_cost, "+ ")
        if order.payment_fee > 0.005:
            _row(f"Fee ({order.payment_method})", order.payment_fee, "+ ")
        lines.append(f"*TOTAL: {order.total:.2f} EGP*")
        if order.amount_received > 0.005:
            _row("✓ Received", order.amount_received)
            change = order.amount_received - order.total
            if change > 0.01:
                _row("Change", change, "← ")
        lines.append("─" * 34)
        lines.append(f"_{c.get('tagline', '')}_ | {c.get('social', '')}")
        return "\n".join(lines)

    @staticmethod
    def open_file(path: str) -> None:
        """Open a file with the system default viewer."""
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception as exc:
            log.warning("Could not open file %s: %s", path, exc)

    # ------------------------------------------------------------------
    # Internal: build PDF
    # ------------------------------------------------------------------

    def _require_reportlab(self) -> None:
        if not _RL_OK:
            raise RuntimeError(
                "ReportLab is not installed.\n"
                "Run:  pip install reportlab")

    def _build_pdf(self, order, doc_type: str,
                   output_path: Optional[Path], is_quote: bool) -> str:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        if output_path is None:
            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            num = getattr(order, "order_number", order.id[:6])
            output_path = EXPORT_DIR / f"{doc_type}_{num}_{ts}.pdf"

        doc = SimpleDocTemplate(
            str(output_path), pagesize=A4,
            topMargin=14*mm, bottomMargin=14*mm,
            leftMargin=14*mm, rightMargin=14*mm,
        )

        company  = self._load_company()
        styles   = self._make_styles()
        elements = []
        elements += self._sec_header(order, doc_type, company, styles)
        elements += self._sec_customer(order, styles)
        elements += self._sec_items(order, styles, show_actual=not is_quote)
        elements += self._sec_totals(order, styles, company, is_quote=is_quote)
        elements += self._sec_footer(order, styles, company, is_quote=is_quote)

        doc.build(elements)
        log.info("PDF saved: %s", output_path)
        return str(output_path)

    # ------------------------------------------------------------------
    # Company settings
    # ------------------------------------------------------------------

    def _load_company(self) -> dict:
        base = {
            "name":          COMPANY["name"],
            "subtitle":      COMPANY["subtitle"],
            "phone":         COMPANY["phone"],
            "address":       COMPANY["address"],
            "tagline":       COMPANY["tagline"],
            "social":        COMPANY["social"],
            "deposit_pct":   50,
            "validity_days": 7,
            "footer_note":   "Thank you for your business!",
        }
        if self._db is None:
            return base
        setting_keys = [
            "company_name", "company_subtitle", "company_phone",
            "company_address", "company_tagline", "company_social",
            "quote_deposit_pct", "quote_validity_days", "invoice_footer",
        ]
        try:
            rows = {r["key"]: r["value"]
                    for r in self._db.get_settings_by_keys(setting_keys)}
            if rows.get("company_name"):     base["name"]          = rows["company_name"]
            if rows.get("company_subtitle"): base["subtitle"]      = rows["company_subtitle"]
            if rows.get("company_phone"):    base["phone"]         = rows["company_phone"]
            if rows.get("company_address"):  base["address"]       = rows["company_address"]
            if rows.get("company_tagline"):  base["tagline"]       = rows["company_tagline"]
            if rows.get("company_social"):   base["social"]        = rows["company_social"]
            if rows.get("quote_deposit_pct"):
                base["deposit_pct"] = float(rows["quote_deposit_pct"])
            if rows.get("quote_validity_days"):
                base["validity_days"] = int(rows["quote_validity_days"])
            if rows.get("invoice_footer"):   base["footer_note"]   = rows["invoice_footer"]
        except Exception:
            pass  # fallback to config defaults
        return base

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    def _make_styles(self):
        s = getSampleStyleSheet()
        defs = [
            ("SecHdr",   {"fontName": "Helvetica-Bold", "fontSize": 11,
                           "textColor": _hex(_C["primary"]), "spaceAfter": 4}),
            ("Body",     {"fontName": "Helvetica", "fontSize": 10,
                           "textColor": _hex(_C["text"])}),
            ("Small",    {"fontName": "Helvetica", "fontSize": 8,
                           "textColor": _hex(_C["text_light"])}),
            ("Footer",   {"fontName": "Helvetica-Oblique", "fontSize": 9,
                           "textColor": _hex(_C["text_light"]),
                           "alignment": TA_CENTER}),
            ("Disclaimer",{"fontName": "Helvetica-Oblique", "fontSize": 8,
                            "textColor": _hex(_C["warning"]),
                            "alignment": TA_CENTER}),
            ("TotalLbl", {"fontName": "Helvetica-Bold", "fontSize": 12,
                           "textColor": _hex(_C["primary"])}),
        ]
        for name, kw in defs:
            s.add(ParagraphStyle(name=name, **kw))
        return s

    # ------------------------------------------------------------------
    # Section: header
    # ------------------------------------------------------------------

    def _sec_header(self, order, doc_type: str, company: dict, s) -> list:
        elems = []

        # Logo
        logo_cell: object = ""
        if _RLImage and LOGO_PATH.exists():
            try:
                logo_cell = _RLImage(str(LOGO_PATH), width=36*mm, height=36*mm)
            except Exception:
                pass

        company_html = (
            f"<b><font size='15' color='{_C['primary']}'>{company['name']}</font></b><br/>"
            f"<font size='9' color='{_C['text_light']}'>{company['subtitle']}</font><br/>"
            f"<font size='9'>{company['address']}</font><br/>"
            f"<font size='9'>📞 {company['phone']}</font>"
        )

        doc_color = {
            "RECEIPT": _C["primary"],
            "QUOTE":   _C["warning"],
            "INVOICE": _C["success"],
        }.get(doc_type, _C["primary"])

        rd_badge = (
            f"<font color='{_C['purple']}'><b>🔬 R&D PROJECT</b></font><br/>"
            if getattr(order, "is_rd_project", False) else ""
        )
        date_str = (getattr(order, "created_date", "") or "")[:10]
        doc_html = (
            f"<font size='13' color='{doc_color}'><b>{doc_type}</b></font><br/>"
            f"{rd_badge}"
            f"<font size='10'>Order #: <b>{order.order_number or order.id[:8]}</b></font><br/>"
            f"<font size='9'>Date: {date_str}</font><br/>"
            f"<font size='9'>Status: <b>{order.status}</b></font>"
        )

        hdr = Table(
            [[logo_cell,
              Paragraph(company_html, s["Body"]),
              Paragraph(doc_html,     s["Body"])]],
            colWidths=[40*mm, 80*mm, 60*mm],
        )
        hdr.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN",  (2, 0), (2, 0),   "RIGHT"),
        ]))
        elems += [
            hdr,
            Spacer(1, 4*mm),
            HRFlowable(width="100%", thickness=2, color=_hex(_C["primary"])),
            Spacer(1, 4*mm),
        ]
        return elems

    # ------------------------------------------------------------------
    # Section: customer info
    # ------------------------------------------------------------------

    def _sec_customer(self, order, s) -> list:
        elems = [Paragraph("Customer Information", s["SecHdr"])]
        rows = [
            ["Name:",  order.customer_name  or "Walk-in"],
            ["Phone:", order.customer_phone or "—"],
        ]
        tbl = Table(rows, colWidths=[26*mm, 100*mm])
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN",    (0, 0), (0, -1),  "RIGHT"),
        ]))
        elems += [tbl, Spacer(1, 5*mm)]
        return elems

    # ------------------------------------------------------------------
    # Section: items table
    # ------------------------------------------------------------------

    def _sec_items(self, order, s, show_actual: bool = False) -> list:
        elems = [Paragraph("📦 Order Items", s["SecHdr"])]

        header_row = ["#", "Description", "Color", "Qty", "Weight (g)", "Rate/g", "Total (EGP)"]
        data = [header_row]
        total_w = 0
        total_t = 0

        for i, item in enumerate(getattr(order, "items", []), 1):
            w  = item.weight
            q  = item.quantity
            r  = item.rate_per_gram
            t  = item.print_cost
            mn = item.time_minutes
            total_w += w * q
            total_t += mn * q

            desc = f"<b>{item.name}</b>"
            if item.tolerance_discount_applied:
                disc = item.tolerance_discount_amount
                desc += (f"<br/><font size='8' color='{_C['success']}'>"
                         f"✓ Tolerance disc: -{disc:.2f}</font>")

            data.append([
                str(i),
                Paragraph(desc, s["Small"]),
                item.color,
                str(q),
                f"{w:.1f}",
                f"{r:.2f}",
                f"{t:.2f}",
            ])

        # Summary row
        h_hours = total_t // 60
        h_mins  = total_t % 60
        data.append([
            "",
            f"Total: {len(getattr(order, 'items', []))} item(s)",
            "",
            "",
            f"{total_w:.0f}g",
            f"{h_hours}h {h_mins}m",
            "",
        ])

        col_w = [10*mm, 62*mm, 22*mm, 12*mm, 22*mm, 18*mm, 28*mm]
        tbl = Table(data, colWidths=col_w)
        tbl.setStyle(TableStyle([
            # Header row
            ("BACKGROUND",  (0, 0), (-1, 0),  _hex(_C["primary"])),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  rl_colors.white),
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0),  9),
            # Data rows
            ("FONTSIZE",    (0, 1), (-1, -2), 9),
            ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
            ("ALIGN",       (1, 1), (1, -1),  "LEFT"),
            ("ALIGN",       (2, 1), (2, -1),  "LEFT"),
            ("GRID",        (0, 0), (-1, -2), 0.5, _hex(_C["border"])),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2),
             [rl_colors.white, _hex(_C["stripe"])]),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",  (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
            # Summary row
            ("BACKGROUND",  (0, -1), (-1, -1), _hex("#e5e7eb")),
            ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
            ("LINEABOVE",   (0, -1), (-1, -1), 1.5, _hex(_C["primary"])),
        ]))
        elems += [tbl, Spacer(1, 6*mm)]
        return elems

    # ------------------------------------------------------------------
    # Section: payment totals
    # ------------------------------------------------------------------

    def _sec_totals(self, order, s, company: dict,
                    is_quote: bool = False) -> list:
        elems = [Paragraph("💰 Payment Summary", s["SecHdr"])]

        rows: list = []

        # Helper: add a row only if value is non-zero (unless force=True)
        def _r(label: str, value_str: str, force: bool = False,
               bold: bool = False, bg: Optional[str] = None):
            rows.append((label, value_str, bold, bg))

        _r("Base Total (4 EGP/g):",
           f"{order.subtotal:.2f} EGP", force=True)

        if order.discount_amount > 0.005:
            _r("✓ Rate Discount:",
               f"-{order.discount_amount:.2f} EGP")

        if order.order_discount_amount > 0.005:
            _r(f"✓ Order Discount ({order.order_discount_percent:.1f}%):",
               f"-{order.order_discount_amount:.2f} EGP")

        if order.tolerance_discount_total > 0.005:
            _r("✓ Tolerance Discounts:",
               f"-{order.tolerance_discount_total:.2f} EGP")

        if order.shipping_cost > 0.005:
            _r("🚚 Shipping:", f"+{order.shipping_cost:.2f} EGP")

        _r(f"Payment: {order.payment_method}", "", force=True)
        if order.payment_fee > 0.005:
            _r("Payment Fee:", f"+{order.payment_fee:.2f} EGP")

        # Separator
        rows.append(("", "", False, None))

        if is_quote:
            _r("📋 ESTIMATED TOTAL:", f"{order.total:.2f} EGP",
               bold=True, force=True)
            dep_pct = company.get("deposit_pct", 50)
            dep     = order.total * dep_pct / 100
            rows.append(("", "", False, None))
            _r(f"💵 Deposit Required ({dep_pct:.0f}%):",
               f"{dep:.2f} EGP", bold=True, bg=_C["yellow_bg"])
            _r("💵 Balance on Delivery:",
               f"{order.total - dep:.2f} EGP", bold=True, bg=_C["yellow_bg"])
            validity = (
                datetime.now() +
                timedelta(days=int(company.get("validity_days", 7)))
            ).strftime("%Y-%m-%d")
            _r("📅 Quote valid until:", validity)
        else:
            _r("📋 TOTAL:", f"{order.total:.2f} EGP", bold=True, force=True)
            if order.rounding_loss > 0.005:
                _r("Rounding:", f"-{order.rounding_loss:.2f} EGP")
            if order.amount_received > 0.005:
                _r("✓ Amount Received:", f"{order.amount_received:.2f} EGP")
                change = order.amount_received - order.total
                if change > 0.01:
                    _r("Change:", f"{change:.2f} EGP")
                elif change < -0.01:
                    _r("⚠ Balance Due:", f"{-change:.2f} EGP")

        # Build table data
        tbl_data  = [[lbl, val] for lbl, val, *_ in rows]
        tbl = Table(tbl_data, colWidths=[110*mm, 60*mm])

        style_cmds = [
            ("ALIGN",      (0, 0), (0, -1), "RIGHT"),
            ("ALIGN",      (1, 0), (1, -1), "RIGHT"),
            ("FONTSIZE",   (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for i, (lbl, val, bold, bg) in enumerate(rows):
            if "✓" in lbl or "Discount" in lbl:
                style_cmds.append(("TEXTCOLOR", (1, i), (1, i),
                                   _hex(_C["success"])))
            if "⚠" in lbl:
                style_cmds.append(("TEXTCOLOR", (1, i), (1, i),
                                   _hex(_C["warning"])))
            if bold:
                style_cmds += [
                    ("FONTNAME",  (0, i), (-1, i), "Helvetica-Bold"),
                    ("FONTSIZE",  (0, i), (-1, i), 13),
                    ("TEXTCOLOR", (0, i), (-1, i), _hex(_C["primary"])),
                    ("LINEABOVE", (0, i), (-1, i), 2,  _hex(_C["primary"])),
                ]
            if bg:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), _hex(bg)))

        tbl.setStyle(TableStyle(style_cmds))
        elems += [tbl, Spacer(1, 8*mm)]
        return elems

    # ------------------------------------------------------------------
    # Section: footer
    # ------------------------------------------------------------------

    def _sec_footer(self, order, s, company: dict,
                    is_quote: bool = False) -> list:
        elems: list = [
            HRFlowable(width="100%", thickness=1, color=_hex(_C["border"])),
            Spacer(1, 4*mm),
        ]

        if is_quote:
            elems.append(Paragraph(
                "📋 ESTIMATE — Final pricing may vary ±100 EGP "
                "based on actual print results.",
                s["Disclaimer"]))
        else:
            elems.append(Paragraph(
                "✓ Supports removed for recycling. "
                "Design tolerances are the customer's responsibility.",
                s["Small"]))

        if getattr(order, "is_rd_project", False):
            elems.append(Paragraph(
                "🔬 R&D Project — Cost-only pricing (no profit margin).",
                s["Disclaimer"]))

        footer_note = company.get("footer_note", "Thank you for your business!")
        elems += [
            Spacer(1, 3*mm),
            Paragraph("Payment due upon delivery. All sales final. "
                       "Files retained 30 days.", s["Small"]),
            Spacer(1, 6*mm),
            Paragraph(
                f"<b>Thank you for choosing {company['name']}!</b>",
                s["Footer"]),
            Paragraph(footer_note, s["Footer"]),
            Spacer(1, 3*mm),
            Paragraph(
                f"{company.get('tagline', '')} | 📞 {company['phone']} | "
                f"📍 {company['address']} | {company.get('social', '')}",
                s["Footer"]),
            Spacer(1, 4*mm),
            Paragraph(
                f"<font size='7'>Generated by {APP_NAME} v{APP_VERSION} — "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</font>",
                s["Footer"]),
        ]
        return elems