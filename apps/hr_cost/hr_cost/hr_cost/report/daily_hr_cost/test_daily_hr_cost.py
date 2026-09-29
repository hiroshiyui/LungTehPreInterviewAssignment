# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from hr_cost.hr_cost.report.daily_hr_cost.daily_hr_cost import execute
from hr_cost.tests.utils import make_employee, make_work_record


class IntegrationTestDailyHRCost(IntegrationTestCase):
	def setUp(self):
		self.alice = make_employee("Test Alice", 100)
		self.bob = make_employee("Test Bob", 200)
		make_work_record(self.alice, "2001-02-01", 8)  # 800
		make_work_record(self.bob, "2001-02-01", 4)  # 800
		make_work_record(self.alice, "2001-02-02", 2)  # 200
		make_work_record(self.bob, "2001-03-01", 8)  # outside the range below

	def tearDown(self):
		frappe.db.rollback()

	def run_report(self, **filters):
		filters = {"from_date": "2001-02-01", "to_date": "2001-02-28", **filters}
		_columns, data, _message, chart, summary = execute(filters)
		return data, chart, {s["label"]: s["value"] for s in summary}

	def test_totals_per_day(self):
		data, chart, summary = self.run_report()
		rows = {row.date: row for row in data}

		self.assertEqual(list(rows), [getdate("2001-02-01"), getdate("2001-02-02")])
		self.assertEqual(rows[getdate("2001-02-01")].hr_cost, 1600)
		self.assertEqual(rows[getdate("2001-02-01")].hours_worked, 12)
		self.assertEqual(rows[getdate("2001-02-01")].employees, 2)
		self.assertEqual(rows[getdate("2001-02-02")].hr_cost, 200)

		self.assertEqual(chart["data"]["datasets"][0]["values"], [1600, 200])
		self.assertEqual(summary["Total HR Cost"], 1800)
		self.assertEqual(summary["Days With Work"], 2)

	def test_employee_filter(self):
		data, _chart, summary = self.run_report(employee=self.bob)
		self.assertEqual(len(data), 1)
		self.assertEqual(summary["Total HR Cost"], 800)

	def test_empty_range(self):
		data, chart, summary = self.run_report(from_date="1990-01-01", to_date="1990-01-31")
		self.assertEqual(data, [])
		self.assertIsNone(chart)
		self.assertEqual(summary["Total HR Cost"], 0)

	def test_invalid_range(self):
		self.assertRaises(frappe.ValidationError, execute, {"from_date": "2001-02-02", "to_date": "2001-02-01"})

	def test_show_empty_days_fills_the_range_with_zero_rows(self):
		data, chart, summary = self.run_report(to_date="2001-02-04", show_empty_days=1)
		self.assertEqual([row.date for row in data], [getdate(f"2001-02-0{d}") for d in range(1, 5)])
		self.assertEqual([row.hr_cost for row in data], [1600, 200, 0, 0])
		self.assertEqual(chart["data"]["datasets"][0]["values"], [1600, 200, 0, 0])
		self.assertEqual(summary["Days With Work"], 2)  # zero rows don't count
		self.assertEqual(summary["Average HR Cost / Day"], 900)

	def test_chart_picker(self):
		expected = {
			"HR Cost": ("bar", [1600, 200]),
			"Hours Worked": ("bar", [12, 2]),
			"Employees at Work": ("line", [2, 1]),
		}
		for name, (chart_type, values) in expected.items():
			with self.subTest(chart=name):
				_data, chart, _summary = self.run_report(chart=name)
				self.assertEqual((chart["type"], chart["data"]["datasets"][0]["values"]), (chart_type, values))
		self.assertRaises(frappe.ValidationError, self.run_report, chart="Pie In The Sky")

	def test_chart_labels_are_short(self):
		_data, chart, _summary = self.run_report()
		self.assertEqual(chart["data"]["labels"], ["01", "02"])  # one month: the day
		_data, chart, _summary = self.run_report(to_date="2001-03-31")
		self.assertEqual(chart["data"]["labels"], ["02-01", "02-02", "03-01"])
