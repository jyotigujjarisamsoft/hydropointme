import frappe
from frappe.utils import flt

def execute(filters=None):
    # Define columns
    columns = [
        {"label": "Sales Invoice Name", "fieldname": "name", "fieldtype": "Link", "options": "Sales Invoice", "width": 200},
        {"label": "Net Total", "fieldname": "net_total", "fieldtype": "Currency", "width": 150},
        {"label": "VAT Amount", "fieldname": "vat_amount", "fieldtype": "Currency", "width": 150},
    ]

    # Fetch data based on filters
    data = get_sales_invoice_data(filters)

    return columns, data

def get_sales_invoice_data(filters):
    conditions = []
    values = {}

    if filters.get("company"):
        conditions.append("company = %(company)s")
        values["company"] = filters["company"]

    if filters.get("from_date"):
        conditions.append("posting_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("posting_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("vat_emirate"):
        conditions.append("vat_emirate = %(vat_emirate)s")
        values["vat_emirate"] = filters["vat_emirate"]

    condition_string = " AND ".join(conditions)

    query = f"""
        SELECT
            name,
            net_total,
            total_taxes_and_charges AS vat_amount
        FROM
            `tabSales Invoice`
        WHERE
            {condition_string} AND docstatus = 1
    """
    return frappe.db.sql(query, values, as_dict=True)
