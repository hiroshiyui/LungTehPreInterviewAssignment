// Copyright (c) 2026, Hui-Hong You and contributors
// For license information, please see license.txt

// Preview the rate and cost while editing; the server recalculates both on save.
frappe.ui.form.on("Work Record", {
	employee(frm) {
		frm.trigger("fetch_hourly_rate");
	},

	date(frm) {
		frm.trigger("fetch_hourly_rate");
	},

	hours_worked(frm) {
		frm.trigger("calculate_cost");
	},

	async fetch_hourly_rate(frm) {
		// Rate and cost are pay data (permlevel 1): users who can't see them get
		// no preview, and the server still costs the record on save.
		if (!frm.perm[1]?.read) return;
		if (!frm.doc.employee || !frm.doc.date) {
			// No employee or date, no rate: don't leave a stale preview.
			await frm.set_value({ hourly_rate: 0, cost: 0 });
			return;
		}
		// The rate valid on the record's date, from the Hourly Rate History.
		const { message } = await frappe.call({
			method: "hr_cost.hr_cost.doctype.employee.employee.get_hourly_rate_on",
			args: { employee: frm.doc.employee, date: frm.doc.date },
		});
		await frm.set_value("hourly_rate", message || 0);
		frm.trigger("calculate_cost");
	},

	calculate_cost(frm) {
		if (!frm.perm[1]?.read) return;
		frm.set_value("cost", flt(frm.doc.hours_worked) * flt(frm.doc.hourly_rate));
	},
});
