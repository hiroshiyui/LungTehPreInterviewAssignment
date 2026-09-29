# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import subprocess

import frappe
from frappe.tests import IntegrationTestCase

from hr_cost.hr_cost.report.pdf import build_report_html, download_report_pdf
from hr_cost.tests.utils import make_employee, make_user, make_work_record

RANGE = {"from_date": "2001-08-01", "to_date": "2001-08-31"}


class IntegrationTestReportPDF(IntegrationTestCase):
	def setUp(self):
		self.hr_manager = make_user("test-pdf-manager@example.com", "HR Manager")
		self.hr_user = make_user("test-pdf-user@example.com", "HR User")
		self.alice = make_employee("Test Alice", 100)
		make_work_record(self.alice, "2001-08-01", 8)  # 800
		make_work_record(self.alice, "2001-08-02", 2)  # 200

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for user in (self.hr_manager, self.hr_user):
			frappe.clear_cache(user=user)

	def test_daily_report_page(self):
		with self.set_user(self.hr_manager):
			html, filename, orientation = build_report_html("Daily HR Cost", RANGE)
		self.assertEqual((filename, orientation), ("Daily HR Cost 2001-08-01 to 2001-08-31.pdf", "Portrait"))
		self.assertIn("<h1>Daily HR Cost</h1>", html)
		self.assertIn("Hourly Wages", html)
		# The total row adds up the money and hours columns.
		total = html[html.index('class="total"') :]
		self.assertIn("1,000.00", total)
		self.assertIn(">10.00<", total)

	def test_monthly_report_is_landscape_and_names_the_employee(self):
		with self.set_user(self.hr_manager):
			html, filename, orientation = build_report_html(
				"Monthly HR Cost", {**RANGE, "employee": self.alice}
			)
		self.assertEqual(orientation, "Landscape")
		self.assertEqual(filename, f"Monthly HR Cost 2001-08-01 to 2001-08-31 {self.alice}.pdf")
		self.assertIn("Test Alice", html)
		self.assertIn("Aug 2001", html)

	def test_values_are_escaped(self):
		make_employee("<b>Test Mallory</b>", 100)
		html, _filename, _orientation = build_report_html("Monthly HR Cost", {**RANGE, "to_date": "2001-08-31"})
		self.assertNotIn("<b>Test Mallory</b>", html)

	def test_only_report_readers_may_download(self):
		with self.set_user(self.hr_user):
			self.assertRaises(frappe.PermissionError, build_report_html, "Daily HR Cost", RANGE)
		self.assertRaises(frappe.ValidationError, build_report_html, "Error Log", RANGE)

	def test_renders_a_pdf(self):
		# Needs wkhtmltopdf, which the base role installs.
		with self.set_user(self.hr_manager):
			download_report_pdf("Monthly HR Cost", frappe.as_json(RANGE))
		self.assertEqual(frappe.local.response.type, "download")  # an attachment, not inline
		self.assertTrue(frappe.local.response.filecontent.startswith(b"%PDF"))

	def test_server_has_fonts_for_employees_names(self):
		# PDFs are drawn on the server: a name in a script it has no font for
		# prints as empty boxes. Employees come from many countries, especially
		# Southeast Asia. (fontconfig language codes; the base role installs Noto.)
		for lang in ("zh-tw", "vi", "id", "tl", "th", "my", "km", "lo"):
			with self.subTest(lang=lang):
				fonts = subprocess.run(["fc-list", f":lang={lang}"], capture_output=True, text=True).stdout
				self.assertTrue(fonts.strip(), f"no font for {lang}")

	def test_names_the_nationality_filter(self):
		frappe.db.set_value("Employee", self.alice, "nationality", "Philippines")
		html, _filename, _orientation = build_report_html("Daily HR Cost", {**RANGE, "nationality": "Philippines"})
		self.assertIn("Philippines", html[: html.index("<table")])
