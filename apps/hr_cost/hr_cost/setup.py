# Copyright (c) 2026, Hui-Hong You and contributors
# For license information, please see license.txt

"""Answer Frappe's one-time setup wizard for the tutorial site, so a learner
lands on the desk with the right currency.

	bench --site <site> execute hr_cost.setup.complete_site_setup \\
		--kwargs '{"language": "English", "country": "Taiwan", "timezone": "Asia/Taipei", "currency": "TWD"}'
"""

import frappe
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete, update_system_settings


def complete_site_setup(language: str, country: str, timezone: str, currency: str) -> dict:
	"""Give the site the wizard's answers, unless it already has them.

	On every migrate, Frappe marks its wizard complete by itself once the site
	has any user besides Administrator (the demo users), without asking the
	questions. So "set up" isn't enough to go by: the answers are missing
	while the site has no country. Returns {"changed": 0} when there was
	nothing to do; provisioning reports a change otherwise."""
	if frappe.db.get_single_value("System Settings", "country"):
		return {"changed": 0}
	answers = {"language": language, "country": country, "timezone": timezone, "currency": currency}
	if not frappe.is_setup_complete():
		setup_complete(answers)  # the wizard's own code path
	else:
		# Marked complete without answers: apply what the wizard would have set.
		update_system_settings(frappe._dict(answers))
	return {"changed": 1}
