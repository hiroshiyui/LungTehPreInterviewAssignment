// Copyright (c) 2026, Hui-Hong You and contributors
// For license information, please see license.txt

frappe.query_reports["Daily HR Cost"] = {
	// "Download PDF": the current view as an A4 file named after the report and
	// period (see report/pdf.py), to print or attach to an email.
	onload(report) {
		report.page.add_inner_button(__("Download PDF"), () => {
			const params = new URLSearchParams({
				report_name: report.report_name,
				filters: JSON.stringify(report.get_filter_values()),
			});
			// Served as an attachment, so the page stays and the file is saved.
			window.location.href = `/api/method/hr_cost.hr_cost.report.pdf.download_report_pdf?${params}`;
		});
	},

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
			fieldname: "nationality",
			label: __("Nationality"),
			fieldtype: "Link",
			options: "Country",
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

	// Drill down: each date links to that day's Work Records (and keeps the
	// employee filter). Days without work have nothing to open.
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname !== "date" || !data || !flt(data.hours_worked)) return formatted;
		const filters = { date: data.date };
		const employee = frappe.query_report.get_filter_value("employee");
		if (employee) filters.employee = employee;
		const url = `/desk/work-record?${new URLSearchParams(filters)}`;
		return `<a href="${url}" title="${__("Open this day's Work Records")}">${formatted}</a>`;
	},
};
