# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate, today


class Employee(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from hr_cost.hr_cost.doctype.employee_hourly_rate.employee_hourly_rate import EmployeeHourlyRate
		from hr_cost.hr_cost.doctype.employee_other_name.employee_other_name import EmployeeOtherName

		date_of_joining: DF.Date
		employee_name: DF.Data
		hourly_rate: DF.Currency
		hourly_rates: DF.Table[EmployeeHourlyRate]
		monthly_salary: DF.Currency
		nationality: DF.Link | None
		other_names: DF.Table[EmployeeOtherName]
		pay_basis: DF.Literal["Hourly", "Monthly"]
		relieving_date: DF.Date | None
		work_permit_expiry: DF.Date | None
		work_permit_number: DF.Data | None
	# end: auto-generated types

	_DOCTYPE_NAME = "Employee"

	def validate(self):
		self.employee_name = (self.employee_name or "").strip()
		self.warn_about_namesakes()
		self.validate_employment_dates()
		self.warn_about_work_permit()
		self.seed_pay_history()
		self.validate_pay_history()
		# Pay Basis, Hourly Rate and Monthly Salary are read-only mirrors of the
		# latest row of the Pay History.
		latest = latest_pay(self.hourly_rates)
		self.pay_basis = latest.pay_basis
		self.hourly_rate = flt(latest.hourly_rate) if latest.pay_basis == HOURLY else 0
		self.monthly_salary = flt(latest.monthly_salary) if latest.pay_basis == MONTHLY else 0

	def on_update(self):
		# Corrected or added pay terms re-cost the Work Records they apply to.
		# A new employee has no Work Records yet.
		if not self.flags.in_insert and self.pay_history_changed():
			recalculate_work_records(self.name, self.hourly_rates)
		# Work Record keeps a copy of the name (the assignment's "Employee Name"
		# field), fetched when the record is saved. Keep the copies current.
		if not self.flags.in_insert and self.has_value_changed("employee_name"):
			work_record = frappe.qb.DocType("Work Record")
			(
				frappe.qb.update(work_record)
				.set(work_record.employee_name, self.employee_name)
				.where(work_record.employee == self.name)
			).run()

	def warn_about_namesakes(self):
		"""Two employees may share a name, but it's usually a mistake, and pickers
		then tell them apart only by ID. Warn; don't refuse."""
		if not (self.is_new() or self.has_value_changed("employee_name")):
			return
		namesakes = frappe.get_all(
			"Employee",
			filters={"employee_name": self.employee_name, "name": ["!=", self.name or ""]},
			pluck="name",
		)
		if namesakes:
			frappe.msgprint(
				_("{0} is also the name of {1}. Pickers show the ID (EMP-…) to tell them apart.").format(
					frappe.bold(self.employee_name), ", ".join(namesakes)
				),
				indicator="orange",
				alert=True,
			)

	def warn_about_work_permit(self):
		"""Foreign staff need a valid work permit. Warn on every save while it
		expires within WORK_PERMIT_NOTICE_DAYS, or has expired; don't refuse:
		what happens next is HR's decision."""
		if message := work_permit_notice(self.work_permit_expiry, self.relieving_date):
			frappe.msgprint(message, indicator="orange", alert=True)

	def validate_employment_dates(self):
		if self.relieving_date and getdate(self.relieving_date) < getdate(self.date_of_joining):
			frappe.throw(_("Relieving Date cannot be before Date of Joining."))
		if self.is_new():
			return
		# Work already recorded must stay inside the employment.
		outside = [["date", "<", self.date_of_joining]]
		if self.relieving_date:
			outside.append(["date", ">", self.relieving_date])
		for condition in outside:
			if record := frappe.get_all(
				"Work Record", filters=[["employee", "=", self.name], condition], pluck="name", limit=1
			):
				frappe.throw(
					_("Work Record {0} is outside these employment dates.").format(record[0])
				)

	def seed_pay_history(self):
		"""A new employee created with just a pay basis and an amount gets them
		as the base row of the Pay History."""
		if not self.hourly_rates:
			basis = self.pay_basis or HOURLY
			amount = flt(self.hourly_rate if basis == HOURLY else self.monthly_salary)
			if amount <= 0:
				frappe.throw(
					_("Hourly Rate must be greater than zero.")
					if basis == HOURLY
					else _("Monthly Salary must be greater than zero.")
				)
			self.append(
				"hourly_rates",
				{
					"valid_from": None,
					"pay_basis": basis,
					"hourly_rate": amount if basis == HOURLY else 0,
					"monthly_salary": amount if basis == MONTHLY else 0,
				},
			)
		elif (
			not self.is_new()
			and any(self.has_value_changed(f) for f in ("pay_basis", "hourly_rate", "monthly_salary"))
			and not self.pay_history_changed()
		):
			frappe.throw(
				_(
					"Pay Basis, Hourly Rate and Monthly Salary show the latest row of the Pay "
					"History. To change pay, add a row with the date the new terms start."
				)
			)

	def validate_pay_history(self):
		seen = set()
		for row in self.hourly_rates:
			row.pay_basis = row.pay_basis or HOURLY
			if row.pay_basis == HOURLY:
				if flt(row.hourly_rate) <= 0:
					frappe.throw(_("Row {0}: Hourly Rate must be greater than zero.").format(row.idx))
				row.monthly_salary = 0
			else:
				if flt(row.monthly_salary) <= 0:
					frappe.throw(_("Row {0}: Monthly Salary must be greater than zero.").format(row.idx))
				row.hourly_rate = 0
			valid_from = getdate(row.valid_from) if row.valid_from else None
			if valid_from in seen:
				frappe.throw(
					_("Row {0}: there is already a base row (empty Valid From).").format(row.idx)
					if valid_from is None
					else _("Row {0}: there is already a row valid from {1}.").format(
						row.idx, frappe.format(valid_from, "Date")
					)
				)
			seen.add(valid_from)

	def pay_history_changed(self) -> bool:
		before = self.get_doc_before_save()
		return before is None or pay_signature(before.hourly_rates) != pay_signature(self.hourly_rates)


HOURLY, MONTHLY = "Hourly", "Monthly"
WORK_PERMIT_NOTICE_DAYS = 30


def work_permit_notice(expiry, relieving_date=None) -> str | None:
	"""A warning when the work permit has expired or expires within
	WORK_PERMIT_NOTICE_DAYS, unless the employment has already ended."""
	if not expiry or (relieving_date and getdate(relieving_date) < getdate(today())):
		return None
	days_left = (getdate(expiry) - getdate(today())).days
	if days_left < 0:
		return _("The work permit expired on {0}.").format(frappe.format(expiry, "Date"))
	if days_left <= WORK_PERMIT_NOTICE_DAYS:
		return _("The work permit expires on {0}, in {1} days.").format(frappe.format(expiry, "Date"), days_left)
	return None
# Taiwan's convention: a monthly salary is 30 days' pay, whatever the month's
# length. So a 31-day month costs 31/30 of the salary, and February 28/30.
DAYS_PER_MONTH = 30


def pay_on(history, on):
	"""The Pay History row valid on `on`: the latest row whose Valid From is on
	or before that date. The base row (empty Valid From) applies before any
	dated row. None if no row applies."""
	on = getdate(on)
	applicable = [row for row in history if not row.valid_from or getdate(row.valid_from) <= on]
	return max(applicable, key=_valid_from) if applicable else None


def latest_pay(history):
	return max(history, key=_valid_from)


def hourly_rate_of(row) -> float:
	"""What an hour of work costs under these pay terms. Under monthly pay the
	salary covers the hours, so a Work Record costs nothing extra."""
	return flt(row.hourly_rate) if (row.pay_basis or HOURLY) == HOURLY else 0.0


def _valid_from(row) -> datetime.date:
	return getdate(row.valid_from) if row.valid_from else datetime.date.min


def pay_signature(history) -> list[tuple]:
	return sorted(
		(str(row.valid_from or ""), row.pay_basis or HOURLY, flt(row.hourly_rate), flt(row.monthly_salary))
		for row in history
	)


def get_pay_history(employee: str) -> list:
	return frappe.get_all(
		"Employee Hourly Rate",
		filters={"parenttype": "Employee", "parentfield": "hourly_rates", "parent": employee},
		fields=["valid_from", "pay_basis", "hourly_rate", "monthly_salary"],
	)


def get_hourly_rate(employee: str, on) -> float | None:
	"""The employee's hourly rate valid on the given date: 0 under monthly pay,
	None if no pay terms apply."""
	row = pay_on(get_pay_history(employee), on)
	return None if row is None else hourly_rate_of(row)


def get_salary_costs(employees: list[dict], from_date, to_date) -> dict:
	"""The salary cost of each monthly-paid employee on each day of the range:
	{employee: {date: salary ÷ 30}}. A day counts while the employee is
	employed (Date of Joining to Relieving Date) under monthly pay terms, up
	to today: like Work Records, which can't be dated in the future, salary
	not yet earned isn't a cost yet.

	`employees` are dicts with name, date_of_joining and relieving_date. The
	caller checks that the user may see pay; this reads it unchecked."""
	if not employees:
		return {}
	rows = frappe.get_all(
		"Employee Hourly Rate",
		filters={"parenttype": "Employee", "parentfield": "hourly_rates", "parent": ["in", [e["name"] for e in employees]]},
		fields=["parent", "valid_from", "pay_basis", "hourly_rate", "monthly_salary"],
	)
	history = {}
	for row in rows:
		history.setdefault(row.parent, []).append(row)

	costs = {}
	for employee in employees:
		pay = history.get(employee["name"], [])
		if not any(row.pay_basis == MONTHLY for row in pay):
			continue  # paid by the hour only: nothing accrues
		day = max(getdate(from_date), getdate(employee["date_of_joining"]))
		last = min(getdate(to_date), getdate(today()))
		if employee.get("relieving_date"):
			last = min(last, getdate(employee["relieving_date"]))
		while day <= last:
			row = pay_on(pay, day)
			if row and row.pay_basis == MONTHLY:
				costs.setdefault(employee["name"], {})[day] = flt(row.monthly_salary) / DAYS_PER_MONTH
			day = add_days(day, 1)
	return costs


@frappe.whitelist()
def get_hourly_rate_on(employee: str, date: str) -> float | None:
	"""For the Work Record form's cost preview. Rates are pay data (permlevel 1
	on Employee), so reading the employee isn't enough: an HR User, who sees
	employees but not their pay, is refused."""
	frappe.has_permission("Employee", "read", employee, throw=True)
	if 1 not in frappe.get_meta("Employee").get_permlevel_access("read"):
		frappe.throw(_("Not permitted to see hourly rates."), frappe.PermissionError)
	return get_hourly_rate(employee, date)


def recalculate_work_records(employee: str, history) -> None:
	"""Re-cost the employee's Work Records after their Pay History changed."""
	precision = frappe.get_precision("Work Record", "cost")
	records = frappe.get_all(
		"Work Record",
		filters={"employee": employee},
		fields=["name", "date", "hours_worked", "hourly_rate", "cost"],
	)
	for record in records:
		row = pay_on(history, record.date)
		if row is None:
			frappe.throw(
				_(
					"Work Record {0} on {1} would have no pay terms. Keep a base row "
					"(empty Valid From) or a row valid from that date or earlier."
				).format(record.name, frappe.format(record.date, "Date"))
			)
		rate = hourly_rate_of(row)
		cost = flt(flt(record.hours_worked) * rate, precision)
		if flt(record.hourly_rate) != rate or flt(record.cost) != cost:
			frappe.db.set_value("Work Record", record.name, {"hourly_rate": rate, "cost": cost})
