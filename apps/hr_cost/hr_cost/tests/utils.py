# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe


def make_employee(
	employee_name: str,
	hourly_rate: float | None = None,
	*,
	monthly_salary: float | None = None,
	date_of_joining: str = "2000-01-01",  # before every test date (2001)
	relieving_date: str | None = None,
	**fields,
) -> str:
	"""An employee paid `hourly_rate` per hour, or `monthly_salary` a month,
	from the start (the base row of their Pay History). `fields` sets any other
	Employee field (nationality, work_permit_expiry, other_names, ...)."""
	return frappe.get_doc(
		{
			"doctype": "Employee",
			"employee_name": employee_name,
			"pay_basis": "Monthly" if monthly_salary else "Hourly",
			"hourly_rate": hourly_rate,
			"monthly_salary": monthly_salary,
			"date_of_joining": date_of_joining,
			"relieving_date": relieving_date,
			**fields,
		}
	).insert().name


def add_rate(employee: str, valid_from: str | None, hourly_rate: float):
	"""Add hourly pay terms to the employee's Pay History and save."""
	return _add_pay(employee, {"valid_from": valid_from, "pay_basis": "Hourly", "hourly_rate": hourly_rate})


def add_salary(employee: str, valid_from: str | None, monthly_salary: float):
	"""Add monthly pay terms to the employee's Pay History and save."""
	return _add_pay(
		employee, {"valid_from": valid_from, "pay_basis": "Monthly", "monthly_salary": monthly_salary}
	)


def _add_pay(employee: str, row: dict):
	doc = frappe.get_doc("Employee", employee)
	doc.append("hourly_rates", row)
	doc.save()
	return doc


def make_work_record(employee: str, date: str, hours_worked: float):
	return frappe.get_doc(
		{"doctype": "Work Record", "employee": employee, "date": date, "hours_worked": hours_worked}
	).insert()


def make_user(email: str, *roles: str) -> str:
	"""A desk user with exactly `roles`. Tests roll it back in tearDown; clear
	its cached roles and User Permissions there too (`frappe.clear_cache`)."""
	user = frappe.get_doc(
		{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
	).insert(ignore_permissions=True)
	user.add_roles(*roles)
	return email
