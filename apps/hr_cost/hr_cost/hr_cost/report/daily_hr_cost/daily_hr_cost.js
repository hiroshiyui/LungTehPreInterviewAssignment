// Copyright (c) 2026, Hui-Hong You and contributors
// For license information, please see license.txt

frappe.query_reports["Daily HR Cost"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
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
			// Keep in step with CHARTS in daily_hr_cost.py.
			options: ["HR Cost", "Hours Worked", "Employees at Work"],
			default: "HR Cost",
		},
		{
			fieldname: "show_empty_days",
			label: __("Show days without work"),
			fieldtype: "Check",
			default: 0,
		},
	],
};
