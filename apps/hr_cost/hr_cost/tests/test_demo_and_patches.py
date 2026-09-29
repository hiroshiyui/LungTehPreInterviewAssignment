# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hr_cost.demo import create_demo_data
from hr_cost.patches.v0_1 import seed_hourly_rate_history
from hr_cost.tests.utils import make_employee


class IntegrationTestDemoAndPatches(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_demo_data_is_idempotent(self):
		create_demo_data()  # creates the data, or finds it already provisioned
		self.assertEqual(create_demo_data(), {"created": 0})  # provisioning relies on this output

	def test_patch_seeds_a_base_rate_for_employees_without_history(self):
		employee = make_employee("Test Legacy", 275)
		frappe.db.delete("Employee Hourly Rate", {"parent": employee})  # as before the upgrade

		seed_hourly_rate_history.execute()
		seed_hourly_rate_history.execute()  # and a re-run adds nothing

		rows = frappe.get_all("Employee Hourly Rate", filters={"parent": employee}, fields=["valid_from", "hourly_rate"])
		self.assertEqual([(r.valid_from, r.hourly_rate) for r in rows], [(None, 275)])
