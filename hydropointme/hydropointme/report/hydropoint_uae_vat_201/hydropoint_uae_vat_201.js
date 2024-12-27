// Copyright (c) 2024, jyoti and contributors
// For license information, please see license.txt

frappe.query_reports["Hydropoint UAE VAT 201"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 1,
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
	],
	"onload": function(report) {
		// Add a custom button
		report.page.add_inner_button(__('Detailed Report'), function() {
			// Get the values of filters
			const filters = report.get_values();
			if (filters) {
				const company = encodeURIComponent(filters.company || "Samsoft Solution (Demo)");
				const from_date = filters.from_date || frappe.datetime.get_today();
				const to_date = filters.to_date || frappe.datetime.get_today();

				// Construct the URL for the detailed report
				const url = `/app/query-report/Hydro%20Report?company=${company}&from_date=${from_date}&to_date=${to_date}`;
				
				// Open the URL in a new tab
				window.open(url, '_blank');
			} else {
				frappe.msgprint(__('Please set all required filters before proceeding.'));
			}
		});
	},
	"formatter": function(value, row, column, data, default_formatter) {
		if (data
			&& (data.legend == 'VAT on Sales and All Other Outputs' || data.legend == 'VAT on Expenses and All Other Inputs')
			&& data.legend == value) {
			value = $(`<span>${value}</span>`);
			var $value = $(value).css("font-weight", "bold");
			value = $value.wrap("<p></p>").parent().html();
		}
		return value;
	},
};
