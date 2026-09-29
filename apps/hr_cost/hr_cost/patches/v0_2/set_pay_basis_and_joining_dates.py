# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import Min
from frappe.utils import getdate


def execute():
	"""Pay Basis and the employment dates arrived after the first employees did.

	Everyone paid so far was paid by the hour, so existing Pay History rows and
	Employees get Pay Basis "Hourly". Date of Joining becomes the employee's
	first Work Record date, or the day the Employee was created if they have
	none. No costs change: hourly pay costs exactly as before."""
	for doctype in ("Employee", "Employee Hourly Rate"):
		table = frappe.qb.DocType(doctype)
		(
			frappe.qb.update(table)
			.set(table.pay_basis, "Hourly")
			.where(table.pay_basis.isnull() | (table.pay_basis == ""))
		).run()

	work_record = frappe.qb.DocType("Work Record")
	for employee in frappe.get_all(
		"Employee", filters={"date_of_joining": ["is", "not set"]}, fields=["name", "creation"]
	):
		first_work = (
			frappe.qb.from_(work_record)
			.select(Min(work_record.date))
			.where(work_record.employee == employee.name)
		).run()[0][0]
		frappe.db.set_value(
			"Employee",
			employee.name,
			"date_of_joining",
			first_work or getdate(employee.creation),
			update_modified=False,
		)
