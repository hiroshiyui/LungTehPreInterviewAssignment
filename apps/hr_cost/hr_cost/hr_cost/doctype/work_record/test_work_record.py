# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from hr_cost.tests.utils import add_rate, make_employee, make_work_record

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

	def test_backdated_record_uses_the_rate_of_its_date(self):
		add_rate(self.employee, "2001-01-16", 400)  # the raise is recorded first...
		record = make_work_record(self.employee, DAY, 8)  # ...then earlier work is entered
		self.assertEqual((record.hourly_rate, record.cost), (250, 2000))
		self.assertEqual(make_work_record(self.employee, "2001-01-16", 8).cost, 3200)

	def test_moving_a_record_to_another_employee_rerates_it(self):
		other = make_employee("Test Frida", 300)
		record = make_work_record(self.employee, DAY, 8)
		record.employee = other
		record.save()
		self.assertEqual((record.hourly_rate, record.cost), (300, 2400))

	def test_changing_the_date_rerates_the_record(self):
		add_rate(self.employee, "2001-02-01", 400)
		record = make_work_record(self.employee, DAY, 8)
		record.date = "2001-02-15"
		record.save()
		self.assertEqual(record.cost, 3200)

	def test_hours_must_be_positive(self):
		self.assertRaises(frappe.ValidationError, make_work_record, self.employee, DAY, 0)

	def test_date_cannot_be_in_the_future(self):
		self.assertRaises(frappe.ValidationError, make_work_record, self.employee, add_days(today(), 1), 8)
		make_work_record(self.employee, today(), 8)  # today itself is fine

	def test_at_most_24_hours_per_employee_per_day(self):
		make_work_record(self.employee, DAY, 16)
		self.assertRaises(frappe.ValidationError, make_work_record, self.employee, DAY, 9)
		make_work_record(self.employee, DAY, 8)  # exactly 24 is fine

	def test_editing_a_record_does_not_count_its_own_hours(self):
		record = make_work_record(self.employee, DAY, 16)
		record.hours_worked = 20  # 20, not 16 + 20
		record.save()
		self.assertEqual(record.hours_worked, 20)

	def test_employee_and_date_are_indexed(self):
		# Named by us in on_doctype_update.
		self.assertTrue(frappe.db.has_index("tabWork Record", "employee_date_index"))
		# From search_index in the JSON. Frappe names it "date" when it creates the
		# table and "date_index" when it adds it to an existing one, so check the
		# column rather than the name.
		leading_date = frappe.db.sql(
			"SHOW INDEX FROM `tabWork Record` WHERE Column_name = 'date' AND Seq_in_index = 1"
		)
		self.assertTrue(leading_date)
