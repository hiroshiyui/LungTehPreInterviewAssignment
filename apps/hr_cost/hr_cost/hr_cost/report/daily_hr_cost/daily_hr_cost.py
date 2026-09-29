# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import add_days, flt, formatdate, getdate


def execute(filters: dict | None = None):
	"""Total HR cost (hours worked x hourly rate) per day, with period totals."""
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	data = get_data(filters)
	if filters.show_empty_days:
		data = fill_empty_days(data, getdate(filters.from_date), getdate(filters.to_date))
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
	"""Sum the stored cost per date, as the current user is allowed to see it.

	`ignore_permissions=False` makes Frappe check the user's role, apply their
	User Permissions (for example, only some employees), and refuse `cost` to a
	user without access to its permlevel. Plain `frappe.qb.from_()` does none
	of that."""
	query_filters = {"date": ["between", [getdate(filters.from_date), getdate(filters.to_date)]]}
	if filters.employee:
		query_filters["employee"] = filters.employee

	query = frappe.qb.get_query(
		"Work Record",
		fields=[
			"date",
			{"SUM": "hours_worked", "as": "hours_worked"},
			{"SUM": "cost", "as": "hr_cost"},
		],
		filters=query_filters,
		group_by="date",
		order_by="date asc",
		ignore_permissions=False,
	)
	# The field syntax has no COUNT(DISTINCT ...), so add it to the checked
	# query; `employee` is a permlevel 0 field every reader of the report sees.
	wr = frappe.qb.DocType("Work Record")
	query = query.select(Count(wr.employee).distinct().as_("employees"))
	return query.run(as_dict=True)


def fill_empty_days(data: list[dict], from_date, to_date) -> list[dict]:
	"""Add a zero row for every date in the range without work, so the chart's
	time axis is continuous: a quiet week shows as zero bars instead of vanishing."""
	by_date = {row.date: row for row in data}
	filled, day = [], from_date
	while day <= to_date:
		filled.append(
			by_date.get(day) or frappe._dict(date=day, employees=0, hours_worked=0, hr_cost=0)
		)
		day = add_days(day, 1)
	return filled


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
	days = sum(1 for row in data if row.hours_worked)  # zero rows aren't days with work
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
