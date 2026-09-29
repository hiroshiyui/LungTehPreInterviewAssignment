# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hr_cost.hr_cost.report.monthly_hr_cost.monthly_hr_cost import execute
from hr_cost.tests.utils import add_rate, make_employee, make_work_record


class IntegrationTestMonthlyHRCost(IntegrationTestCase):
	def setUp(self):
		self.alice = make_employee("Test Alice", 100)
		self.bob = make_employee("Test Bob", 200)
		add_rate(self.bob, "2001-03-01", 300)  # a raise in March
		make_work_record(self.alice, "2001-01-31", 8)  # 800
		make_work_record(self.alice, "2001-03-01", 8)  # 800
		make_work_record(self.alice, "2001-03-15", 2)  # 200
		make_work_record(self.bob, "2001-01-10", 4)  # 800
		make_work_record(self.bob, "2001-03-10", 4)  # 1200, at the new rate
		make_work_record(self.bob, "2001-04-01", 8)  # outside the range below

	def tearDown(self):
		frappe.db.rollback()

	def run_report(self, **filters):
		filters = {"from_date": "2001-01-01", "to_date": "2001-03-31", **filters}
		columns, data, _message, chart, summary = execute(filters)
		return columns, {row.employee: row for row in data}, chart, {s["label"]: s["value"] for s in summary}

	def test_one_column_per_month_including_months_without_work(self):
		columns, _rows, chart, _summary = self.run_report()
		fields = [c["fieldname"] for c in columns]
		self.assertEqual(fields[2:5], ["m_2001_01", "m_2001_02", "m_2001_03"])
		self.assertEqual(chart["data"]["labels"], ["Jan 2001", "Feb 2001", "Mar 2001"])

	def test_totals_per_employee_per_month(self):
		_columns, rows, chart, summary = self.run_report()
		alice, bob = rows[self.alice], rows[self.bob]

		self.assertEqual((alice.m_2001_01, alice.m_2001_02, alice.m_2001_03), (800, 0, 1000))
		self.assertEqual((alice.hours_worked, alice.hr_cost), (18, 1800))
		# Each month uses the rate valid then: the March raise doesn't touch January.
		self.assertEqual((bob.m_2001_01, bob.m_2001_03), (800, 1200))
		self.assertEqual(bob.hr_cost, 2000)

		self.assertEqual(chart["data"]["datasets"][0]["values"], [1600, 0, 2200])
		self.assertEqual(summary["Total HR Cost"], 3800)
		self.assertEqual(summary["Employees"], 2)
		self.assertEqual(summary["Average HR Cost / Month"], 1900)  # February had no work

	def test_shows_the_employees_current_name(self):
		frappe.db.set_value("Employee", self.alice, "employee_name", "Test Alice Renamed")
		_columns, rows, _chart, _summary = self.run_report()
		self.assertEqual(rows[self.alice].employee_name, "Test Alice Renamed")

	def test_employee_filter(self):
		_columns, rows, _chart, summary = self.run_report(employee=self.bob)
		self.assertEqual(list(rows), [self.bob])
		self.assertEqual(summary["Total HR Cost"], 2000)

	def test_a_partial_month_counts_only_the_days_in_range(self):
		_columns, rows, _chart, _summary = self.run_report(from_date="2001-03-10", to_date="2001-03-31")
		self.assertEqual(rows[self.alice].m_2001_03, 200)
		self.assertEqual(rows[self.bob].m_2001_03, 1200)

	def test_empty_range(self):
		_columns, rows, chart, summary = self.run_report(from_date="1990-01-01", to_date="1990-12-31")
		self.assertEqual(rows, {})
		self.assertIsNone(chart)
		self.assertEqual(summary["Total HR Cost"], 0)

	def test_invalid_range(self):
		self.assertRaises(frappe.ValidationError, execute, {"from_date": "2001-02-01", "to_date": "2001-01-31"})
