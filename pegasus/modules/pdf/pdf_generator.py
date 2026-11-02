"""
PDF Report Generator for Enterprise Reports
Enterprise-grade PDF generation with configurable templates and professional formatting
Supports dynamic data extraction, multi-format output, and corporate styling
"""

from typing import *
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing_extensions import TypedDict
import asyncio
import json
import logging
from pathlib import Path
from fpdf import FPDF
from fpdf.enums import XPosition

logger = logging.getLogger(__name__)

class ReportTemplate(BaseModel):
    """"PDF report template configuration"""
    template_id: str
    name: str
    description: str
    page_size: str = "A4"
    orientation: str = "portrait"
    margins: Dict[str, float] = {"top": 20, "bottom": 20, "left": 20, "right": 20}
    header_height: int = 40
    footer_height: int = 20
    primary_font: str = "Helvetica"
    secondary_font: str = "Helvetica"
    primary_font_size: int = 12
    secondary_font_size: int = 10
    heading_font_size: int = 18
    subheading_font_size: int = 14
    line_height: float = 1.2
    watermark_enabled: bool = False
    watermark_text: str = "CONFIDENTIAL"
    colors: Dict[str, str] = {"primary": "#1976aa", "secondary": "#666666", "accent": "#1976aa"}
    sections: List[Dict[str, Any]]

class PDFSection(BaseModel):
    """PDF section configuration"""
    section_id: str
    title: str
    type: str = "content"
    content: Optional[List[Dict[str, Any]]] = None
    chart_data: Optional[Dict[str, Any]] = None
    table_data: Optional[Dict[str, Any]] = None
    image_path: Optional[str] = None
    calculations: Optional[List[Dict[str, Any]]] = None
    formatting: Dict[str, Any] = field(default_factory=lambda: {"align": "left", "wrap": True})
class ReportData(BaseModel):
    """Report data structure"""
    report_id: str
    title: str
    date: datetime
    generated_by: str
    organization: str
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    data_points: Dict[str, Any] = field(default_factory=dict)
    sections: List[PDFSection] = field(default_factory=list)
    charts: List[Dict[str, Any]] = field(default_factory=list)
    executive_summary: Optional[str] = None
