# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from hr_cost.demo import DEMO_USERS, create_demo_data
from hr_cost.patches.v0_1 import seed_hourly_rate_history
from hr_cost.patches.v0_2 import set_pay_basis_and_joining_dates
from hr_cost.tests.utils import make_employee, make_work_record


class IntegrationTestDemoAndPatches(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_demo_data_is_idempotent(self):
		create_demo_data()  # creates the data, or finds it already provisioned
		self.assertEqual(create_demo_data(), {"created": 0})  # provisioning relies on this output

	def test_demo_users_have_one_hr_role_each(self):
		create_demo_data()
		for email, _first_name, role in DEMO_USERS:
			roles = set(frappe.get_roles(email)) - {"All", "Guest", "Desk User"}
			self.assertEqual(roles, {role}, email)

	def test_patch_seeds_a_base_rate_for_employees_without_history(self):
		employee = make_employee("Test Legacy", 275)
		frappe.db.delete("Employee Hourly Rate", {"parent": employee})  # as before the upgrade

		seed_hourly_rate_history.execute()
		seed_hourly_rate_history.execute()  # and a re-run adds nothing

		rows = frappe.get_all("Employee Hourly Rate", filters={"parent": employee}, fields=["valid_from", "hourly_rate"])
		self.assertEqual([(r.valid_from, r.hourly_rate) for r in rows], [(None, 275)])

	def test_patch_sets_hourly_pay_and_joining_dates(self):
		worked = make_employee("Test Legacy Worker", 275)
		make_work_record(worked, "2001-04-03", 8)
		idle = make_employee("Test Legacy Idle", 275)
		# As before the upgrade: no pay basis anywhere, and no joining dates.
		employee, pay = frappe.qb.DocType("Employee"), frappe.qb.DocType("Employee Hourly Rate")
		frappe.qb.update(employee).set(employee.pay_basis, None).where(employee.name == worked).run()
		frappe.qb.update(pay).set(pay.pay_basis, None).where(pay.parent == worked).run()
		frappe.db.set_value("Employee", [worked, idle], "date_of_joining", None, update_modified=False)

		set_pay_basis_and_joining_dates.execute()
		set_pay_basis_and_joining_dates.execute()  # and a re-run changes nothing

		self.assertEqual(frappe.db.get_value("Employee", worked, ["pay_basis", "date_of_joining"]), ("Hourly", getdate("2001-04-03")))
		self.assertEqual(frappe.get_all("Employee Hourly Rate", {"parent": worked}, pluck="pay_basis"), ["Hourly"])
		created = getdate(frappe.db.get_value("Employee", idle, "creation"))
		self.assertEqual(getdate(frappe.db.get_value("Employee", idle, "date_of_joining")), created)
