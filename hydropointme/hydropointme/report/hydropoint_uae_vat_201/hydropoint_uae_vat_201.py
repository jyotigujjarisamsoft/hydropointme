# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data, emirates, amounts_by_emirate = get_data(filters)
	return columns, data

def get_columns():
	return [
		{"fieldname": "no", "label": _("No"), "fieldtype": "Data", "width": 50},
		{"fieldname": "legend", "label": _("Legend"), "fieldtype": "Data", "width": 300},
		{"fieldname": "amount", "label": _("Amount (AED)"), "fieldtype": "Currency", "width": 125},
		{"fieldname": "vat_amount", "label": _("VAT Amount (AED)"), "fieldtype": "Currency", "width": 150},
	]

def get_data(filters=None):
	data = []

	# VAT on Sales and Outputs section
	start_index_sales = len(data)
	emirates, amounts_by_emirate = append_vat_on_sales(data, filters)
	end_index_sales = len(data)
	append_total_row(data, start_index_sales, end_index_sales, "VAT on Sales and All Other Outputs")

	data.append({"no": "", "legend": "", "amount": "", "vat_amount": ""})  # Blank separator

	# VAT on Expenses and Inputs section
	start_index_expenses = len(data)
	append_vat_on_expenses(data, filters)
	end_index_expenses = len(data)
	append_total_row(data, start_index_expenses, end_index_expenses, "VAT on Expenses and All Other Inputs")

	return data, emirates, amounts_by_emirate

def append_total_row(data, start_index, end_index, section_label):
	total_amount = 0
	total_vat_amount = 0

	for row in data[start_index:end_index]:
		total_amount += frappe.utils.flt(row.get("raw_amount") or 0)
		total_vat_amount += frappe.utils.flt(row.get("raw_vat_amount") or 0)

	data.append({
		"no": "",
		"legend": _("Total {0}").format(section_label),
		"amount": frappe.format(total_amount, "Currency"),
		"vat_amount": frappe.format(total_vat_amount, "Currency"),
		"raw_amount": total_amount,
		"raw_vat_amount": total_vat_amount
	})

def append_vat_on_sales(data, filters):
	append_data(data, '', _('VAT on Sales and All Other Outputs'), 0, 0)

	emirates, amounts_by_emirate = standard_rated_expenses_emiratewise(data, filters)

	tourist_total = (-1) * get_tourist_tax_return_total(filters)
	tourist_tax = (-1) * get_tourist_tax_return_tax(filters)
	append_data(data, '2',
		_('Tax Refunds provided to Tourists under the Tax Refunds for Tourists Scheme'),
		tourist_total, tourist_tax)

	reverse_charge_total = get_reverse_charge_total(filters)
	reverse_charge_tax = get_reverse_charge_tax(filters)
	append_data(data, '3', _('Supplies subject to the reverse charge provision'),
		reverse_charge_total, reverse_charge_tax)

	append_data(data, '4', _('Zero Rated'), get_zero_rated_total(filters), 0)
	append_data(data, '5', _('Exempt Supplies'), get_exempt_total(filters), 0)

	append_data(data, '', '', 0, 0)

	return emirates, amounts_by_emirate

def standard_rated_expenses_emiratewise(data, filters):
	total_emiratewise = get_total_emiratewise(filters)
	emirates = get_emirates()
	amounts_by_emirate = {}
	for emirate, amount, vat in total_emiratewise:
		amounts_by_emirate[emirate] = {
			"legend": emirate,
			"raw_amount": amount,
			"raw_vat_amount": vat,
			"amount": frappe.format(amount, 'Currency'),
			"vat_amount": frappe.format(vat, 'Currency'),
		}
	amounts_by_emirate = append_emiratewise_expenses(data, emirates, amounts_by_emirate)
	return emirates, amounts_by_emirate

