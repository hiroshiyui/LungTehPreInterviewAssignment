# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hr_cost.hr_cost.doctype.employee.employee import get_hourly_rate
from hr_cost.tests.utils import add_rate, make_employee, make_work_record


class IntegrationTestEmployee(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_title_is_employee_name(self):
		name = make_employee("  Test Dana  ", 300)
		self.assertTrue(name.startswith("EMP-"))
		self.assertEqual(frappe.db.get_value("Employee", name, "employee_name"), "Test Dana")

	def test_hourly_rate_must_be_positive(self):
		self.assertRaises(frappe.ValidationError, make_employee, "Test Zero", 0)

	def test_hourly_rate_seeds_the_base_rate(self):
		doc = frappe.get_doc("Employee", make_employee("Test Seed", 300))
		self.assertEqual([(r.valid_from, r.hourly_rate) for r in doc.hourly_rates], [(None, 300)])

	def test_hourly_rate_shows_the_latest_rate(self):
		employee = make_employee("Test Latest", 300)
		doc = add_rate(employee, "2001-06-01", 350)
		self.assertEqual(doc.hourly_rate, 350)

	def test_rate_depends_on_the_date(self):
		employee = make_employee("Test Dated", 300)
		add_rate(employee, "2001-06-01", 350)
		self.assertEqual(get_hourly_rate(employee, "2001-05-31"), 300)
		self.assertEqual(get_hourly_rate(employee, "2001-06-01"), 350)
		self.assertEqual(get_hourly_rate(employee, "2001-12-31"), 350)

	def test_no_rate_before_the_first_dated_rate(self):
		doc = frappe.get_doc(
			{
				"doctype": "Employee",
				"employee_name": "Test Hired Later",
				"hourly_rates": [{"valid_from": "2001-06-01", "hourly_rate": 300}],
			}
		).insert()
		self.assertIsNone(get_hourly_rate(doc.name, "2001-05-31"))
		self.assertRaises(frappe.ValidationError, make_work_record, doc.name, "2001-05-31", 8)

	def test_duplicate_dates_are_rejected(self):
		employee = make_employee("Test Duplicate", 300)
		add_rate(employee, "2001-06-01", 350)
		self.assertRaises(frappe.ValidationError, add_rate, employee, "2001-06-01", 360)

	def test_only_one_base_rate(self):
		employee = make_employee("Test Two Bases", 300)
		self.assertRaises(frappe.ValidationError, add_rate, employee, None, 310)

	def test_rates_in_the_history_must_be_positive(self):
		employee = make_employee("Test Zero Row", 300)
		self.assertRaises(frappe.ValidationError, add_rate, employee, "2001-06-01", 0)

	def test_hourly_rate_cannot_be_changed_directly(self):
		doc = frappe.get_doc("Employee", make_employee("Test Direct", 300))
		doc.hourly_rate = 400
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_correcting_a_rate_recosts_its_work_records(self):
		employee = make_employee("Test Typo", 30)  # meant to be 300
		record = make_work_record(employee, "2001-01-15", 8)
		self.assertEqual(record.cost, 240)

		doc = frappe.get_doc("Employee", employee)
		doc.hourly_rates[0].hourly_rate = 300
		doc.save()

		record.reload()
		self.assertEqual((record.hourly_rate, record.cost), (300, 2400))

	def test_a_raise_leaves_earlier_work_alone(self):
		employee = make_employee("Test Raise", 300)
		before = make_work_record(employee, "2001-01-15", 8)
		after = make_work_record(employee, "2001-02-15", 8)

		add_rate(employee, "2001-02-01", 400)

		before.reload()
		after.reload()
		self.assertEqual(before.cost, 2400)
		self.assertEqual(after.cost, 3200)

	def test_history_edit_that_leaves_work_without_a_rate_is_rejected(self):
		employee = make_employee("Test Orphan", 300)
		make_work_record(employee, "2001-01-15", 8)
		doc = frappe.get_doc("Employee", employee)
		doc.hourly_rates[0].valid_from = "2001-02-01"  # the base rate no longer covers January
		self.assertRaises(frappe.ValidationError, doc.save)
