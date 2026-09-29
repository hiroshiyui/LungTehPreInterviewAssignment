# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import Count, Sum
from frappe.utils import flt, formatdate, getdate


def execute(filters: dict | None = None):
	"""Total HR cost (hours worked x hourly rate) per day, with period totals."""
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	data = get_data(filters)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def validate_filters(filters: frappe._dict) -> None:
	if not filters.from_date or not filters.to_date:
		frappe.throw(_("From Date and To Date are required."))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))


def get_columns() -> list[dict]:
	return [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 120},
		{"label": _("Employees"), "fieldname": "employees", "fieldtype": "Int", "width": 110},
		{"label": _("Hours Worked"), "fieldname": "hours_worked", "fieldtype": "Float", "width": 130},
		{"label": _("Total HR Cost"), "fieldname": "hr_cost", "fieldtype": "Currency", "width": 160},
	]


def get_data(filters: frappe._dict) -> list[dict]:
	wr = frappe.qb.DocType("Work Record")
	query = (
		frappe.qb.from_(wr)
		.select(
			wr.date,
			Count(wr.employee).distinct().as_("employees"),
			Sum(wr.hours_worked).as_("hours_worked"),
			Sum(wr.cost).as_("hr_cost"),
		)
		.where(wr.date[getdate(filters.from_date) : getdate(filters.to_date)])
		.groupby(wr.date)
		.orderby(wr.date)
	)
	if filters.employee:
		query = query.where(wr.employee == filters.employee)

	return query.run(as_dict=True)


def get_chart(data: list[dict]) -> dict | None:
	if not data:
		return None
	return {
		"data": {
			"labels": [formatdate(row.date) for row in data],
			"datasets": [{"name": _("Total HR Cost"), "values": [flt(row.hr_cost) for row in data]}],
		},
		"type": "bar",
		"fieldtype": "Currency",
	}


def get_summary(data: list[dict]) -> list[dict]:
	total_cost = sum(flt(row.hr_cost) for row in data)
	total_hours = sum(flt(row.hours_worked) for row in data)
	days = len(data)
	return [
		{"label": _("Total HR Cost"), "value": total_cost, "datatype": "Currency", "indicator": "Blue"},
		{"label": _("Total Hours"), "value": total_hours, "datatype": "Float", "indicator": "Green"},
		{"label": _("Days With Work"), "value": days, "datatype": "Int", "indicator": "Grey"},
		{
			"label": _("Average HR Cost / Day"),
			"value": total_cost / days if days else 0,
			"datatype": "Currency",
			"indicator": "Grey",
		},
	]
