// Copyright (c) 2026, Hui-Hong You and contributors
// For license information, please see license.txt

frappe.query_reports["Monthly HR Cost"] = {
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
			fieldname: "nationality",
			label: __("Nationality"),
			fieldtype: "Link",
			options: "Country",
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
