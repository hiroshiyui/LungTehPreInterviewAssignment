# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

"""Which employees a report covers, from its Employee and Nationality filters."""

import frappe


def employee_filter(filters: frappe._dict) -> str | list | None:
	"""A Work Record `employee` filter for the report's Employee and Nationality
	filters, or None for everyone. Employees are listed with `frappe.get_list`,
	so the user's User Permissions apply here too."""
	if not filters.nationality:
		return filters.employee or None
	conditions = {"nationality": filters.nationality}
	if filters.employee:
		conditions["name"] = filters.employee
	names = frappe.get_list("Employee", filters=conditions, pluck="name")
	return ["in", names or [""]]  # [""] when nobody matches: IN () isn't valid SQL
