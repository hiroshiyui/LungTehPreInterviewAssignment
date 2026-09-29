# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import add_days, flt, getdate

from hr_cost.hr_cost.report.salaries import get_permitted_salary_costs
from hr_cost.hr_cost.report.scope import employee_filter


def execute(filters: dict | None = None):
	"""Total HR cost per day, with period totals: hourly wages (hours worked ×
	hourly rate, stored on each Work Record) plus monthly salaries, which
	accrue at salary ÷ 30 per calendar day."""
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	data = get_data(filters)
	if filters.show_empty_days:
		data = fill_empty_days(data, getdate(filters.from_date), getdate(filters.to_date))
	return get_columns(), data, None, get_chart(filters.chart, data), get_summary(data)


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
		{"label": _("Hourly Wages"), "fieldname": "wages", "fieldtype": "Currency", "width": 140},
		{"label": _("Salaries"), "fieldname": "salaries", "fieldtype": "Currency", "width": 140},
		{"label": _("Total HR Cost"), "fieldname": "hr_cost", "fieldtype": "Currency", "width": 160},
	]


def get_data(filters: frappe._dict) -> list[dict]:
	"""Hourly wages and salaries per date: one row per date with either."""
	rows = {row.date: row for row in get_wages(filters)}
	salaries, _names = get_permitted_salary_costs(
		getdate(filters.from_date), getdate(filters.to_date), filters.employee, filters.nationality
	)
	for days in salaries.values():
		for day, amount in days.items():
			row = rows.setdefault(day, empty_row(day))
			row.salaries = flt(row.salaries) + amount
	for row in rows.values():
		row.salaries = flt(row.salaries)
		row.hr_cost = flt(row.wages) + row.salaries
	return sorted(rows.values(), key=lambda row: row.date)


def empty_row(day) -> frappe._dict:
	return frappe._dict(date=day, employees=0, hours_worked=0, wages=0, salaries=0, hr_cost=0)


def get_wages(filters: frappe._dict) -> list[dict]:
	"""Sum the stored cost per date, as the current user is allowed to see it.

	`ignore_permissions=False` makes Frappe check the user's role, apply their
	User Permissions (for example, only some employees), and refuse `cost` to a
	user without access to its permlevel. Plain `frappe.qb.from_()` does none
	of that."""
	query_filters = {"date": ["between", [getdate(filters.from_date), getdate(filters.to_date)]]}
	if employees := employee_filter(filters):
		query_filters["employee"] = employees

	query = frappe.qb.get_query(
		"Work Record",
		fields=[
			"date",
			{"SUM": "hours_worked", "as": "hours_worked"},
			{"SUM": "cost", "as": "wages"},
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
		filled.append(by_date.get(day) or empty_row(day))
		day = add_days(day, 1)
	return filled


# Chart name -> (the row field it plots, chart type, value format). Separate
# charts, not one mixed chart: costs run in thousands and hours in tens, and
# Frappe's charts have a single y axis, so hours would lie flat on it.
CHARTS = {
	"HR Cost": ("hr_cost", "bar", "Currency"),
	"Hours Worked": ("hours_worked", "bar", "Float"),
	"Employees at Work": ("employees", "line", "Int"),
}


def chart_label(date, data: list[dict]) -> str:
	"""Short, so it fits under a bar: the day ("07") when the range is one
	month, otherwise month-day ("09-07"). The table keeps the full date."""
	first, last = data[0].date, data[-1].date
	return f"{date:%d}" if (first.year, first.month) == (last.year, last.month) else f"{date:%m-%d}"


def get_chart(chart: str | None, data: list[dict]) -> dict | None:
	"""The chart picked in the report's "Chart" filter."""
	if not data:
		return None
	chart = chart or "HR Cost"
	if chart not in CHARTS:
		frappe.throw(_("Unknown chart: {0}").format(chart))
	field, chart_type, fieldtype = CHARTS[chart]
	labels = [chart_label(row.date, data) for row in data]
	if chart == "HR Cost":
		# Stack wages and salaries, so each bar shows what the day's cost is made of.
		datasets = [{"name": _("Hourly Wages"), "values": [flt(row.wages) for row in data]}]
		if any(row.salaries for row in data):
			datasets.append({"name": _("Salaries"), "values": [flt(row.salaries) for row in data]})
		return {
			"data": {"labels": labels, "datasets": datasets},
			"type": "bar",
			"barOptions": {"stacked": 1},
			"fieldtype": fieldtype,
		}
	return {
		"data": {
			"labels": labels,
			"datasets": [{"name": _(chart), "values": [flt(row[field]) for row in data]}],
		},
		"type": chart_type,
		"fieldtype": fieldtype,
	}


def get_summary(data: list[dict]) -> list[dict]:
	total_cost = sum(flt(row.hr_cost) for row in data)
	total_hours = sum(flt(row.hours_worked) for row in data)
	days = sum(1 for row in data if row.hours_worked)  # zero rows aren't days with work
	# Salaries cost every calendar day, weekends included, so average over the
	# days with any cost, not only the days with work.
	days_with_cost = sum(1 for row in data if row.hr_cost)
	return [
		{"label": _("Total HR Cost"), "value": total_cost, "datatype": "Currency", "indicator": "Blue"},
		{"label": _("Total Hours"), "value": total_hours, "datatype": "Float", "indicator": "Green"},
		{"label": _("Days With Work"), "value": days, "datatype": "Int", "indicator": "Grey"},
		{
			"label": _("Average HR Cost / Day"),
			"value": total_cost / days_with_cost if days_with_cost else 0,
			"datatype": "Currency",
			"indicator": "Grey",
		},
	]
