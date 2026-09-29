# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class Employee(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from hr_cost.hr_cost.doctype.employee_hourly_rate.employee_hourly_rate import EmployeeHourlyRate

		employee_name: DF.Data
		hourly_rate: DF.Currency
		hourly_rates: DF.Table[EmployeeHourlyRate]
	# end: auto-generated types

	_DOCTYPE_NAME = "Employee"

	def validate(self):
		self.employee_name = (self.employee_name or "").strip()
		self.seed_rate_history()
		self.validate_rate_history()
		# Hourly Rate is a read-only mirror of the latest rate in the history.
		self.hourly_rate = latest_rate(self.hourly_rates)

	def on_update(self):
		# A corrected or added rate re-costs the Work Records it applies to.
		# A new employee has no Work Records yet.
		if not self.flags.in_insert and self.rate_history_changed():
			recalculate_work_records(self.name, self.hourly_rates)

	def seed_rate_history(self):
		"""An employee created with just an Hourly Rate gets it as the base rate."""
		if not self.hourly_rates:
			if flt(self.hourly_rate) <= 0:
				frappe.throw(_("Hourly Rate must be greater than zero."))
			self.append("hourly_rates", {"valid_from": None, "hourly_rate": self.hourly_rate})
		elif (
			not self.is_new() and self.has_value_changed("hourly_rate") and not self.rate_history_changed()
		):
			frappe.throw(
				_(
					"Hourly Rate shows the latest rate from Hourly Rate History. To change it, "
					"add a row with the date the new rate starts."
				)
			)

	def validate_rate_history(self):
		seen = set()
		for row in self.hourly_rates:
			if flt(row.hourly_rate) <= 0:
				frappe.throw(_("Row {0}: Hourly Rate must be greater than zero.").format(row.idx))
			valid_from = getdate(row.valid_from) if row.valid_from else None
			if valid_from in seen:
				frappe.throw(
					_("Row {0}: there is already a base rate (empty Valid From).").format(row.idx)
					if valid_from is None
					else _("Row {0}: there is already a rate valid from {1}.").format(
						row.idx, frappe.format(valid_from, "Date")
					)
				)
			seen.add(valid_from)

	def rate_history_changed(self) -> bool:
		before = self.get_doc_before_save()
		return before is None or rate_signature(before.hourly_rates) != rate_signature(self.hourly_rates)


def rate_on(rates, on) -> float | None:
	"""The rate valid on `on`: the latest row whose Valid From is on or before
	that date. The base row (empty Valid From) applies before any dated row."""
	on = getdate(on)
	applicable = [row for row in rates if not row.valid_from or getdate(row.valid_from) <= on]
	if not applicable:
		return None
	return flt(max(applicable, key=_valid_from).hourly_rate)


def latest_rate(rates) -> float:
	return flt(max(rates, key=_valid_from).hourly_rate)


def _valid_from(row) -> datetime.date:
	return getdate(row.valid_from) if row.valid_from else datetime.date.min


def rate_signature(rates) -> list[tuple]:
	return sorted((str(row.valid_from or ""), flt(row.hourly_rate)) for row in rates)


def get_hourly_rate(employee: str, on) -> float | None:
	"""The employee's rate valid on the given date (None if none applies)."""
	rates = frappe.get_all(
		"Employee Hourly Rate",
		filters={"parenttype": "Employee", "parentfield": "hourly_rates", "parent": employee},
		fields=["valid_from", "hourly_rate"],
	)
	return rate_on(rates, on)


@frappe.whitelist()
def get_hourly_rate_on(employee: str, date: str) -> float | None:
	"""For the Work Record form's cost preview."""
	frappe.has_permission("Employee", "read", employee, throw=True)
	return get_hourly_rate(employee, date)


def recalculate_work_records(employee: str, rates) -> None:
	"""Re-cost the employee's Work Records after their rate history changed."""
	precision = frappe.get_precision("Work Record", "cost")
	records = frappe.get_all(
		"Work Record",
		filters={"employee": employee},
		fields=["name", "date", "hours_worked", "hourly_rate", "cost"],
	)
	for record in records:
		rate = rate_on(rates, record.date)
		if rate is None:
			frappe.throw(
				_(
					"Work Record {0} on {1} would have no hourly rate. Keep a base rate "
					"(empty Valid From) or a rate valid from that date or earlier."
				).format(record.name, frappe.format(record.date, "Date"))
			)
		cost = flt(flt(record.hours_worked) * rate, precision)
		if flt(record.hourly_rate) != rate or flt(record.cost) != cost:
			frappe.db.set_value("Work Record", record.name, {"hourly_rate": rate, "cost": cost})
