# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hr_cost.tests.utils import make_employee, make_work_record

DAY = "2001-01-15"


class IntegrationTestWorkRecord(IntegrationTestCase):
	def setUp(self):
		self.employee = make_employee("Test Evan", 250)

	def tearDown(self):
		frappe.db.rollback()

	def test_cost_is_hours_times_rate(self):
		record = make_work_record(self.employee, DAY, 7.5)
		self.assertEqual(record.employee_name, "Test Evan")
		self.assertEqual(record.hourly_rate, 250)
		self.assertEqual(record.cost, 1875)

	def test_rate_change_does_not_rewrite_history(self):
		record = make_work_record(self.employee, DAY, 8)
		frappe.db.set_value("Employee", self.employee, "hourly_rate", 400)

		record.reload()
		record.hours_worked = 4
		record.save()
		self.assertEqual(record.hourly_rate, 250)
		self.assertEqual(record.cost, 1000)

		self.assertEqual(make_work_record(self.employee, "2001-01-16", 4).cost, 1600)

	def test_hours_must_be_positive(self):
		self.assertRaises(frappe.ValidationError, make_work_record, self.employee, DAY, 0)

	def test_at_most_24_hours_per_employee_per_day(self):
		make_work_record(self.employee, DAY, 16)
		self.assertRaises(frappe.ValidationError, make_work_record, self.employee, DAY, 9)
		make_work_record(self.employee, DAY, 8)  # exactly 24 is fine
