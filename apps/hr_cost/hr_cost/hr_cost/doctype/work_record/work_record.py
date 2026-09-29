# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from frappe.utils import flt

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
		self.validate_hours_worked()
		self.set_hourly_rate()
		self.cost = flt(flt(self.hours_worked) * flt(self.hourly_rate), self.precision("cost"))

	def validate_hours_worked(self):
		if flt(self.hours_worked) <= 0:
			frappe.throw(_("Hours Worked must be greater than zero."))

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
		# Snapshot the employee's rate when the record is created (or re-assigned),
		# so a later raise does not change the cost of work already done.
		if self.is_new() or self.has_value_changed("employee") or not self.hourly_rate:
			self.hourly_rate = frappe.db.get_value("Employee", self.employee, "hourly_rate")
