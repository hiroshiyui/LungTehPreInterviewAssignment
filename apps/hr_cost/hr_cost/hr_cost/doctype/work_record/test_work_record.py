# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import os
import tempfile
from unittest.mock import patch

import frappe
from frappe.core.doctype.data_import.importer import Importer
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

	def test_data_import_goes_through_the_same_rules(self):
		# Bulk logging via Data Import inserts each row like the form does: the
		# server costs it (a Cost column is ignored), and the 24 h cap holds.
		rows = [
			"Employee,Date,Hours Worked,Cost",
			f"{self.employee},2001-01-20,8,1",
			f"{self.employee},2001-01-20,20,1",  # 28 h on one day: refused
		]
		with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
			f.write("\n".join(rows))
		try:
			data_import = frappe.new_doc("Data Import")
			data_import.update({"reference_doctype": "Work Record", "import_type": "Insert New Records"})
			# console=True reads a local path, as `bench data-import` does; the Desk
			# passes an uploaded File instead, through the same insert logic.
			# The Importer commits after each good row and rolls back after a bad
			# one. Keep it all inside the test's transaction, so tearDown's rollback
			# still removes everything. (The bad row fails in validate(), before
			# anything is written, so skipping its rollback loses nothing.)
			with patch.object(frappe.db, "commit"), patch.object(frappe.db, "rollback"):
				Importer("Work Record", file_path=f.name, data_import=data_import, console=True).import_data()
		finally:
			os.unlink(f.name)
		imported = frappe.get_all("Work Record", {"employee": self.employee, "date": "2001-01-20"}, ["hours_worked", "cost"])
		self.assertEqual([(r.hours_worked, r.cost) for r in imported], [(8, 2000)])

	def test_monthly_paid_work_logs_hours_only(self):
		monthly = make_employee("Test Pat", monthly_salary=36000)
		record = make_work_record(monthly, DAY, 9)
		self.assertEqual((record.hours_worked, record.hourly_rate, record.cost), (9, 0, 0))

	def test_date_must_be_within_employment(self):
		employee = make_employee("Test Quinn", 200, date_of_joining="2001-01-10", relieving_date="2001-01-20")
		self.assertRaises(frappe.ValidationError, make_work_record, employee, "2001-01-09", 8)
		self.assertRaises(frappe.ValidationError, make_work_record, employee, "2001-01-21", 8)
		make_work_record(employee, "2001-01-10", 8)  # the first and last days are fine
		make_work_record(employee, "2001-01-20", 8)

	def test_work_after_the_permit_expired_is_recorded_with_a_warning(self):
		employee = make_employee("Test Rizal", 200, work_permit_expiry="2001-01-14")
		frappe.clear_messages()
		record = make_work_record(employee, DAY, 8)  # the 15th
		self.assertEqual(record.cost, 1600)
		self.assertIn("work permit expired", " ".join(str(m) for m in frappe.message_log))
