# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class EmployeeOtherName(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		other_name: DF.Data
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		writing_system: DF.Literal["Latin", "Chinese", "Thai", "Vietnamese", "Burmese", "Khmer", "Lao", "Japanese", "Korean", "Other"]
	# end: auto-generated types

	_DOCTYPE_NAME = "Employee Other Name"
