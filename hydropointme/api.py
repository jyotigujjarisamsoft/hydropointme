from __future__ import unicode_literals
from xml.etree.ElementTree import tostring
import frappe
from frappe import _, msgprint
from frappe.utils import flt, getdate, comma_and
from collections import defaultdict
from datetime import datetime
from datetime import date
import json 

@frappe.whitelist()
def create_purchase_invoice(voucher_name):
    # Fetch the Petty Cash Voucher document
    voucher = frappe.get_doc("Petty Cash Voucher", voucher_name)
    print("Fetched Voucher:", voucher)

    # Create a new Purchase Invoice
    purchase_invoice = frappe.new_doc("Purchase Invoice")
    purchase_invoice.naming_series = "PTY-.YYYY.-"
    purchase_invoice.supplier = "Petty Cash"  # Static supplier for Petty Cash
    purchase_invoice.is_paid = 1  # Check 'Is Paid' checkbox
    purchase_invoice.posting_date = voucher.date  # Use the date from the voucher
    purchase_invoice.due_date = voucher.date  # Set the due date as the voucher date
    purchase_invoice.mode_of_payment = "Petty Cash"
    purchase_invoice.cash_bank_account = voucher.credit_account
    #purchase_invoice.branch = "Dubai"

    # Dictionary to store consolidated taxes
    tax_totals = {}
    total_tax_amount = 0.0  # Initialize the total tax amount

    # Add items to the Purchase Invoice
    for row in voucher.voucher_details:
        print("Processing row:", row)
        item = {
            "item_code": "Service Items",  # Replace with the default or dynamic item code
            "qty": 1,  # Default quantity to 1
            "rate": row.value,  # Map the rate to the 'value' field
            "description": row.description,  # Map the description
            "item_tax_template": row.vat_type,  # Map the VAT type
            "expense_account": row.expenses_account,  # Correct fieldname for the expense account
            "custom_remarks": row.remarks,  # Add remarks
        }
        purchase_invoice.append("items", item)

        # Calculate taxes based on Item Tax Template
        if row.vat_type:  # Ensure VAT type exists
            tax_template = frappe.get_doc("Item Tax Template", row.vat_type)
            for tax in tax_template.taxes:  # Loop through taxes in the template
                tax_key = tax.tax_type
                if tax_key not in tax_totals:
                    tax_totals[tax_key] = 0.0
                # Accumulate the tax amount for the item
                tax_amount = row.value * tax.tax_rate / 100
                tax_totals[tax_key] += tax_amount
                total_tax_amount += tax_amount  # Add to total tax amount

    # Populate the Purchase Taxes and Charges table
    for tax_type, tax_amount in tax_totals.items():
        purchase_invoice.append("taxes", {
            "charge_type": "On Net Total",
            "account_head": "VAT 5% - HP",  # Tax account head from the template
            "rate": 0,  # Set to 0, as we're using amount
            "tax_amount": tax_amount,  # Consolidated tax amount
            "description": f"Tax calculated for {tax_type}",  # Add description
        })

    # Throw an error if no items are found
    if not purchase_invoice.items:
        frappe.throw("No items found in Petty Cash Voucher Details.")

    # Set the value of the custom field with the total tax amount
    purchase_invoice.recoverable_standard_rated_expenses = total_tax_amount

    # Insert and submit the Purchase Invoice
    purchase_invoice.insert()  # Save the Purchase Invoice
    purchase_invoice.submit()  # Submit the Purchase Invoice

    # Log and return the created Purchase Invoice name
    frappe.msgprint(f"Purchase Invoice {purchase_invoice.name} created successfully!")
    return purchase_invoice.name

