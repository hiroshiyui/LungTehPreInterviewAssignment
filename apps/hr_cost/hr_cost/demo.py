# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

"""Sample data so the reports have something to show, and one user per HR
role so the difference between the roles can be seen.

	bench --site <site> execute hr_cost.demo.create_demo_data
"""

import random

import frappe
from frappe.utils import add_days, add_months, get_first_day, getdate, today
from frappe.utils.password import update_password

DEMO_EMPLOYEES = (
	# name, pay basis, hourly rate or monthly salary, nationality, other names,
	# days until the work permit expires (None: no permit needed)
	("Alice Chen", "Hourly", 450, "Taiwan", [("Chinese", "陳愛麗")], None),
	("Bob Lin", "Hourly", 380, "Taiwan", [("Chinese", "林寶")], None),
	("Carol Wang", "Hourly", 520, "Taiwan", [("Chinese", "王凱蘿")], None),
	# 60000 a month is 2000 a day (÷ 30); her Work Records log hours only.
	("Dora Lee", "Monthly", 60000, "Taiwan", [("Chinese", "李朵拉")], None),
	# Staff from Southeast Asia: names in their own scripts, and work permits.
	("Nguyen Thi Huong", "Monthly", 29500, "Vietnam", [("Vietnamese", "Nguyễn Thị Hương"), ("Chinese", "阮氏香")], 20),
	("Somchai Jaidee", "Hourly", 196, "Thailand", [("Thai", "สมชาย ใจดี")], 400),
	("Siti Rahayu", "Monthly", 29500, "Indonesia", [], 700),
)
BOB_RAISE = 420
DEMO_USERS = (
	# email, first name, role
	("hr.manager@example.com", "Hanna (HR Manager)", "HR Manager"),
	("hr.user@example.com", "Uma (HR User)", "HR User"),
)
# Known on purpose, like Administrator's "admin": this is a tutorial site that
# listens on 127.0.0.1 only. Never load demo data on a real site.
DEMO_PASSWORD = "demo"


def create_demo_data() -> dict:
	"""Create the demo users, then each missing demo employee (joined at the
	start of last month) with weekday Work Records from then until today. Bob
	gets a raise on the 1st of this month, so the reports show the Pay History
	at work. Creates only what's missing, and returns how many documents it
	created: provisioning reports a change unless that's 0. `bench execute`
	commits; tests roll back."""
	created = create_demo_users()
	start = get_first_day(add_months(today(), -1))

	employees = []
	for name, basis, amount, nationality, other_names, permit_days in DEMO_EMPLOYEES:
		if frappe.db.exists("Employee", {"employee_name": name}):
			continue
		employee = frappe.get_doc(
			{
				"doctype": "Employee",
				"employee_name": name,
				"nationality": nationality,
				"other_names": [{"writing_system": ws, "other_name": other} for ws, other in other_names],
				"date_of_joining": start,
				"work_permit_number": f"DEMO-{len(employees) + 1:04d}" if permit_days else None,
				"work_permit_expiry": add_days(today(), permit_days) if permit_days else None,
				"pay_basis": basis,
				"hourly_rate": amount if basis == "Hourly" else 0,
				"monthly_salary": amount if basis == "Monthly" else 0,
			}
		).insert()
		if name == "Bob Lin":
			employee.append(
				"hourly_rates",
				{"valid_from": get_first_day(today()), "pay_basis": "Hourly", "hourly_rate": BOB_RAISE},
			)
			employee.save()
		employees.append(employee.name)
		created += 1

	rng = random.Random(42)
	day, end = start, getdate(today())
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


def create_demo_users() -> int:
	"""One desk user per HR role, so learners can log in as each and compare."""
	created = 0
	for email, first_name, role in DEMO_USERS:
		if frappe.db.exists("User", email):
			continue
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": first_name, "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		user.add_roles(role)
		update_password(email, DEMO_PASSWORD)
		created += 1
	return created
