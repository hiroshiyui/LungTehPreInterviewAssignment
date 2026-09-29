# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from frappe.utils import flt, getdate, today

from hr_cost.hr_cost.doctype.employee.employee import get_hourly_rate

MAX_HOURS_PER_DAY = 24


class WorkRecord(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		cost: DF.Currency
		date: DF.Date
		employee: DF.Link
		employee_name: DF.Data | None
		hourly_rate: DF.Currency
		hours_worked: DF.Float
	# end: auto-generated types

	_DOCTYPE_NAME = "Work Record"

	def validate(self):
		self.validate_date()
		self.validate_hours_worked()
		self.set_hourly_rate()
		self.cost = flt(flt(self.hours_worked) * flt(self.hourly_rate), self.precision("cost"))

	def validate_date(self):
		if not self.date or not self.employee:
			return  # the mandatory-field check reports these
		# Otherwise future costs would already show up in this month's report.
		if getdate(self.date) > getdate(today()):
			frappe.throw(_("Date cannot be in the future."))
		joining, relieving, permit_expiry = frappe.db.get_value(
			"Employee", self.employee, ["date_of_joining", "relieving_date", "work_permit_expiry"]
		)
		if (joining and getdate(self.date) < getdate(joining)) or (
			relieving and getdate(self.date) > getdate(relieving)
		):
			frappe.throw(
				_("{0} was not employed on {1}.").format(
					self.employee_name or self.employee, frappe.format(self.date, "Date")
				)
			)
		# Work after the permit expired is recorded (it happened), with a warning.
		if permit_expiry and getdate(self.date) > getdate(permit_expiry):
			frappe.msgprint(
				_("{0}'s work permit expired on {1}, before this work date.").format(
					self.employee_name or self.employee, frappe.format(permit_expiry, "Date")
				),
				indicator="orange",
				alert=True,
			)

	def validate_hours_worked(self):
		if flt(self.hours_worked) <= 0:
			frappe.throw(_("Hours Worked must be greater than zero."))

		# Lock the employee's row until this transaction ends, so two saves for
		# the same employee take turns: without it, both could read the old total
		# below and together exceed the daily limit.
		frappe.db.get_value("Employee", self.employee, "name", for_update=True)

		wr = frappe.qb.DocType("Work Record")
		already_logged = (
			frappe.qb.from_(wr)
			.select(Sum(wr.hours_worked))
			.where((wr.employee == self.employee) & (wr.date == self.date) & (wr.name != self.name))
		).run()[0][0]

		if flt(already_logged) + flt(self.hours_worked) > MAX_HOURS_PER_DAY:
			frappe.throw(
				_("{0} would have more than {1} hours on {2} ({3} already recorded).").format(
					self.employee_name or self.employee,
					MAX_HOURS_PER_DAY,
					frappe.format(self.date, "Date"),
					flt(already_logged),
				)
			)

	def set_hourly_rate(self):
		# The rate valid on the *work* date, not today's: a record entered late,
		# after a raise, is still costed at the rate that applied on that day.
		# Under monthly pay it's 0: the salary covers the hours (the reports add
		# the salary itself), so the record logs hours only.
		if not self.employee or not self.date:
			return  # the mandatory-field check reports these
		rate = get_hourly_rate(self.employee, self.date)
		if rate is None:
			frappe.throw(
				_("{0} has no pay terms valid on {1}.").format(
					self.employee_name or self.employee, frappe.format(self.date, "Date")
				)
			)
		self.hourly_rate = rate


def on_doctype_update():
	"""Called by `bench migrate`. The 24 h check filters by employee and date on
	every save; Frappe's JSON can only declare single-column indexes."""
	frappe.db.add_index("Work Record", ["employee", "date"])
