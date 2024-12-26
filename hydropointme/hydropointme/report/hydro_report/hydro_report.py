import frappe

def execute(filters=None):
    # Define columns
    columns = [
        {"label": "Sales Invoice Name", "fieldname": "sales_invoice_name", "fieldtype": "Link", "options": "Sales Invoice", "width": 200},
        {"label": "Net Total", "fieldname": "total_base_amount", "fieldtype": "Currency", "width": 150},
        {"label": "VAT Amount", "fieldname": "total_tax_amount", "fieldtype": "Currency", "width": 150},
    ]

    # Fetch data based on filters
    data = get_sales_invoice_data(filters)

    return columns, data

def get_sales_invoice_data(filters):
    conditions = []
    values = {}

    if filters.get("company"):
        conditions.append("s.company = %(company)s")
        values["company"] = filters["company"]

    if filters.get("from_date"):
        conditions.append("s.posting_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("s.posting_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("vat_emirate"):
        conditions.append("s.vat_emirate = %(vat_emirate)s")
        values["vat_emirate"] = filters["vat_emirate"]

    # Ensure there is always a valid condition
    condition_string = " AND ".join(conditions) or "1=1"

    query = f"""
        SELECT
            s.name AS sales_invoice_name,
            SUM(i.base_amount) AS total_base_amount,
            SUM(i.tax_amount) AS total_tax_amount
        FROM
            `tabSales Invoice Item` i
        INNER JOIN 
            `tabSales Invoice` s
        ON
            i.parent = s.name
        WHERE
            {condition_string}
            AND s.docstatus = 1
            AND i.is_exempt != 1
            AND i.is_zero_rated != 1
        GROUP BY
            s.name
    """

    return frappe.db.sql(query, values, as_dict=True)
