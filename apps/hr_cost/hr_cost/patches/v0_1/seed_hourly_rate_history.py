# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Give every Employee created before the Hourly Rate History existed a
	base rate row, so Work Records can look up a rate again.

	Existing Work Records keep their stored rate and cost: under the old model
	each record copied the rate at its creation time, which can't be turned
	back into dated history. Records are re-costed the next time that
	employee's history is edited."""
	for employee in frappe.get_all("Employee", fields=["name", "hourly_rate"]):
		if frappe.db.exists("Employee Hourly Rate", {"parenttype": "Employee", "parent": employee.name}):
			continue
		row = frappe.get_doc(
			{
				"doctype": "Employee Hourly Rate",
				"parenttype": "Employee",
				"parentfield": "hourly_rates",
				"parent": employee.name,
				"idx": 1,
				"hourly_rate": employee.hourly_rate,
			}
		)
		# Inserted directly: saving the Employee would re-cost its existing records.
		row.db_insert()
