# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hr_cost.tests.utils import make_employee


class IntegrationTestEmployee(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_title_is_employee_name(self):
		name = make_employee("  Test Dana  ", 300)
		self.assertTrue(name.startswith("EMP-"))
		self.assertEqual(frappe.db.get_value("Employee", name, "employee_name"), "Test Dana")

	def test_hourly_rate_must_be_positive(self):
		self.assertRaises(frappe.ValidationError, make_employee, "Test Zero", 0)
