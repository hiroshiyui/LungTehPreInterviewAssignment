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


def create_demo_data() -> dict:
	"""Create demo employees and weekday work records from the start of last
	month until today. Does nothing if the demo employees already exist."""
	if frappe.db.exists("Employee", {"employee_name": DEMO_EMPLOYEES[0][0]}):
		return {"created": 0}

	employees = [
		frappe.get_doc({"doctype": "Employee", "employee_name": name, "hourly_rate": rate}).insert().name
		for name, rate in DEMO_EMPLOYEES
	]

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

	frappe.db.commit()
	return {"created": created}
