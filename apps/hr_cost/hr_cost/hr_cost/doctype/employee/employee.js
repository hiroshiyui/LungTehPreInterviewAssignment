// Copyright (c) 2026, Hui-Hong You and contributors
// For license information, please see license.txt

// Draw the Hourly Rate History as a line: one point per rate, in the order
// they took effect, plus "Today" so the current rate reaches the present.
frappe.ui.form.on("Employee", {
	refresh(frm) {
		frm.trigger("render_rate_history_chart");
	},

	render_rate_history_chart(frm) {
		const wrapper = frm.get_field("rate_history_chart").$wrapper;
		wrapper.empty();
		// Rates are pay data (permlevel 1). Frappe already hides this field from
		// users who can't see pay, but don't draw anything for them either.
		if (!frm.perm[1]?.read || frm.is_new()) return;

		// The base rate (no Valid From) comes first, then dated rates by date:
		// the same order the server uses to pick the rate valid on a date.
		const rates = (frm.doc.hourly_rates || [])
			.slice()
			.sort((a, b) => (a.valid_from || "").localeCompare(b.valid_from || ""));
		if (!rates.length) return;

		const labels = rates.map((r) => (r.valid_from ? frappe.datetime.str_to_user(r.valid_from) : __("Base")));
		const values = rates.map((r) => flt(r.hourly_rate));
		labels.push(__("Today"));
		values.push(values[values.length - 1]);

		frappe.utils.make_chart($("<div>").appendTo(wrapper)[0], {
			title: __("Hourly Rate History"),
			type: "line",
			height: 220,
			data: { labels, datasets: [{ name: __("Hourly Rate"), values }] },
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
	hourly_rate: (frm) => frm.trigger("render_rate_history_chart"),
});
