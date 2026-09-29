# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

"""Sample data so the Daily HR Cost report has something to show.

	bench --site <site> execute hr_cost.demo.create_demo_data
"""

import random

import frappe
from frappe.utils import add_days, add_months, get_first_day, getdate, today

DEMO_EMPLOYEES = (
	("Alice Chen", 450),
	("Bob Lin", 380),
	("Carol Wang", 520),
)
BOB_RAISE = 420


def create_demo_data() -> dict:
	"""Create demo employees and weekday work records from the start of last
	month until today. Bob gets a raise on the 1st of this month, so the report
	shows the rate history at work. Does nothing if the demo employees already
	exist. `bench execute` commits; tests roll back."""
	if frappe.db.exists("Employee", {"employee_name": DEMO_EMPLOYEES[0][0]}):
		return {"created": 0}

	employees = [
		frappe.get_doc({"doctype": "Employee", "employee_name": name, "hourly_rate": rate}).insert().name
		for name, rate in DEMO_EMPLOYEES
	]

	bob = frappe.get_doc("Employee", employees[1])
	bob.append("hourly_rates", {"valid_from": get_first_day(today()), "hourly_rate": BOB_RAISE})
	bob.save()

	rng = random.Random(42)
	created = 0
	day, end = get_first_day(add_months(today(), -1)), getdate(today())
	while day <= end:
		if day.weekday() < 5:
			for employee in employees:
				frappe.get_doc(
					{
						"doctype": "Work Record",
						"employee": employee,
						"date": day,
						"hours_worked": rng.choice((4, 6, 7.5, 8, 8, 8, 9.5)),
					}
				).insert()
				created += 1
		day = add_days(day, 1)

	return {"created": created}