def append_emiratewise_expenses(data, emirates, amounts_by_emirate):
	for no, emirate in enumerate(emirates, 97):
		if emirate in amounts_by_emirate:
			amounts_by_emirate[emirate]["no"] = _('1{0}').format(chr(no))
			amounts_by_emirate[emirate]["legend"] = _('Standard rated supplies in {0}').format(emirate)
			data.append(amounts_by_emirate[emirate])
		else:
			append_data(data, _('1{0}').format(chr(no)),
				_('Standard rated supplies in {0}').format(emirate),
				0, 0)
	return amounts_by_emirate

def append_vat_on_expenses(data, filters):
	append_data(data, '', _('VAT on Expenses and All Other Inputs'), 0, 0)
	append_data(data, '9', _('Standard Rated Expenses'),
		get_standard_rated_expenses_total(filters),
		get_standard_rated_expenses_tax(filters))
	append_data(data, '10', _('Supplies subject to the reverse charge provision'),
		get_reverse_charge_recoverable_total(filters),
		get_reverse_charge_recoverable_tax(filters))

def append_data(data, no, legend, amount, vat_amount):
	data.append({
		"no": no,
		"legend": legend,
		"amount": frappe.format(amount, 'Currency'),
		"vat_amount": frappe.format(vat_amount, 'Currency') if vat_amount != "-" else "-",
		"raw_amount": frappe.utils.flt(amount),
		"raw_vat_amount": frappe.utils.flt(0 if vat_amount == "-" else vat_amount)
	})

def get_total_emiratewise(filters):
	conditions = get_conditions(filters)
	try:
		return frappe.db.sql("""
			select
				s.vat_emirate as emirate, sum(i.base_amount) as total, sum(i.tax_amount)
			from
				`tabSales Invoice Item` i inner join `tabSales Invoice` s
			on
				i.parent = s.name
			where
				s.docstatus = 1 and i.is_exempt != 1 and i.is_zero_rated != 1
				{where_conditions}
			group by
				s.vat_emirate;
			""".format(where_conditions=conditions), filters)
	except (IndexError, TypeError):
		return 0

def get_emirates():
	return [
		'Abu Dhabi', 'Dubai', 'Sharjah', 'Ajman',
		'Umm Al Quwain', 'Ras Al Khaimah', 'Fujairah'
	]

def get_filters(filters):
	query_filters = []
	if filters.get("company"):
		query_filters.append(["company", '=', filters['company']])
	if filters.get("from_date"):
		query_filters.append(["posting_date", '>=', filters['from_date']])
	if filters.get("from_date"):
		query_filters.append(["posting_date", '<=', filters['to_date']])
	return query_filters

def get_reverse_charge_total(filters):
	query_filters = get_filters(filters)
	query_filters.append(['reverse_charge', '=', 'Y'])
	query_filters.append(['docstatus', '=', 1])
	try:
		return frappe.db.get_all('Purchase Invoice', filters=query_filters,
			fields=['sum(total)'], as_list=True, limit=1)[0][0] or 0
	except (IndexError, TypeError):
		return 0

def get_reverse_charge_tax(filters):
	conditions = get_conditions_join(filters)
	return frappe.db.sql("""
		select sum(debit) from
			`tabPurchase Invoice` p inner join `tabGL Entry` gl
		on gl.voucher_no = p.name
		where p.reverse_charge = "Y"
			and p.docstatus = 1
			and gl.docstatus = 1
			and account in (select account from `tabUAE VAT Account` where parent=%(company)s)
			{where_conditions};
		""".format(where_conditions=conditions), filters)[0][0] or 0

def get_reverse_charge_recoverable_total(filters):
	query_filters = get_filters(filters)
	query_filters.append(['reverse_charge', '=', 'Y'])
	query_filters.append(['recoverable_reverse_charge', '>', '0'])
	query_filters.append(['docstatus', '=', 1])
	try:
		return frappe.db.get_all('Purchase Invoice', filters=query_filters,
			fields=['sum(total)'], as_list=True, limit=1)[0][0] or 0
	except (IndexError, TypeError):
		return 0

