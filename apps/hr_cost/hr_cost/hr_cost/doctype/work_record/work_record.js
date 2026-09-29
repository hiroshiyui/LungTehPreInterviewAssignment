// Copyright (c) 2026, Hui-Hong You and contributors
// For license information, please see license.txt

// Preview the cost while editing; the server recalculates it on save.
frappe.ui.form.on("Work Record", {
	async employee(frm) {
		if (!frm.doc.employee) return;
		const { message } = await frappe.db.get_value("Employee", frm.doc.employee, "hourly_rate");
		await frm.set_value("hourly_rate", message.hourly_rate);
		frm.trigger("calculate_cost");
	},

	hours_worked(frm) {
		frm.trigger("calculate_cost");
	},

	calculate_cost(frm) {
		frm.set_value("cost", flt(frm.doc.hours_worked) * flt(frm.doc.hourly_rate));
	},
});
