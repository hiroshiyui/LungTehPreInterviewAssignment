# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from hr_cost.hr_cost.doctype.employee.employee import get_hourly_rate, get_salary_costs, work_permit_notice
from hr_cost.tests.utils import add_rate, add_salary, make_employee, make_work_record


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
				"date_of_joining": "2000-01-01",
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

	def test_renaming_updates_the_name_on_work_records(self):
		employee = make_employee("Test Gina", 300)
		record = make_work_record(employee, "2001-06-01", 8)
		doc = frappe.get_doc("Employee", employee)
		doc.employee_name = "Test Gina Renamed"
		doc.save()
		self.assertEqual(frappe.db.get_value("Work Record", record.name, "employee_name"), "Test Gina Renamed")

	def test_a_namesake_is_allowed_with_a_warning(self):
		first = make_employee("Test Hana", 300)
		frappe.clear_messages()
		second = make_employee("Test Hana", 310)
		self.assertNotEqual(first, second)
		self.assertIn(first, " ".join(m.get("message", "") for m in map(frappe.parse_json, frappe.message_log)))

	def test_monthly_pay_mirrors_the_salary(self):
		doc = frappe.get_doc("Employee", make_employee("Test Ivy", monthly_salary=36000))
		self.assertEqual((doc.pay_basis, doc.monthly_salary, doc.hourly_rate), ("Monthly", 36000, 0))
		self.assertEqual(
			[(r.valid_from, r.pay_basis, r.monthly_salary) for r in doc.hourly_rates], [(None, "Monthly", 36000)]
		)

	def test_monthly_salary_must_be_positive(self):
		self.assertRaises(frappe.ValidationError, make_employee, "Test Zero Salary", monthly_salary=0)

	def test_a_contract_change_to_monthly_pay_recosts_later_work_only(self):
		employee = make_employee("Test Jay", 200)
		before = make_work_record(employee, "2001-07-10", 8)
		after = make_work_record(employee, "2001-07-20", 8)
		doc = add_salary(employee, "2001-07-15", 36000)
		self.assertEqual((doc.pay_basis, doc.monthly_salary, doc.hourly_rate), ("Monthly", 36000, 0))
		self.assertEqual(frappe.db.get_value("Work Record", before.name, "cost"), 1600)
		# Under monthly pay the salary covers the hours: the record costs nothing extra.
		self.assertEqual(frappe.db.get_value("Work Record", after.name, ["hourly_rate", "cost"]), (0, 0))

	def test_relieving_date_cannot_precede_joining(self):
		self.assertRaises(
			frappe.ValidationError,
			make_employee,
			"Test Kim",
			200,
			date_of_joining="2001-02-01",
			relieving_date="2001-01-31",
		)

	def test_employment_dates_must_cover_recorded_work(self):
		employee = make_employee("Test Lee", 200)
		make_work_record(employee, "2001-03-10", 8)
		doc = frappe.get_doc("Employee", employee)
		doc.date_of_joining = "2001-03-11"
		self.assertRaises(frappe.ValidationError, doc.save)
		doc.reload()
		doc.relieving_date = "2001-03-09"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_salary_accrues_a_thirtieth_per_day_while_employed(self):
		monthly = make_employee(
			"Test Mia", monthly_salary=30000, date_of_joining="2001-01-10", relieving_date="2001-01-12"
		)
		hourly = make_employee("Test Ned", 200)
		employees = frappe.get_all(
			"Employee", {"name": ["in", [monthly, hourly]]}, ["name", "date_of_joining", "relieving_date"]
		)
		costs = get_salary_costs(employees, "2001-01-01", "2001-01-31")
		self.assertEqual(list(costs), [monthly])  # hourly pay accrues nothing
		self.assertEqual(
			costs[monthly],
			{getdate("2001-01-10"): 1000, getdate("2001-01-11"): 1000, getdate("2001-01-12"): 1000},
		)

	def test_salary_follows_the_pay_history(self):
		# Hourly until the 15th, then monthly: salary accrues from the 15th only.
		employee = make_employee("Test Oli", 200)
		add_salary(employee, "2001-01-15", 30000)
		employees = frappe.get_all("Employee", {"name": employee}, ["name", "date_of_joining", "relieving_date"])
		days = get_salary_costs(employees, "2001-01-01", "2001-01-31")[employee]
		self.assertEqual((min(days), max(days), len(days)), (getdate("2001-01-15"), getdate("2001-01-31"), 17))

	def test_salary_does_not_accrue_in_the_future(self):
		employee = make_employee("Test Pia", monthly_salary=30000)
		employees = frappe.get_all("Employee", {"name": employee}, ["name", "date_of_joining", "relieving_date"])
		days = get_salary_costs(employees, add_days(today(), -2), add_days(today(), 10))[employee]
		self.assertEqual(max(days), getdate(today()))
		self.assertEqual(len(days), 3)

	def test_names_in_other_writing_systems(self):
		employee = make_employee(
			"Somchai Jaidee",
			200,
			nationality="Thailand",
			other_names=[
				{"writing_system": "Thai", "other_name": "สมชาย ใจดี"},
				{"writing_system": "Chinese", "other_name": "宋猜"},
			],
		)
		doc = frappe.get_doc("Employee", employee)
		self.assertEqual(doc.nationality, "Thailand")
		self.assertEqual([(r.writing_system, r.other_name) for r in doc.other_names], [("Thai", "สมชาย ใจดี"), ("Chinese", "宋猜")])

	def test_work_permit_notice(self):
		self.assertIn("expired", work_permit_notice(add_days(today(), -1)))
		self.assertIn("in 30 days", work_permit_notice(add_days(today(), 30)))
		self.assertIsNone(work_permit_notice(add_days(today(), 31)))
		self.assertIsNone(work_permit_notice(None))
		# No longer employed: no reminder.
		self.assertIsNone(work_permit_notice(add_days(today(), -1), relieving_date=add_days(today(), -5)))

	def test_saving_warns_about_an_expiring_work_permit(self):
		frappe.clear_messages()
		make_employee("Test Permit", 200, work_permit_expiry=add_days(today(), 10))
		self.assertIn("in 10 days", " ".join(str(m) for m in frappe.message_log))
