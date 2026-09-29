// Copyright (c) 2026, Hui-Hong You and contributors
// For license information, please see license.txt

frappe.query_reports["Monthly HR Cost"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.year_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.year_end(),
			reqd: 1,
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "chart",
			label: __("Chart"),
			fieldtype: "Select",
			// Keep in step with CHARTS in monthly_hr_cost.py.
			options: ["Cost by Employee", "Cost Share", "Effective Hourly Rate"],
			default: "Cost by Employee",
		},
	],
};
