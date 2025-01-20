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

@frappe.whitelist()
def update_custom_fields_on_submit(doc_name):
    """
    Update custom_rate_hidden and custom_amount_hidden for Delivery Note Items on submit.
    """
    delivery_note = frappe.get_doc("Delivery Note", doc_name)
    
    for item in delivery_note.items:
        if item.against_sales_order and item.item_code:
            sales_order_item = frappe.get_value(
                "Sales Order Item",
                {"parent": item.against_sales_order, "item_code": item.item_code},
                ["rate", "qty"],
                as_dict=True
            )
            if sales_order_item:
                item.custom_rate_hidden = sales_order_item["rate"]
                item.custom_amount_hidden = sales_order_item["qty"] * sales_order_item["rate"]
    
    # Save the document after modifications
    delivery_note.save()
    frappe.db.commit()
    return {"status": "success"}

@frappe.whitelist()
def update_pending_qty(proforma_invoice):
    """
    Update pending_qty in Proforma Invoice items based on the total delivered quantities
    from all Delivery Notes created against the Proforma Invoice.
    """
    # Fetch the Proforma Invoice document
    proforma_invoice_doc = frappe.get_doc("Proforma Invoice", proforma_invoice)

    # Fetch all Delivery Note items linked to this Proforma Invoice
    delivery_note_items = frappe.db.sql(
        """
        SELECT 
            dn_item.item_code, 
            dn_item.qty, 
            dn_item.custom_against_proforma_invoice_item 
        FROM 
            `tabDelivery Note Item` dn_item
        INNER JOIN 
            `tabDelivery Note` dn
        ON 
            dn.name = dn_item.parent
        WHERE 
            dn.custom_proforma_invoice = %s
            AND EXISTS (
                SELECT 1 
                FROM `tabPerforma Invoice Items` pi_item
                WHERE pi_item.name = dn_item.custom_against_proforma_invoice_item
                AND pi_item.parent = %s
            )
        """,
        (proforma_invoice, proforma_invoice),
        as_dict=True,
    )

    # Calculate total delivered quantities per item
    delivered_quantities = {}
    for dn_item in delivery_note_items:
        proforma_item = dn_item.get("custom_against_proforma_invoice_item")
        delivered_quantities[proforma_item] = (
            delivered_quantities.get(proforma_item, 0) + dn_item.get("qty", 0)
        )

    # Update pending_qty in Proforma Invoice items
    for pi_item in proforma_invoice_doc.items:
        total_delivered_qty = delivered_quantities.get(pi_item.name, 0)
        pi_item.pending_qty = max(pi_item.pi_qty - total_delivered_qty, 0)

    # Save the updated Proforma Invoice
    proforma_invoice_doc.save()
    frappe.db.commit()

    return {"status": "success"}

@frappe.whitelist()
def update_custom_pi_pending_qty(sales_order, item_code, sales_order_item):
    """
    Update the custom_pi_pending_qty field in Sales Order Item
    for the given sales_order, item_code, and sales_order_item.
    """
    # Fetch the Sales Order Item
    sales_order_item_data = frappe.get_doc("Sales Order Item", sales_order_item)

    if not sales_order_item_data:
        frappe.throw(f"No Sales Order Item found with name {sales_order_item} for Sales Order {sales_order} and Item Code {item_code}.")

    # Fetch the total pi_qty for the item_code where sales_order_item matches
    total_pi_qty = frappe.db.sql("""
        SELECT SUM(pi_qty) as total_pi_qty
        FROM `tabPerforma Invoice Items`
        WHERE sales_order = %s AND item = %s AND sales_order_item = %s
    """, (sales_order, item_code, sales_order_item), as_dict=True)[0].get("total_pi_qty", 0) or 0

    # Calculate pending quantity
    custom_pi_pending_qty = sales_order_item_data.qty - total_pi_qty

    # Update the custom_pi_pending_qty field in Sales Order Item
    frappe.db.set_value(
        "Sales Order Item",
        sales_order_item,
        "custom_pi_pending_qty",
        custom_pi_pending_qty
    )

