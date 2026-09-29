# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe


def make_employee(employee_name: str, hourly_rate: float) -> str:
	"""An employee whose base rate (empty Valid From) is `hourly_rate`."""
	return frappe.get_doc(
		{"doctype": "Employee", "employee_name": employee_name, "hourly_rate": hourly_rate}
	).insert().name


def add_rate(employee: str, valid_from: str | None, hourly_rate: float):
	"""Add a row to the employee's Hourly Rate History and save."""
	doc = frappe.get_doc("Employee", employee)
	doc.append("hourly_rates", {"valid_from": valid_from, "hourly_rate": hourly_rate})
	doc.save()
	return doc


def make_work_record(employee: str, date: str, hours_worked: float):
	return frappe.get_doc(
		{"doctype": "Work Record", "employee": employee, "date": date, "hours_worked": hours_worked}
	).insert()
