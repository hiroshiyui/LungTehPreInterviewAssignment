# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hr_cost.setup import complete_site_setup

ANSWERS = {"language": "English", "country": "Taiwan", "timezone": "Asia/Taipei", "currency": "TWD"}


class IntegrationTestSetup(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_answers_a_wizard_that_frappe_skipped(self):
		# As after Frappe marked the wizard complete on its own: no answers.
		frappe.db.set_single_value("System Settings", {"country": None, "currency": None, "time_zone": None})
		self.assertEqual(complete_site_setup(**ANSWERS), {"changed": 1})
		settings = frappe.get_single("System Settings")
		self.assertEqual((settings.country, settings.currency, settings.time_zone), ("Taiwan", "TWD", "Asia/Taipei"))
		self.assertEqual(complete_site_setup(**ANSWERS), {"changed": 0})  # provisioning relies on this output