@frappe.whitelist()
def get_pending_delivery_items(proforma_invoice):
    """
    Fetch items from Proforma Invoice that are not yet fully delivered in Delivery Notes,
    including additional details like item_name, stock_uom, and stock_on_hand from the Bin table.
    """
    # Fetch Proforma Invoice Items with additional details from the Item table
    proforma_items = frappe.db.sql(
        """
        SELECT 
            pii.idx,
            pii.name AS proforma_invoice_item_name,
            pii.item AS item_code,
            pii.description,
            pii.pi_qty AS qty,
            pii.rate,
            pii.amount,
            pii.sales_order,
            pii.sales_order_item,
            pii.warehouse,  -- Fetch warehouse from Proforma Invoice Item
            it.item_name,
            it.stock_uom
        FROM 
            `tabPerforma Invoice Items` pii
        LEFT JOIN 
            `tabItem` it ON pii.item = it.name
        WHERE 
            pii.parent = %s
        ORDER BY 
            pii.idx ASC
        """,
        (proforma_invoice,),
        as_dict=True
    )

    # Fetch Delivery Note Items linked to the Proforma Invoice Items
    dn_items = frappe.db.sql(
        """
        SELECT 
            dni.custom_against_proforma_invoice_item,
            dni.item_code,
            SUM(dni.qty) AS total_delivered_qty
        FROM 
            `tabDelivery Note Item` dni
        WHERE 
            dni.custom_against_proforma_invoice = %s
        GROUP BY 
            dni.item_code, dni.custom_against_proforma_invoice_item
        """,
        (proforma_invoice,),
        as_dict=True
    )

    # Map total delivered quantities
    dn_items_map = {
        (item["item_code"], item["custom_against_proforma_invoice_item"]): item["total_delivered_qty"] for item in dn_items
    }

    # Fetch stock_on_hand from Bin table using proper parameterization
    item_codes = [item["item_code"] for item in proforma_items if item.get("item_code")]
    warehouses = [item["warehouse"] for item in proforma_items if item.get("warehouse")]

    bin_items = frappe.db.sql(
        """
        SELECT 
            bin.item_code,
            bin.warehouse,
            bin.actual_qty AS stock_on_hand
        FROM 
            `tabBin` bin
        WHERE 
            bin.item_code IN %s AND bin.warehouse IN %s
        """,
        (tuple(item_codes), tuple(warehouses)),
        as_dict=True
    )

    # Create a map for stock_on_hand by item_code and warehouse
    bin_items_map = {
        (bin_item["item_code"], bin_item["warehouse"]): bin_item["stock_on_hand"] for bin_item in bin_items
    }

    # Prepare pending items
    pending_items = []
    for item in proforma_items:
        total_delivered_qty = dn_items_map.get((item["item_code"], item["proforma_invoice_item_name"]), 0)
        pending_qty = item["qty"] - total_delivered_qty

        # Fetch stock_on_hand for the item from the Bin map
        stock_on_hand = bin_items_map.get((item["item_code"], item["warehouse"]), 0)

        if pending_qty > 0:
            pending_items.append({
                "idx": item["idx"],
                "proforma_invoice_item_name": item["proforma_invoice_item_name"],
                "item_code": item["item_code"],
                "item_name": item["item_name"],  # Add item_name
                "stock_uom": item["stock_uom"],  # Add stock_uom
                "description": item["description"],
                "qty": item["qty"],
                "custom_delivery_pending_qty": pending_qty,
                "rate": item["rate"],
                "amount": item["rate"] * pending_qty,
                "sales_order": item["sales_order"],
                "sales_order_item_name": item["sales_order_item"],
                "warehouse": item["warehouse"],
                "stock_on_hand": stock_on_hand,  # Add stock_on_hand
            })

    return pending_items

@frappe.whitelist()
def get_pending_items(sales_order):
    """
    Fetch items from Sales Order that are not yet fully accounted for in Proforma Invoice Items.
    """
    # Check if the user has read permissions for the Sales Order
    if not frappe.has_permission(doctype="Sales Order", doc=sales_order, ptype="read"):
        frappe.throw("You do not have enough permissions to access this resource. Please contact your manager.")

    # Get all items from the Sales Order, including their stock from the Bin doctype
    sales_order_items = frappe.db.sql(
        """
        SELECT 
            soi.idx,
            soi.name AS sales_order_item_name,
            soi.item_code,
            soi.description,
            soi.qty,
            soi.rate,
            soi.amount,
            COALESCE(bin.actual_qty, 0) AS stock_on_hand,  -- Fetch stock from Bin
            soi.custom_pi_pending_qty,
            soi.warehouse  -- Include warehouse in query
        FROM 
            `tabSales Order Item` soi
        LEFT JOIN 
            `tabBin` bin
        ON 
            bin.item_code = soi.item_code AND bin.warehouse = soi.warehouse
        WHERE 
            soi.parent = %s
        ORDER BY 
            soi.idx ASC
        """,
        (sales_order,),
        as_dict=True
    )

    # Get all Proforma Invoice Items related to this Sales Order
    pi_items = frappe.db.sql(
        """
        SELECT 
            pii.sales_order_item,  -- Add Sales Order Item field
            pii.item AS item_code,
            SUM(pii.pi_qty) AS total_pi_qty
        FROM 
            `tabPerforma Invoice Items` pii
        WHERE 
            pii.sales_order = %s
        GROUP BY 
            pii.item, pii.sales_order_item  -- Group by both item_code and sales_order_item
        """,
        (sales_order,),
        as_dict=True
    )

    # Map total `pi_qty` for each sales_order_item
    pi_items_map = {
        (item["item_code"], item["sales_order_item"]): item["total_pi_qty"] for item in pi_items
    }

    # Prepare list of pending items
    pending_items = []
    for item in sales_order_items:
        # Calculate the total Proforma Invoice quantity for this item using item_code and sales_order_item
        total_pi_qty = pi_items_map.get((item["item_code"], item["sales_order_item_name"]), 0)

        # Calculate the actual pending quantity
        pending_qty = item["qty"] - total_pi_qty

        # Ensure pending quantity is accurate and greater than zero
        if pending_qty > 0:
            pending_items.append({
                "idx": item["idx"],  # Include the original index
                "sales_order_item_name": item["sales_order_item_name"],
                "item_code": item["item_code"],
                "description": item["description"],
                "qty": item["qty"],
                "custom_pi_pending_qty": pending_qty,
                "rate": item["rate"],
                "amount": item["rate"] * pending_qty,
                "stock_on_hand": item["stock_on_hand"],
                "warehouse": item["warehouse"],  # Include warehouse in the response
            })

    # Return the pending items sorted by their original index
    pending_items.sort(key=lambda x: x["idx"])
    return pending_items
