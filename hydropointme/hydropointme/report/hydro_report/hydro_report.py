import frappe

def execute(filters=None):
    # Define columns dynamically based on filters
    columns = get_columns(filters)

    # Fetch data based on filters
    data = get_sales_invoice_data(filters)

    return columns, data


def get_columns(filters):
    # Default columns for Sales Invoice
    columns = [
        {"label": "Sales Invoice Name", "fieldname": "sales_invoice_name", "fieldtype": "Link", "options": "Sales Invoice", "width": 200},
        {"label": "Net Total", "fieldname": "total_base_amount", "fieldtype": "Currency", "width": 150},
        {"label": "VAT Amount", "fieldname": "total_tax_amount", "fieldtype": "Currency", "width": 150},
    ]

    # Custom columns for "Expenses"
    if filters.get("vat_emirate") == "Expenses":
        columns = [
            {"label": "Purchase Invoice Name", "fieldname": "purchase_invoice_name", "fieldtype": "Link", "options": "Purchase Invoice", "width": 200},
            {"label": "Total Amount", "fieldname": "total_amount", "fieldtype": "Currency", "width": 150},
            {"label": "Recoverable Expenses", "fieldname": "recoverable_standard_rated_expenses", "fieldtype": "Currency", "width": 150},
        ]

    return columns


def get_sales_invoice_data(filters):
    conditions = []
    values = {}

    # Add company condition
    if filters.get("company"):
        conditions.append("s.company = %(company)s")
        values["company"] = filters["company"]

    # Add date range conditions
    if filters.get("from_date"):
        conditions.append("s.posting_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("s.posting_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    # Handle vat_emirate filter
    if filters.get("vat_emirate"):
        vat_emirate = filters["vat_emirate"]

        # List of Emirates
        emirates_list = [
            "Abu Dhabi", "Dubai", "Sharjah", "Ajman",
            "Umm Al Quwain", "Ras Al Khaimah", "Fujairah"
        ]

        if vat_emirate in emirates_list:
            conditions.append("s.vat_emirate = %(vat_emirate)s")
            values["vat_emirate"] = vat_emirate

            # Add fallback conditions for exempt and zero-rated items
            conditions.append("i.is_exempt != 1")
            conditions.append("i.is_zero_rated != 1")

        elif vat_emirate == "Zero Rated":
            conditions.append("i.is_zero_rated = 1")

        elif vat_emirate == "Exempt Supplies":
            conditions.append("i.is_exempt = 1")

        elif vat_emirate == "Expenses":
            # Query for "Expenses" case
            query = """
                SELECT
                    name AS purchase_invoice_name,
                    total AS total_amount,
                    recoverable_standard_rated_expenses
                FROM
                    `tabPurchase Invoice`
                WHERE
                    recoverable_standard_rated_expenses > 0
                    AND docstatus = 1
            """
            print("Generated Query for Expenses:", query)  # Debugging: Print the query
            data = frappe.db.sql(query, as_dict=True)
            print("Data Retrieved for Expenses:", data)  # Debugging: Print the fetched data
            return data

    # Join conditions into a single string
    condition_string = " AND ".join(conditions) or "1=1"

    # Query for Sales Invoices
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
        GROUP BY
            s.name
    """

    print("Generated SQL Query:", query)  # Debugging: Print the query
    print("Values:", values)  # Debugging: Print the values being passed to the query

    return frappe.db.sql(query, values, as_dict=True)