def get_reverse_charge_recoverable_tax(filters):
	conditions = get_conditions_join(filters)
	return frappe.db.sql("""
		select sum(debit * p.recoverable_reverse_charge / 100)
		from `tabPurchase Invoice` p inner join `tabGL Entry` gl
		on gl.voucher_no = p.name
		where p.reverse_charge = "Y"
			and p.docstatus = 1
			and p.recoverable_reverse_charge > 0
			and gl.docstatus = 1
			and account in (select account from `tabUAE VAT Account` where parent=%(company)s)
			{where_conditions};
		""".format(where_conditions=conditions), filters)[0][0] or 0

def get_conditions_join(filters):
	conditions = ""
	for opts in (("company", " and p.company=%(company)s"),
		("from_date", " and p.posting_date>=%(from_date)s"),
		("to_date", " and p.posting_date<=%(to_date)s")):
		if filters.get(opts[0]):
			conditions += opts[1]
	return conditions

def get_standard_rated_expenses_total(filters):
	query_filters = get_filters(filters)
	query_filters.append(['recoverable_standard_rated_expenses', '>', 0])
	query_filters.append(['docstatus', '=', 1])
	try:
		return frappe.db.get_all('Purchase Invoice', filters=query_filters,
			fields=['sum(total)'], as_list=True, limit=1)[0][0] or 0
	except (IndexError, TypeError):
		return 0

def get_standard_rated_expenses_tax(filters):
	query_filters = get_filters(filters)
	query_filters.append(['recoverable_standard_rated_expenses', '>', 0])
	query_filters.append(['docstatus', '=', 1])
	try:
		return frappe.db.get_all('Purchase Invoice', filters=query_filters,
			fields=['sum(recoverable_standard_rated_expenses)'], as_list=True, limit=1)[0][0] or 0
	except (IndexError, TypeError):
		return 0

def get_tourist_tax_return_total(filters):
	query_filters = get_filters(filters)
	query_filters.append(['tourist_tax_return', '>', 0])
	query_filters.append(['docstatus', '=', 1])
	try:
		return frappe.db.get_all('Sales Invoice', filters=query_filters,
			fields=['sum(total)'], as_list=True, limit=1)[0][0] or 0
	except (IndexError, TypeError):
		return 0

def get_tourist_tax_return_tax(filters):
	query_filters = get_filters(filters)
	query_filters.append(['tourist_tax_return', '>', 0])
	query_filters.append(['docstatus', '=', 1])
	try:
		return frappe.db.get_all('Sales Invoice', filters=query_filters,
			fields=['sum(tourist_tax_return)'], as_list=True, limit=1)[0][0] or 0
	except (IndexError, TypeError):
		return 0

def get_zero_rated_total(filters):
	conditions = get_conditions(filters)
	try:
		return frappe.db.sql("""
			select sum(i.base_amount) as total
			from `tabSales Invoice Item` i
			inner join `tabSales Invoice` s on i.parent = s.name
			where s.docstatus = 1 and i.is_zero_rated = 1
				{where_conditions};
			""".format(where_conditions=conditions), filters)[0][0] or 0
	except (IndexError, TypeError):
		return 0

def get_exempt_total(filters):
	conditions = get_conditions(filters)
	try:
		return frappe.db.sql("""
			select sum(i.base_amount) as total
			from `tabSales Invoice Item` i
			inner join `tabSales Invoice` s on i.parent = s.name
			where s.docstatus = 1 and i.is_exempt = 1
				{where_conditions};
			""".format(where_conditions=conditions), filters)[0][0] or 0
	except (IndexError, TypeError):
		return 0

def get_conditions(filters):
	conditions = ""
	for opts in (("company", " and company=%(company)s"),
		("from_date", " and posting_date>=%(from_date)s"),
		("to_date", " and posting_date<=%(to_date)s")):
		if filters.get(opts[0]):
			conditions += opts[1]
	return conditions

