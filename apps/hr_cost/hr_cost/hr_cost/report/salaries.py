# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

"""Monthly salaries for the reports, read with the same checks as the rest of
each report: Work Record costs come from permission-aware queries, and so
must salaries."""

import frappe
from frappe import _

from hr_cost.hr_cost.doctype.employee.employee import get_salary_costs


def get_permitted_salary_costs(
	from_date, to_date, employee: str | None = None, nationality: str | None = None
) -> tuple[dict, dict]:
	"""Salary cost per employee per day ({employee: {date: amount}}), and the
	employees' current names ({employee: name}), for the employees this user
	may see.

	Salaries are pay (permlevel 1 on Employee): a user who can't read that
	level is refused. `frappe.get_list` applies the user's role and User
	Permissions, so a manager limited to some employees gets only theirs."""
	if 1 not in frappe.get_meta("Employee").get_permlevel_access("read"):
		frappe.throw(_("You are not permitted to see salaries."), frappe.PermissionError)
	filters = {"date_of_joining": ["<=", to_date]}  # joined after the range: nothing accrues
	if employee:
		filters["name"] = employee
	if nationality:
		filters["nationality"] = nationality
	employees = frappe.get_list(
		"Employee", filters=filters, fields=["name", "employee_name", "date_of_joining", "relieving_date"]
	)
	return (
		get_salary_costs(employees, from_date, to_date),
		{row.name: row.employee_name for row in employees},
	)