@frappe.whitelist()
def create_landed_cost_voucher(purchase_receipt, purchase_invoice):
    if not purchase_receipt:
        frappe.throw("Purchase Receipt is required to create Landed Cost Voucher")

    # Fetch details from Purchase Receipt
    purchase_receipt_doc = frappe.get_doc("Purchase Receipt", purchase_receipt)
    supplier = purchase_receipt_doc.supplier
    print("supplier",supplier)
    grand_total = purchase_receipt_doc.grand_total
    print("grand_total",grand_total)
    posting_date = purchase_receipt_doc.posting_date
    print("posting_date",posting_date)

    # Create a new Landed Cost Voucher
    lcv = frappe.new_doc("Landed Cost Voucher")
    lcv.company = frappe.defaults.get_user_default("Company")
    
    # Set 'Distribute Charges Based On' to 'Amount'
    lcv.distribute_charges_based_on = "Amount"

    # Add Purchase Receipt details
    lcv.append("purchase_receipts", {
        "receipt_document_type": "Purchase Receipt",
        "receipt_document": purchase_receipt,
        "supplier":supplier,
        "grand_total":grand_total,
        "posting_date":posting_date
    })

    if purchase_invoice:
        # Fetch purchase invoice items
        purchase_invoice_items = frappe.get_all(
            'Purchase Invoice Item', 
            filters={'parent': purchase_invoice}, 
            fields=['expense_account', 'amount', 'description', 'item_code']
        )
        print("purchase_invoice_items", purchase_invoice_items)
        
        # Add taxes and charges for each purchase invoice item
        for item in purchase_invoice_items:
            lcv.append("taxes", {
                "description": item.get('item_code'),  # Combine description and item code
                "expense_account": item.get('expense_account'),  # Use expense account from Purchase Invoice Item
                "amount": item.get('amount')  # Use amount from Purchase Invoice Item
            })


    # Trigger the built-in method to fetch items
    lcv.flags.ignore_permissions = True  # To ensure custom script permissions
    lcv.get_items_from_purchase_receipts()

    # Save the Landed Cost Voucher
    lcv.insert()
    lcv.save()
    lcv.submit()

    return lcv.name


@frappe.whitelist()
def get_sales_order_details(item_code):
    sales_order_items = frappe.db.sql("""
        SELECT
            so.name AS sales_order_name,
            so.customer AS customer,
            so.transaction_date AS posting_date,
            soi.rate AS item_rate
        FROM
            `tabSales Order` AS so
        INNER JOIN
            `tabSales Order Item` AS soi
        ON
            so.name = soi.parent
        WHERE
            soi.item_code = %(item_code)s
        ORDER BY
            so.transaction_date DESC
        LIMIT 5
    """, {
        'item_code': item_code
    }, as_dict=True)

    # Format the posting_date as dd-mm-yyyy
    for item in sales_order_items:
        item['posting_date'] = item['posting_date'].strftime('%d-%m-%Y')

    return sales_order_items

@frappe.whitelist()
def get_purchase_order_details(item_code):
    purchase_order_items = frappe.db.sql("""
        SELECT
            po.name AS purchase_order_name,
            po.supplier AS supplier,
            po.transaction_date AS posting_date,
            poi.rate AS item_rate
        FROM
            `tabPurchase Order` AS po
        INNER JOIN
            `tabPurchase Order Item` AS poi
        ON
            po.name = poi.parent
        WHERE
            poi.item_code = %(item_code)s
        ORDER BY
            po.transaction_date DESC
        LIMIT 5
    """, {
        'item_code': item_code
    }, as_dict=True)

    # Format the posting_date as dd-mm-yyyy
    for item in purchase_order_items:
        item['posting_date'] = item['posting_date'].strftime('%d-%m-%Y')

    return purchase_order_items

@frappe.whitelist()
def get_sales_order_item_details(sales_order, item_code):
    # Fetch the Sales Order Item details based on parent (sales_order) and item_code
    sales_order_items = frappe.get_all('Sales Order Item', filters={
        'parent': sales_order,
        'item_code': item_code
    }, fields=['rate', 'qty'])
    print("sales_order_items",sales_order_items)
    if sales_order_items:
        return sales_order_items[0]  # Return the first matching record (assuming only one match)
    else:
        return None  # Return None if no matching record found