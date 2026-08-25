"""Deterministic JSON, Markdown, HTML, and trace reporting for WhyBack."""

from whyback.reporting.models import ReportData, TraceViewData
from whyback.reporting.render import (
    ReportBundlePaths,
    build_interpretation_limits,
    build_population_context,
    build_report_data,
    render_report_html,
    render_report_json,
    render_report_markdown,
    write_report_bundle,
)
from whyback.reporting.trace import (
    build_trace_view,
    render_trace_html,
    write_trace_html,
)

__all__ = [
    "ReportBundlePaths",
    "ReportData",
    "TraceViewData",
    "build_interpretation_limits",
    "build_population_context",
    "build_report_data",
    "build_trace_view",
    "render_report_html",
    "render_report_json",
    "render_report_markdown",
    "render_trace_html",
    "write_report_bundle",
    "write_trace_html",
]
