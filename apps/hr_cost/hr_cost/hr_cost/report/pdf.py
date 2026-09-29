# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

"""The reports' "Download PDF": the page's current view as a printable A4
file, named after the report and period, to print or attach to an email."""

import frappe
from frappe import _
from frappe.utils import format_date, now_datetime
from frappe.utils.pdf import get_pdf

from hr_cost.hr_cost.report.daily_hr_cost import daily_hr_cost
from hr_cost.hr_cost.report.monthly_hr_cost import monthly_hr_cost

# Report -> (its execute(), page orientation). Monthly has a column per month.
REPORTS = {
	"Daily HR Cost": (daily_hr_cost.execute, "Portrait"),
	"Monthly HR Cost": (monthly_hr_cost.execute, "Landscape"),
}
SUMMED = ("Currency", "Float")  # columns the total row adds up


@frappe.whitelist()
def download_report_pdf(report_name: str, filters: str | dict | None = None):
	"""Send the report as a PDF download. Same checks as the report page: the
	Report's roles here, and the report's own permission-aware queries."""
	html, filename, orientation = build_report_html(report_name, filters)
	frappe.local.response.filename = filename
	frappe.local.response.filecontent = get_pdf(
		html,
		{"orientation": orientation, "page-size": "A4"},
		smart_shrinking=True,  # scale a wide table down to the page instead of clipping it
	)
	# "download", not "pdf": Frappe serves "pdf" inline (the browser's viewer),
	# "download" as an attachment, which saves straight to a file.
	frappe.local.response.type = "download"


def build_report_html(report_name: str, filters: str | dict | None = None) -> tuple[str, str, str]:
	"""The report's printable HTML, its file name, and its page orientation."""
	if report_name not in REPORTS:
		frappe.throw(_("{0} can't be downloaded as a PDF.").format(report_name))
	if not frappe.get_doc("Report", report_name).is_permitted():
		frappe.throw(_("You are not permitted to see {0}.").format(report_name), frappe.PermissionError)

	execute, orientation = REPORTS[report_name]
	filters = frappe._dict(frappe.parse_json(filters) or {})
	columns, data, _message, _chart, summary = execute(filters)

	period = f"{format_date(filters.from_date)} – {format_date(filters.to_date)}"
	employee_name = (
		frappe.db.get_value("Employee", filters.employee, "employee_name") if filters.employee else None
	)
	html = frappe.render_template(
		"hr_cost/report/report_pdf.html",
		{
			"title": _(report_name),
			"period": period,
			"employee": employee_name,
			"nationality": filters.nationality,
			"summary": [
				{"label": s["label"], "value": frappe.format_value(s["value"], {"fieldtype": s["datatype"]})}
				for s in summary
			],
			"columns": [
				{"label": c["label"], "numeric": c["fieldtype"] in ("Currency", "Float", "Int")}
				for c in columns
			],
			"rows": [[frappe.format_value(row.get(c["fieldname"]), c) for c in columns] for row in data],
			"total": total_row(columns, data),
			"generated": _("Generated {0} by {1}").format(
				frappe.format_value(now_datetime(), {"fieldtype": "Datetime"}),
				frappe.utils.get_fullname(),
			),
		},
	)
	name = f"{report_name} {filters.from_date} to {filters.to_date}"
	if filters.employee:
		# The ID, not the name: Frappe mangles non-ASCII characters (e.g. a
		# Chinese name) in download file names. The page itself shows the name.
		name += f" {filters.employee}"
	return html, f"{name}.pdf", orientation


def total_row(columns: list[dict], data: list[dict]) -> list[str] | None:
	"""Sums of the money and hours columns, under the table; blank elsewhere."""
	if not data:
		return None
	cells = []
	for i, column in enumerate(columns):
		if column["fieldtype"] in SUMMED:
			total = sum(row.get(column["fieldname"]) or 0 for row in data)
			cells.append(frappe.format_value(total, column))
		else:
			cells.append(_("Total") if i == 0 else "")
	return cells
