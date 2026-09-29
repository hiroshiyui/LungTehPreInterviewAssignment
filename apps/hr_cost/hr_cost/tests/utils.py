# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe


def make_employee(employee_name: str, hourly_rate: float) -> str:
	return frappe.get_doc(
		{"doctype": "Employee", "employee_name": employee_name, "hourly_rate": hourly_rate}
	).insert().name


def make_work_record(employee: str, date: str, hours_worked: float):
	return frappe.get_doc(
		{"doctype": "Work Record", "employee": employee, "date": date, "hours_worked": hours_worked}
	).insert()
