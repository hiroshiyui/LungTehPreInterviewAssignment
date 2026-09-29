// Copyright (c) 2026, Hui-Hong You and contributors
// For license information, please see license.txt

// Draw the Pay History as a line: one point per row, in the order they took
// effect, plus "Today" so the current terms reach the present.
frappe.ui.form.on("Employee", {
	refresh(frm) {
		frm.trigger("render_rate_history_chart");
		frm.trigger("show_work_permit_notice");
	},

	// The same notice the server gives on save (work_permit_notice in employee.py).
	show_work_permit_notice(frm) {
		frm.set_intro("");
		const expiry = frm.doc.work_permit_expiry;
		const relieved = frm.doc.relieving_date && frm.doc.relieving_date < frappe.datetime.get_today();
		if (!expiry || relieved) return;
		const days = frappe.datetime.get_day_diff(expiry, frappe.datetime.get_today());
		if (days < 0) {
			frm.set_intro(__("The work permit expired on {0}.", [frappe.datetime.str_to_user(expiry)]), "red");
		} else if (days <= 30) {
			frm.set_intro(
				__("The work permit expires on {0}, in {1} days.", [frappe.datetime.str_to_user(expiry), days]),
				"orange"
			);
		}
	},

	render_rate_history_chart(frm) {
		const wrapper = frm.get_field("rate_history_chart").$wrapper;
		wrapper.empty();
		// Rates are pay data (permlevel 1). Frappe already hides this field from
		// users who can't see pay, but don't draw anything for them either.
		if (!frm.perm[1]?.read || frm.is_new()) return;

		// The base row (no Valid From) comes first, then dated rows by date: the
		// same order the server uses to pick the pay terms valid on a date.
		const history = (frm.doc.hourly_rates || [])
			.slice()
			.sort((a, b) => (a.valid_from || "").localeCompare(b.valid_from || ""));
		if (!history.length) return;

		// Hourly rates and monthly salaries differ by a factor of ~100, so one
		// line can't show both: plot the current pay basis's terms.
		const basis = history[history.length - 1].pay_basis || "Hourly";
		const rows = history.filter((r) => (r.pay_basis || "Hourly") === basis);
		const amount = (r) => flt(basis === "Monthly" ? r.monthly_salary : r.hourly_rate);
		const labels = rows.map((r) => (r.valid_from ? frappe.datetime.str_to_user(r.valid_from) : __("Base")));
		const values = rows.map(amount);
		labels.push(__("Today"));
		values.push(values[values.length - 1]);
		const title = basis === "Monthly" ? __("Monthly Salary History") : __("Hourly Rate History");

		frappe.utils.make_chart($("<div>").appendTo(wrapper)[0], {
			title,
			type: "line",
			height: 220,
			data: { labels, datasets: [{ name: basis === "Monthly" ? __("Monthly Salary") : __("Hourly Rate"), values }] },
			colors: ["blue"], // make_chart's default light blue is faint for a single line
			lineOptions: { regionFill: 1 },
			tooltipOptions: { formatTooltipY: (value) => format_currency(value) },
		});
	},
});

// Redraw as rows are added, edited or removed, before the form is saved. Grid
// events fire on the child DocType, named after the table field.
frappe.ui.form.on("Employee Hourly Rate", {
	hourly_rates_add: (frm) => frm.trigger("render_rate_history_chart"),
	hourly_rates_remove: (frm) => frm.trigger("render_rate_history_chart"),
	valid_from: (frm) => frm.trigger("render_rate_history_chart"),
	pay_basis: (frm) => frm.trigger("render_rate_history_chart"),
	hourly_rate: (frm) => frm.trigger("render_rate_history_chart"),
	monthly_salary: (frm) => frm.trigger("render_rate_history_chart"),
});