class PDFReportGenerator:
    """PDF Report Generator Implementation"""

    def __init__(self, templates_dir: str = "templates", output_dir: str = "output"):
        self.templates_dir = Path(templates_dir)
        self.output_dir = Path(output_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_report(self, report_data: ReportData, template_id: Optional[str] = None) -> str:
        """Generate PDF report"""
        try:
            # Load or use default template
            if template_id:
                template = await self._load_template(template_id)
            else:
                template = await self._get_default_template()

            # Create PDF document
            pdf = FPDF()
            pdf.add_page()

            # Add metadata
            pdf.set_title(report_data.title)
            pdf.set_author(report_data.generated_by)
            pdf.set_subject(report_data.title)
            pdf.set_creator(f"{report_data.organization} PDF Generator")
            pdf.set_keywords("report, business, enterprise, PDF")

            # Add watermark if enabled
            if template.watermark_enabled:
                self._add_watermark(pdf, template)

            # Add header
            self._add_header(pdf, report_data, template)

            # Add sections
            for section in report_data.sections:
                self._add_section(pdf, section, template, report_data)

            # Add charts if available
            for chart_data in report_data.charts:
                self._add_chart(pdf, chart_data, template)

            # Add footer
            self._add_footer(pdf, report_data, template)

            # Generate filename
            filename = f"{report_data.title}_{report_data.date.strftime('%Y%m%d')}_{report_data.report_id}.pdf"
            filepath = self.output_dir / filename

            # Save PDF
            pdf.output(str(filepath))

            logger.info(f"Generated PDF report: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to generate PDF report: {e}")
            raise

    async def _load_template(self, template_id: str) -> ReportTemplate:
        """Load report template"""
        template_file = self.templates_dir / f"{template_id}.json"
        if not template_file.exists():
            logger.warning(f"Template {template_id} not found, using default")
            return await self._get_default_template()

        try:
            with open(template_file, "r") as f:
                template_dict = json.load(f)

            # Convert to ReportTemplate (simplified)
            sections = [PDFSection(**section) for section in template_dict.get("sections", [])]

            return ReportTemplate(
                template_id=template_dict.get("template_id", template_id),
                name=template_dict.get("name", "Unnamed Template"),
                description=template_dict.get("description", ""),
                page_size=template_dict.get("page_size", "A4"),
                orientation=template_dict.get("orientation", "portrait"),
                margins=template_dict.get("margins", {"top": 20, "bottom": 20, "left": 20, "right": 20}),
                header_height=template_dict.get("header_height", 40),
                footer_height=template_dict.get("footer_height", 20),
                primary_font=template_dict.get("primary_font", "Helvetica"),
                secondary_font=template_dict.get("secondary_font", "Helvetica"),
                primary_font_size=template_dict.get("primary_font_size", 12),
                secondary_font_size=template_dict.get("secondary_font_size", 10),
                heading_font_size=template_dict.get("heading_font_size", 18),
                subheading_font_size=template_dict.get("subheading_font_size", 14),
                line_height=template_dict.get("line_height", 1.2),
                watermark_enabled=template_dict.get("watermark_enabled", False),
                watermark_text=template_dict.get("watermark_text", "CONFIDENTIAL"),
                colors=template_dict.get("colors", {"primary": "#1976aa", "secondary": "#666666", "accent": "#1976aa"}),
                sections=sections
            )

        except Exception as e:
            logger.error(f"Failed to load template {template_id}: {e}")
            return await self._get_default_template()

    async def _get_default_template(self) -> ReportTemplate:
        """Get default template"""
        sections = [
            PDFSection(
                section_id="executive_summary",
                title="Executive Summary",
                type="summary",
                content=[]
            ),
            PDFSection(
                section_id="key_findings",
                title="Key Findings",
                type="table",
                table_data={}
            ),
            PDFSection(
                section_id="detailed_analysis",
                title="Detailed Analysis",
                type="content",
                content=[]
            ),
            PDFSection(
                section_id="recommendations",
                title="Recommendations",
                type="list",
                content=[]
            ),
            PDFSection(
                section_id="appendices",
                title="Appendices",
                type="image",
                image_path=""
            )
        ]

        return ReportTemplate(
            template_id="default",
            name="Default Corporate Report",
            description="Standard corporate report template",
            page_size="A4",
            orientation="portrait",
            margins={"top": 40, "bottom": 40, "left": 30, "right": 30},
            header_height=40,
            footer_height=30,
            primary_font="Helvetica",
            secondary_font="Helvetica",
            primary_font_size=12,
            secondary_font_size=10,
            heading_font_size=18,
            subheading_font_size=14,
            line_height=1.2,
            watermark_enabled=True,
            watermark_text="CONFIDENTIAL",
            colors={"primary": "#1976aa", "secondary": "#666666", "accent": "#1976aa"},
            sections=sections
        )

    def _add_watermark(self, pdf: FPDF, template: ReportTemplate) -> None:
        """Add watermark to PDF"""
        pdf.set_font(pdf.get_font_family("Arial")[0], "B", 20)
        pdf.set_text_color(230, 230, 230)

        # Center watermark
        pdf.set_xy(pdf.epw / 2, pdf.epw / 2)
        pdf.rotate(45)

        # Calculate number of repetitions
        repetitions = int(pdf.epw / 200) * int(pdf.eph / 300)

        for i in range(repetitions):
            y_position = 100 + i * 150
            if y_position < pdf.eph:
                pdf.set_xy(pdf.epw / 2, y_position)
                pdf.cell(100, 10, template.watermark_text, 0, 0, "C")


    def _add_header(self, pdf: FPDF, report_data: ReportData, template: ReportTemplate) -> None:
        """Add report header"""
        pdf.set_font("B", 16)
        pdf.set_text_color(25, 118, 170)  # Primary color

        # Organization name
        pdf.set_xy(template.margins["left"], template.margins["top"] / 2)
        pdf.cell(0, 10, report_data.organization, 0, 1, "L")

        # Report title
        pdf.set_font("B", 20)
        pdf.set_xy(template.margins["left"], template.margins["top"] / 2 + 15)
        pdf.cell(0, 15, report_data.title, 0, 1, "L")

        # Report metadata
        pdf.set_font("", 10)
        pdf.set_text_color(102, 102, 102)  # Secondary color

        metadata_lines = [
            f"Report ID: {report_data.report_id}",
            f"Date: {report_data.date.strftime('%B %d, %Y')}",
            f"Generated by: {report_data.generated_by}",
            f"Version: {report_data.version}"
        ]

        current_y = template.margins["top"] / 2 + 45
        for line in metadata_lines:
            pdf.set_xy(template.margins["left"], current_y)
            pdf.cell(0, 8, line, 0, 1, "L")
            current_y += 12

        # Add separator line
        pdf.set_xy(template.margins["left"], current_y)
        pdf.set_line_width(0.5)
        pdf.set_draw_color(25, 118, 170)
        pdf.line(template.margins["left"], current_y, pdf.epw - template.margins["right"], current_y)

    def _add_section(self, pdf: FPDF, section: PDFSection, template: ReportTemplate, report_data: ReportData) -> None:
        """Add section to PDF"""
        current_y = self._get_current_y(pdf, template)

        # Section title
        pdf.set_font("B", template.heading_font_size)
        pdf.set_text_color(25, 118, 170)
        pdf.set_xy(template.margins["left"], current_y)
        pdf.cell(0, 15, section.title, 0, 1, "L")

        current_y += 20

        # Section content based on type
        if section.type == "content":
            self._add_content_section(pdf, section, template, current_y)
        elif section.type == "table":
            self._add_table_section(pdf, section, template, current_y)
        elif section.type == "list":
            self._add_list_section(pdf, section, template, current_y)
        elif section.type == "summary":
            self._add_summary_section(pdf, section, template, current_y)
        elif section.type == "image":
            self._add_image_section(pdf, section, template, current_y)

        # Update current position
        section_height = self._calculate_section_height(pdf, section, template)
        pdf.set_xy(template.margins["left"], current_y + section_height + 20)

    def _add_content_section(self, pdf: FPDF, section: PDFSection, template: ReportTemplate, start_y: float) -> None:
        """Add content section"""
        pdf.set_font("", template.primary_font_size)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(template.margins["left"], start_y)

        if section.content:
            for item in section.content:
                if item.get("type") == "paragraph":
                    pdf.multi_cell(pdf.epw - template.margins["left"] - template.margins["right"],
                                 template.primary_font_size * template.line_height,
                                 item.get("text", ""),
                                 border=0,
                                 align="L")
                    pdf.ln(template.primary_font_size * template.line_height)

                elif item.get("type") == "heading":
                    pdf.set_font("B", template.subheading_font_size)
                    pdf.multi_cell(pdf.epw - template.margins["left"] - template.margins["right"],
                                 template.subheading_font_size * template.line_height,
                                 item.get("text", ""),
                                 border=0,
                                 align="L")
                    pdf.ln(template.subheading_font_size * template.line_height)
                    pdf.set_font("", template.primary_font_size)

    def _add_table_section(self, pdf: FPDF, section: PDFSection, template: ReportTemplate, start_y: float) -> None:
        """Add table section"""
        pdf.set_font("", template.secondary_font_size)
        pdf.set_text_color(0, 0, 0)

        if section.table_data:
            # Simple table implementation
            table_data = section.table_data
            headers = table_data.get("headers", [])
            rows = table_data.get("rows", [])

            if headers:
                # Table header
                pdf.set_font("B", template.secondary_font_size)
                pdf.set_fill_color(240, 240, 240)

                header_y = start_y
                for i, header in enumerate(headers):
                    pdf.set_xy(template.margins["left"] + i * (pdf.epw - template.margins["left"] - template.margins["right"]) / len(headers),
                               header_y)
                    pdf.cell((pdf.epw - template.margins["left"] - template.margins["right"]) / len(headers),
                              template.secondary_font_size * template.line_height,
                              header,
                              1,
                              0,
                              "C",
                              fill=True)

                # Table rows
                pdf.set_font("", template.secondary_font_size)
                row_y = start_y + template.secondary_font_size * template.line_height + 5

                for row in rows:
                    for i, cell in enumerate(row):
                        pdf.set_xy(template.margins["left"] + i * (pdf.epw - template.margins["left"] - template.margins["right"]) / len(headers),
                                   row_y)
                        pdf.cell((pdf.epw - template.margins["left"] - template.margins["right"]) / len(headers),
                                  template.secondary_font_size * template.line_height,
                                  str(cell),
                                  1,
                                  0,
                                  "L")

                    row_y += template.secondary_font_size * template.line_height + 5

    def _add_list_section(self, pdf: FPDF, section: PDFSection, template: ReportTemplate, start_y: float) -> None:
        """Add list section"""
        pdf.set_font("", template.primary_font_size)
        pdf.set_text_color(0, 0, 0)

        if section.content:
            for item in section.content:
                if item.get("type") == "bullet":
                    pdf.set_xy(template.margins["left"], start_y)
                    pdf.cell(5, template.primary_font_size * template.line_height, "•", 0, 0, "L")
                    pdf.set_xy(template.margins["left"] + 10, start_y)
                    pdf.multi_cell(pdf.epw - template.margins["left"] - template.margins["right"] - 10,
                                 template.primary_font_size * template.line_height,
                                 item.get("text", ""),
                                 border=0,
                                 align="L")
                    pdf.ln(template.primary_font_size * template.line_height)
                    start_y += template.primary_font_size * template.line_height + 5

    def _add_summary_section(self, pdf: FPDF, section: PDFSection, template: ReportTemplate, start_y: float) -> None:
        """Add summary section"""
        if section.executive_summary:
            pdf.set_font("B", template.subheading_font_size)
            pdf.set_text_color(25, 118, 170)
            pdf.set_xy(template.margins["left"], start_y)
            pdf.cell(0, 15, "Executive Summary", 0, 1, "L")

            pdf.set_font("", template.primary_font_size)
            pdf.set_text_color(0, 0, 0)

            summary_y = start_y + 20
            summary_lines = section.executive_summary.split("\n")
            for line in summary_lines:
                pdf.set_xy(template.margins["left"], summary_y)
                pdf.multi_cell(pdf.epw - template.margins["left"] - template.margins["right"],
                             template.primary_font_size * template.line_height,
                             line,
                             border=0,
                             align="L")
                pdf.ln(template.primary_font_size * template.line_height)
                summary_y += template.primary_font_size * template.line_height * 1.5

    def _add_image_section(self, pdf: FPDF, section: PDFSection, template: ReportTemplate, start_y: float) -> None:
        """Add image section"""
        if section.image_path and Path(section.image_path).exists():
            try:
                pdf.image(section.image_path,
                         x=template.margins["left"],
                         y=start_y,
                         w=pdf.epw - template.margins["left"] - template.margins["right"],
                         h=100)
                pdf.ln(110)

            except Exception as e:
                logger.error(f"Failed to add image section: {e}")

    def _add_chart(self, pdf: FPDF, chart_data: Dict[str, Any], template: ReportTemplate) -> None:
        """Add chart to PDF (placeholder for actual chart generation)"""
        current_y = self._get_current_y(pdf, template)

        # Placeholder for chart generation
        chart_title = chart_data.get("title", "Chart")
        chart_type = chart_data.get("type", "bar")

        pdf.set_font("B", template.subheading_font_size)
        pdf.set_text_color(25, 118, 170)
        pdf.set_xy(template.margins["left"], current_y)
        pdf.cell(0, 15, chart_title, 0, 1, "L")

        current_y += 20

        # Add chart placeholder
        pdf.set_font("", template.secondary_font_size)
        pdf.set_text_color(102, 102, 102)
        pdf.set_xy(template.margins["left"], current_y)
        pdf.cell(0, 10, f"[{chart_type.capitalize()} Chart - Data Placeholder]", 0, 1, "L")

        # TODO: Implement actual chart generation using libraries like matplotlib or Plotly

    def _add_footer(self, pdf: FPDF, report_data: ReportData, template: ReportTemplate) -> None:
        """Add report footer"""
        footer_y = pdf.eph - template.footer_height

        pdf.set_y(footer_y)

        # Footer line
        pdf.set_line_width(0.5)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(template.margins["left"], footer_y,
                pdf.epw - template.margins["right"], footer_y)

        # Footer text
        pdf.set_font("", 8)
        pdf.set_text_color(153, 153, 153)

        footer_text = [
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Report ID: {report_data.report_id}",
            f"Version: {report_data.version}",
            f"Page {pdf.page_no()}"
        ]

        current_x = template.margins["left"]
        for i, line in enumerate(footer_text):
            pdf.set_xy(current_x, footer_y + 5 + i * 8)
            pdf.cell(0, 8, line, 0, 1, "L")

    def _get_current_y(self, pdf: FPDF, template: ReportTemplate) -> float:
        """Get current Y position with margin consideration"""
        return pdf.get_y()

    def _calculate_section_height(self, pdf: FPDF, section: PDFSection, template: ReportTemplate) -> float:
        """Calculate section height"""
        # Simple height calculation - could be enhanced
        return 200  # Placeholder

    def load_templates_from_file(self, file_path: str) -> Dict[str, ReportTemplate]:
        """Load all templates from file"""
        try:
            with open(file_path, "r") as f:
                templates_data = json.load(f)

            templates = {}
            for template_dict in templates_data:
                sections = [PDFSection(**section) for section in template_dict.get("sections", [])]
                template = ReportTemplate(
                    template_id=template_dict.get("template_id", ""),
                    name=template_dict.get("name", ""),
                    description=template_dict.get("description", ""),
                    page_size=template_dict.get("page_size", "A4"),
                    orientation=template_dict.get("orientation", "portrait"),
                    margins=template_dict.get("margins", {"top": 20, "bottom": 20, "left": 20, "right": 20}),
                    header_height=template_dict.get("header_height", 40),
                    footer_height=template_dict.get("footer_height", 20),
                    primary_font=template_dict.get("primary_font", "Helvetica"),
                    secondary_font=template_dict.get("secondary_font", "Helvetica"),
                    primary_font_size=template_dict.get("primary_font_size", 12),
                    secondary_font_size=template_dict.get("secondary_font_size", 10),
                    heading_font_size=template_dict.get("heading_font_size", 18),
                    subheading_font_size=template_dict.get("subheading_font_size", 14),
                    line_height=template_dict.get("line_height", 1.2),
                    watermark_enabled=template_dict.get("watermark_enabled", False),
                    watermark_text=template_dict.get("watermark_text", "CONFIDENTIAL"),
                    colors=template_dict.get("colors", {"primary": "#1976aa", "secondary": "#666666", "accent": "#1976aa"}),
                    sections=sections
                )
                templates[template.template_id] = template

            logger.info(f"Loaded {len(templates)} templates from {file_path}")
            return templates

        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
            return {}

    async def save_templates_to_file(self, templates: Dict[str, ReportTemplate], file_path: str) -> bool:
        """Save templates to file"""
        try:
            templates_data = []
            for template in templates.values():
                template_dict = {
                    "template_id": template.template_id,
                    "name": template.name,
                    "description": template.description,
                    "page_size": template.page_size,
                    "orientation": template.orientation,
                    "margins": template.margins,
                    "header_height": template.header_height,
                    "footer_height": template.footer_height,
                    "primary_font": template.primary_font,
                    "secondary_font": template.secondary_font,
                    "primary_font_size": template.primary_font_size,
                    "secondary_font_size": template.secondary_font_size,
                    "heading_font_size": template.heading_font_size,
                    "subheading_font_size": template.subheading_font_size,
                    "line_height": template.line_height,
                    "watermark_enabled": template.watermark_enabled,
                    "watermark_text": template.watermark_text,
                    "colors": template.colors,
                    "sections": [section.dict() for section in template.sections]
                }
                templates_data.append(template_dict)

            with open(file_path, "w") as f:
                json.dump(templates_data, f, indent=2)

            logger.info(f"Saved {len(templates)} templates to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save templates: {e}")
            return False