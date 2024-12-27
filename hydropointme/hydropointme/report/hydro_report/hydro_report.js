// Copyright (c) 2024, jyoti and contributors
// For license information, please see license.txt

frappe.query_reports["Hydro Report"] = {
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
        {
            "fieldname": "vat_emirate",
            "label": __("vat_emirate"),
            "fieldtype": "Select",
            "options": [
				"",
                "Abu Dhabi",
                "Dubai",
                "Sharjah",
                "Ajman",
                "Umm Al Quwain",
                "Ras Al Khaimah",
                "Fujairah",
				"Zero Rated",
				"Exempt Supplies",
				"Expenses"
            ]
        }
    ]
};