# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

"""Who sees pay. Rates and costs are at permlevel 1, which only HR Manager can
read. HR User enters work records without seeing them, and System Manager
administers the site without them."""

import frappe
from frappe.desk.query_report import run as run_report
from frappe.tests import IntegrationTestCase

from hr_cost.hr_cost.doctype.employee.employee import get_hourly_rate_on
from hr_cost.hr_cost.report.daily_hr_cost import daily_hr_cost
from hr_cost.hr_cost.report.monthly_hr_cost import monthly_hr_cost
from hr_cost.tests.utils import make_employee, make_user, make_work_record

DAY = "2001-05-02"
RANGE = {"from_date": "2001-05-01", "to_date": "2001-05-31"}
REPORTS = {"Daily HR Cost": daily_hr_cost.execute, "Monthly HR Cost": monthly_hr_cost.execute}


class IntegrationTestPermissions(IntegrationTestCase):
	def setUp(self):
		self.hr_manager = make_user("test-hr-manager@example.com", "HR Manager")
		self.hr_user = make_user("test-hr-user@example.com", "HR User")
		self.system_manager = make_user("test-system-manager@example.com", "System Manager")
		self.alice = make_employee("Test Alice", 100)
		self.bob = make_employee("Test Bob", 200)
		make_work_record(self.alice, DAY, 8)  # 800
		make_work_record(self.bob, DAY, 4)  # 800

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for user in (self.hr_manager, self.hr_user, self.system_manager):
			frappe.clear_cache(user=user)  # cached roles / User Permissions outlive the rollback

	def test_hr_user_enters_work_but_cannot_set_or_see_its_cost(self):
		with self.set_user(self.hr_user):
			record = frappe.get_doc(
				{"doctype": "Work Record", "employee": self.alice, "date": "2001-05-03", "hours_worked": 2, "cost": 1}
			).insert()
			visible = frappe.get_list("Work Record", filters={"name": record.name}, fields=["name", "cost"])
		# The server discarded the submitted cost and costed the record itself.
		self.assertEqual(frappe.db.get_value("Work Record", record.name, "cost"), 200)
		self.assertEqual(visible, [{"name": record.name}])

	def test_hr_user_sees_employees_but_not_their_rates(self):
		with self.set_user(self.hr_user):
			employees = frappe.get_list("Employee", filters={"name": self.alice}, fields=["name", "hourly_rate"])
			self.assertEqual(employees, [{"name": self.alice}])
			self.assertRaises(frappe.PermissionError, get_hourly_rate_on, self.alice, DAY)
			self.assertRaises(frappe.PermissionError, make_employee, "Test Carol", 300)

	def test_system_manager_cannot_see_rates_or_create_employees(self):
		with self.set_user(self.system_manager):
			employees = frappe.get_list("Employee", filters={"name": self.alice}, fields=["name", "hourly_rate"])
			self.assertEqual(employees, [{"name": self.alice}])
			self.assertRaises(frappe.PermissionError, get_hourly_rate_on, self.alice, DAY)
			# A new employee needs a rate, which this role can't set.
			self.assertRaises(frappe.PermissionError, make_employee, "Test Carol", 300)

	def test_hr_manager_sees_rates(self):
		with self.set_user(self.hr_manager):
			self.assertEqual(get_hourly_rate_on(self.alice, DAY), 100)

	def test_only_hr_manager_may_run_the_reports(self):
		# Two independent locks; each is checked on its own.
		for report, execute in REPORTS.items():
			for user in (self.hr_user, self.system_manager):
				with self.subTest(report=report, user=user):
					# 1. The Report's roles keep them out of the desk page...
					self.assertFalse(frappe.get_doc("Report", report).is_permitted(user))
					# 2. ...and the query itself refuses `cost`, even called directly.
					with self.set_user(user):
						self.assertRaises(frappe.PermissionError, run_report, report, filters=RANGE)
						self.assertRaises(frappe.PermissionError, execute, RANGE)
			with self.subTest(report=report, user=self.hr_manager), self.set_user(self.hr_manager):
				self.assertTrue(frappe.get_doc("Report", report).is_permitted(self.hr_manager))
				self.assertTrue(run_report(report, filters=RANGE)["result"])

	def test_reports_honour_user_permissions(self):
		# An HR Manager restricted to Bob sees only Bob's cost.
		frappe.get_doc(
			{"doctype": "User Permission", "user": self.hr_manager, "allow": "Employee", "for_value": self.bob}
		).insert()
		with self.set_user(self.hr_manager):
			_columns, daily, *_rest = daily_hr_cost.execute(RANGE)
			_columns, monthly, *_rest = monthly_hr_cost.execute(RANGE)
		self.assertEqual([(row.hr_cost, row.employees) for row in daily], [(800, 1)])
		self.assertEqual([row.employee for row in monthly], [self.bob])

	def test_workspace_plots_go_through_the_reports(self):
		# Every chart and card reads one of the permission-aware reports, so it
		# inherits their roles and checks; none queries Work Record directly.
		reports = set(REPORTS)
		charts = frappe.get_all("Dashboard Chart", {"module": "HR Cost"}, ["name", "chart_type", "report_name"])
		cards = frappe.get_all("Number Card", {"module": "HR Cost"}, ["name", "type", "report_name"])
		self.assertTrue(charts and cards)
		for chart in charts:
			self.assertEqual((chart.chart_type, chart.report_name in reports), ("Report", True), chart.name)
			roles = frappe.get_all("Has Role", {"parenttype": "Dashboard Chart", "parent": chart.name}, pluck="role")
			self.assertEqual(roles, ["HR Manager"], chart.name)
		for card in cards:
			self.assertEqual((card.type, card.report_name in reports), ("Report", True), card.name)

		workspace = frappe.get_doc("Workspace", "HR Cost")
		self.assertEqual([r.role for r in workspace.roles], ["HR Manager"])
		self.assertEqual({c.chart_name for c in workspace.charts}, {c.name for c in charts})
		self.assertEqual({c.number_card_name for c in workspace.number_cards}, {c.name for c in cards})
