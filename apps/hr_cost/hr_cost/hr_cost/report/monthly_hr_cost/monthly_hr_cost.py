# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_months, flt, get_first_day, getdate


def execute(filters: dict | None = None):
	"""Total HR cost per employee per month: one row per employee, one column
	per month in the range, with a total row (the Report's "Add Total Row")."""
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	months = get_months(getdate(filters.from_date), getdate(filters.to_date))
	data = get_data(filters, months)
	return get_columns(months), data, None, get_chart(data, months), get_summary(data, months)


def validate_filters(filters: frappe._dict) -> None:
	if not filters.from_date or not filters.to_date:
		frappe.throw(_("From Date and To Date are required."))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))


def get_months(from_date, to_date) -> list:
	"""The first day of every month the range touches, including months without
	work, so every employee row has the same columns."""
	months, month = [], get_first_day(from_date)
	while month <= to_date:
		months.append(month)
		month = add_months(month, 1)
	return months


def month_field(month) -> str:
	return f"m_{month:%Y_%m}"  # e.g. m_2026_01: fieldnames can't start with a digit


def get_columns(months: list) -> list[dict]:
	return [
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
		*(
			{"label": f"{month:%b %Y}", "fieldname": month_field(month), "fieldtype": "Currency", "width": 120}
			for month in months
		),
		{"label": _("Total Hours"), "fieldname": "hours_worked", "fieldtype": "Float", "width": 110},
		{"label": _("Total HR Cost"), "fieldname": "hr_cost", "fieldtype": "Currency", "width": 140},
	]


def get_data(filters: frappe._dict, months: list) -> list[dict]:
	"""One query, grouped by employee and calendar month, over the stored cost
	(each Work Record is already costed at the rate valid on its date).

	Like the daily report, the query runs with `ignore_permissions=False`, so
	it honours the user's role, User Permissions and field permlevels."""
	query_filters = {"date": ["between", [getdate(filters.from_date), getdate(filters.to_date)]]}
	if filters.employee:
		query_filters["employee"] = filters.employee

	query = frappe.qb.get_query(
		"Work Record",
		fields=[
			"employee",
			"employee.employee_name",  # the current name, joined from Employee
			{"YEAR": "date", "as": "year"},
			{"MONTH": "date", "as": "month"},
			{"SUM": "hours_worked", "as": "hours_worked"},
			{"SUM": "cost", "as": "hr_cost"},
		],
		filters=query_filters,
		group_by="employee, year, month",
		ignore_permissions=False,
	)

	rows = {}  # employee -> report row
	for r in query.run(as_dict=True):
		row = rows.setdefault(
			r.employee,
			frappe._dict(
				employee=r.employee,
				employee_name=r.employee_name,
				hours_worked=0,
				hr_cost=0,
				**{month_field(m): 0 for m in months},
			),
		)
		row[month_field(getdate(f"{r.year}-{r.month:02d}-01"))] = flt(r.hr_cost)
		row.hours_worked += flt(r.hours_worked)
		row.hr_cost += flt(r.hr_cost)
	# By name, then ID, so namesakes stay apart and in a stable order.
	return sorted(rows.values(), key=lambda row: (row.employee_name or "", row.employee))


def get_chart(data: list[dict], months: list) -> dict | None:
	if not data:
		return None
	return {
		"data": {
			"labels": [f"{month:%b %Y}" for month in months],
			"datasets": [
				{
					"name": _("Total HR Cost"),
					"values": [sum(row[month_field(month)] for row in data) for month in months],
				}
			],
		},
		"type": "bar",
		"fieldtype": "Currency",
	}


def get_summary(data: list[dict], months: list) -> list[dict]:
	total_cost = sum(row.hr_cost for row in data)
	# Like the daily report, average over months with work: the default range is
	# the whole year, and its months still to come would drag the average down.
	months_with_work = sum(1 for month in months if any(row[month_field(month)] for row in data))
	return [
		{"label": _("Total HR Cost"), "value": total_cost, "datatype": "Currency", "indicator": "Blue"},
		{
			"label": _("Total Hours"),
			"value": sum(row.hours_worked for row in data),
			"datatype": "Float",
			"indicator": "Green",
		},
		{"label": _("Employees"), "value": len(data), "datatype": "Int", "indicator": "Grey"},
		{
			"label": _("Average HR Cost / Month"),
			"value": total_cost / months_with_work if months_with_work else 0,
			"datatype": "Currency",
			"indicator": "Grey",
		},
	]
