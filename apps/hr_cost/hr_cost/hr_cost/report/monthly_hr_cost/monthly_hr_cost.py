# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_months, flt, get_first_day, getdate

from hr_cost.hr_cost.report.salaries import get_permitted_salary_costs
from hr_cost.hr_cost.report.scope import employee_filter


def execute(filters: dict | None = None):
	"""Total HR cost per employee per month: one row per employee, one column
	per month in the range, with a total row (the Report's "Add Total Row")."""
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	months = get_months(getdate(filters.from_date), getdate(filters.to_date))
	data, hours = get_data(filters, months)
	cost = {month: sum(row[month_field(month)] for row in data) for month in months}
	return (
		get_columns(months),
		data,
		None,
		get_chart(filters.chart, data, months, cost, hours),
		get_summary(data, months, cost),
	)


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


def get_data(filters: frappe._dict, months: list) -> tuple[list[dict], dict]:
	"""Each employee's HR cost per month: hourly wages from one query, grouped
	by employee and calendar month, over the stored cost (each Work Record is
	already costed at the rate valid on its date), plus monthly salaries, which
	accrue at salary ÷ 30 per calendar day.

	Like the daily report, the query runs with `ignore_permissions=False`, so
	it honours the user's role, User Permissions and field permlevels.

	Returns the report rows, and the hours worked per month (for the
	effective hourly rate chart)."""
	query_filters = {"date": ["between", [getdate(filters.from_date), getdate(filters.to_date)]]}
	if employees := employee_filter(filters):
		query_filters["employee"] = employees

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

	def row_for(employee, employee_name):
		return rows.setdefault(
			employee,
			frappe._dict(
				employee=employee,
				employee_name=employee_name,
				hours_worked=0,
				hr_cost=0,
				**{month_field(m): 0 for m in months},
			),
		)

	rows = {}  # employee -> report row
	hours = dict.fromkeys(months, 0.0)
	for r in query.run(as_dict=True):
		row = row_for(r.employee, r.employee_name)
		month = getdate(f"{r.year}-{r.month:02d}-01")
		row[month_field(month)] += flt(r.hr_cost)
		hours[month] += flt(r.hours_worked)
		row.hours_worked += flt(r.hours_worked)
		row.hr_cost += flt(r.hr_cost)

	salaries, names = get_permitted_salary_costs(
		getdate(filters.from_date), getdate(filters.to_date), filters.employee, filters.nationality
	)
	for employee, days in salaries.items():
		# A salaried employee gets a row even without a Work Record in the range.
		row = row_for(employee, names[employee])
		for day, amount in days.items():
			row[month_field(get_first_day(day))] += amount
			row.hr_cost += amount
	# By name, then ID, so namesakes stay apart and in a stable order.
	return sorted(rows.values(), key=lambda row: (row.employee_name or "", row.employee)), hours


CHARTS = ("Cost by Employee", "Cost Share", "Effective Hourly Rate")


def chart_label(month, months: list) -> str:
	"""Short, so it fits under a bar: "Jan", or "Jan 26" when the range spans
	years. The report page gives axis labels only a few characters."""
	return f"{month:%b}" if months[0].year == months[-1].year else f"{month:%b %y}"


def get_chart(chart: str | None, data: list[dict], months: list, cost: dict, hours: dict) -> dict | None:
	"""The chart picked in the report's "Chart" filter."""
	if not data:
		return None
	chart = chart or CHARTS[0]
	if chart not in CHARTS:
		frappe.throw(_("Unknown chart: {0}").format(chart))

	if chart == "Cost Share":
		# Who the range's cost goes to, as slices of the whole.
		return {
			"data": {
				"labels": [row.employee_name for row in data],
				"datasets": [{"name": _("HR Cost"), "values": [row.hr_cost for row in data]}],
			},
			# No "fieldtype": Frappe would format the legend's values as HTML.
			"type": "donut",
		}

	if chart == "Effective Hourly Rate":
		# Cost ÷ hours for each month: it rises with raises, and moves with who
		# did the work. Salaries count as cost, and salaried staff's logged hours
		# as hours. A month without hours has no rate, so it's left out.
		worked = [month for month in months if hours[month]]
		return {
			"data": {
				"labels": [chart_label(month, months) for month in worked],
				"datasets": [
					{
						"name": _("Effective Hourly Rate"),
						"values": [flt(cost[month] / hours[month], 2) for month in worked],
					}
				],
			},
			"type": "line",
			"fieldtype": "Currency",
		}

	# One bar per month, stacked by employee: the total, and who it goes to.
	return {
		"data": {
			"labels": [chart_label(month, months) for month in months],
			"datasets": [
				{"name": row.employee_name, "values": [row[month_field(month)] for month in months]}
				for row in data
			],
		},
		"type": "bar",
		"barOptions": {"stacked": 1},
		"fieldtype": "Currency",
	}


def get_summary(data: list[dict], months: list, cost: dict) -> list[dict]:
	total_cost = sum(row.hr_cost for row in data)
	# Average over months with any cost: the default range is the whole year,
	# and its months still to come would drag the average down.
	worked = [month for month in months if cost[month]]
	summary = [
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
			"value": total_cost / len(worked) if worked else 0,
			"datatype": "Currency",
			"indicator": "Grey",
		},
	]
	if change := get_month_over_month(months, cost, worked):
		summary.append(change)
	return summary


def get_month_over_month(months: list, cost: dict, worked: list) -> dict | None:
	"""The latest month with work against the calendar month before it, when
	both are in the range. A rise in cost shows red, a fall green."""
	if not worked:
		return None
	latest = worked[-1]
	previous = add_months(latest, -1)
	if previous not in cost:
		return None
	change = cost[latest] - cost[previous]
	return {
		"label": _("{0} vs {1}").format(f"{latest:%b %Y}", f"{previous:%b %Y}"),
		"value": change,
		"datatype": "Currency",
		"indicator": "Red" if change > 0 else "Green",
	}
