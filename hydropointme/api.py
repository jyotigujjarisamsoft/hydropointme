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

    # Fetch Purchase Invoice details to get the expense account
    if purchase_invoice:
        purchase_invoice_items = frappe.get_all('Purchase Invoice Item', filters={'parent': purchase_invoice}, fields=['expense_account', 'amount', 'description'])
        if purchase_invoice_items:
            # Assuming the expense account is the same for all items, pick the first one
            expense_account = purchase_invoice_items[0].expense_account
            amount = purchase_invoice_items[0].amount
            description = purchase_invoice_items[0].description
        else:
            expense_account = "Default Expense Account"  # Set a default if no items are found
            amount = 0
            description = "Default Description"
    else:
        expense_account = "Default Expense Account"
        amount = 0
        description = "Default Description"

    # Add default taxes and charges
    lcv.append("taxes", {
        "description": description,
        "expense_account": expense_account,  # Autofilled expense account from Purchase Invoice
        "amount": amount  # Example fixed tax amount
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