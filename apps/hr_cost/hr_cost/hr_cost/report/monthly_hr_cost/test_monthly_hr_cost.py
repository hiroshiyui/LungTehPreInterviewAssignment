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
		self.assertEqual(chart["data"]["labels"], ["Jan", "Feb", "Mar"])

	def test_totals_per_employee_per_month(self):
		_columns, rows, chart, summary = self.run_report()
		alice, bob = rows[self.alice], rows[self.bob]

		self.assertEqual((alice.m_2001_01, alice.m_2001_02, alice.m_2001_03), (800, 0, 1000))
		self.assertEqual((alice.hours_worked, alice.hr_cost), (18, 1800))
		# Each month uses the rate valid then: the March raise doesn't touch January.
		self.assertEqual((bob.m_2001_01, bob.m_2001_03), (800, 1200))
		self.assertEqual(bob.hr_cost, 2000)

		# The default chart stacks each month's bar by employee.
		self.assertEqual(chart["barOptions"], {"stacked": 1})
		self.assertEqual(
			[(d["name"], d["values"]) for d in chart["data"]["datasets"]],
			[("Test Alice", [800, 0, 1000]), ("Test Bob", [800, 0, 1200])],
		)
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

	def test_cost_share_chart(self):
		_columns, _rows, chart, _summary = self.run_report(chart="Cost Share")
		self.assertEqual(chart["type"], "donut")
		self.assertEqual(chart["data"]["labels"], ["Test Alice", "Test Bob"])
		self.assertEqual(chart["data"]["datasets"][0]["values"], [1800, 2000])

	def test_effective_hourly_rate_chart(self):
		_columns, _rows, chart, _summary = self.run_report(chart="Effective Hourly Rate")
		self.assertEqual(chart["type"], "line")
		# February had no work, so no rate. January: 1600 / 12 h; March, after
		# Bob's raise: 2200 / 14 h.
		self.assertEqual(chart["data"]["labels"], ["Jan", "Mar"])
		self.assertEqual(chart["data"]["datasets"][0]["values"], [133.33, 157.14])

	def test_unknown_chart(self):
		self.assertRaises(frappe.ValidationError, self.run_report, chart="Pie In The Sky")

	def test_month_over_month(self):
		# The latest month with work (March) against February, which had none.
		_columns, _rows, _chart, summary = self.run_report()
		self.assertEqual(summary["Mar 2001 vs Feb 2001"], 2200)
		# Without the previous month in the range there's nothing to compare.
		_columns, _rows, _chart, summary = self.run_report(from_date="2001-03-01")
		self.assertFalse([label for label in summary if " vs " in label])

	def test_chart_labels_show_the_year_when_the_range_spans_years(self):
		_columns, _rows, chart, _summary = self.run_report(from_date="2000-12-01")
		self.assertEqual(chart["data"]["labels"], ["Dec 00", "Jan 01", "Feb 01", "Mar 01"])
