from erpnext.zra_client.generic_api import send_response, send_response_list
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.custom_frappe_client import CustomFrappeClient
from frappe import _
import frappe
import random
import json
import re

ZRA_CLIENT_INSTANCE = ZRAClient()
CUSTOM_FRAPPE_INSTANCE = CustomFrappeClient()


@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_purchase_order():
    data = frappe.form_dict
    supplierId = data.get("supplierId")
    requiredBy = data.get("requiredBy")
    currency = data.get("currency")
    status = data.get("status")
    costCenter = data.get("costCenter")
    project = data.get("project")
    taxCategory = data.get("taxCategory")
    shippingRule = data.get("shippingRule")
    incoterm = data.get("incoterm")
    placeOfSupply = data.get("placeOfSupply")
    addresses = data.get("addresses", {})
    supplierAddress = addresses.get("supplierAddress", {})
    dispatchAddress = addresses.get("dispatchAddress", {})
    shippingAddress = addresses.get("shippingAddress", {})
    
    print(supplierAddress)
    print(dispatchAddress)
    print(shippingAddress)
    
    terms = data.get("terms")


    items = data.get("items", [])
        
    taxes = data.get("taxes", [])

    metadata = data.get("metadata", {})
    remarks = metadata.get("remarks", "")
    
    if not supplierId:
        return send_response(
            status="fail",
            message="Supplier Id must not be null",
            data=[],
            http_status=400,
            status_code=400
        )
    
    supplier = frappe.db.get_value(
        "Supplier",
        {"custom_supplier_id": supplierId},
        "name"
    )
    
    if not supplier:
        return send_response(
            status="fail",
            message="Supplier not found",
            data=[],
            http_status=404,
            status_code=404
        )
        
    TAX_CAT = CUSTOM_FRAPPE_INSTANCE.GetAvailableTaxCategory()

    if taxCategory not in TAX_CAT:
        return send_response(
            status="fail",
            message=f"Tax Category '{taxCategory}' does not exist.  Available Tax Categories +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++: {TAX_CAT}",
            data=[],
            status_code=400,
            http_status=400
        )

    
    if not costCenter:
        return send_response(
            status="fail",
            message="Cost center must not be null",
            data=[],
            status_code=400,
            http_status=400
        )
        
    if not project:
        return send_response(
            status="fail",
            message="Project name must not null",
            data=[],
            status_code=400,
            http_status=400
        )
        
    costCenterName = ZRA_CLIENT_INSTANCE.GetOrCreateCostCenter("Cost Center", costCenter)
    projectName = ZRA_CLIENT_INSTANCE.GetOrCreateProject(project),
    

    if not shippingRule:
        return send_response(
            status="fail",
            message="Shipping rule must not be null",
            data=[],
            http_status=400,
            status_code=400,
        )
    
    
    if not incoterm:
        return send_response(
            status="fail",
            message="Incoterm must not be null",
            data=[],
            http_status=400,
            status_code=400
        )
        
    incotermName = CUSTOM_FRAPPE_INSTANCE.GetOrCreateIncoterm(incoterm)
    
    invoice_items = []
    for i in items:
        print(i)
        itemCode = i.get("itemCode")
        quantity = i.get("quantity")
        print(quantity)
        
        
        if not itemCode:
            return send_response(
                status="fail",
                message="Item code must not null",
                data=[],
                status_code=400,
                http_status=400
            )
        
        
        if not quantity:
            return send_response(
                status="fail",
                message="Item quantity must not be null",
                data=[],
                status_code=400,
                http_status=400,
            )
        item_details = CUSTOM_FRAPPE_INSTANCE.GetItemDetails(itemCode)
        if not item_details:
            return send_response(
                status="fail",
                message=f"Item '{itemCode}' does not exist",
                status_code=404,
                http_status=404
            )

        
        
        invoice_items.append({
            "item_code": itemCode,
            "item_name": item_details.get("itemName"),
            "warehouse": CUSTOM_FRAPPE_INSTANCE.GetDefaultWareHouse(),
            "qty": quantity,
            "rate": item_details.get("standardRate"),
            "expense_account": CUSTOM_FRAPPE_INSTANCE.getDefaultExpenseAccount(),
        
        })
    
    supplier_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateSupplierAddress(addresses, supplier)
    dispatch_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateDispatchAddress(addresses, supplier)
    shipping_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateShippingAddress(addresses, supplier)
    print(supplier_addr_name, dispatch_addr_name, shipping_addr_name)

    po_doc = frappe.get_doc({
        "doctype": "Purchase Order",
        "supplier": supplier,
        "currency": currency,
        "cost_center": costCenterName,
        "project": projectName,
        "schedule_date": requiredBy,
        "incoterm": incotermName,
        "status": status,
        "custom_placeofsupply": placeOfSupply,
        "custom_remarks": remarks,
        "tax_category": taxCategory,
        "items": invoice_items
    })
            
    for t in taxes:
        tax_type = (t.get("type") or "").strip()
        account_head = (t.get("accountHead") or "").strip()
        rate = float(t.get("taxRate") or 0)
        taxable = float(t.get("taxableAmount") or 0)
        amount = float(t.get("taxAmount") or 0)
        
        valid_tax_types = CUSTOM_FRAPPE_INSTANCE.GetTaxesChargesRate()
        VALID_ACCOUNTS_HEAD = CUSTOM_FRAPPE_INSTANCE.GetExpensesValuationAccount() 

        if tax_type not in valid_tax_types:
            return send_response(
                status="fail",
                message=f"Invalid Tax Type: {tax_type}. Allowed: {', '.join(valid_tax_types)}",
                status_code=400,
                http_status=400
            )
            
        if account_head not in VALID_ACCOUNTS_HEAD:
            return send_response(
                status="fail",
                message=f"Invalid Account Head: {account_head}. Allowed: {', '.join(VALID_ACCOUNTS_HEAD)}",
                status_code=400,
                http_status=400
            )

        po_doc.append("taxes", {
            "charge_type": tax_type,
            "account_head": account_head,
            "rate": rate,
            "tax_amount": amount,
            "total": taxable,
            "description": tax_type
        })
    po_doc.insert(ignore_permissions=True)
    po_doc.save(ignore_permissions=True)
    frappe.db.sql("""
        UPDATE `tabPurchase Order`
        SET supplier_address = %s,
            dispatch_address = %s,
            shipping_address = %s
        WHERE name = %s
    """, (supplier_addr_name, dispatch_addr_name, shipping_addr_name, po_doc.name))

    frappe.db.commit()

    
    CUSTOM_FRAPPE_INSTANCE.createInvoiceTermsAndPayments(po_doc.name, terms)
    
    return send_response(
        status="success",
        message="Purchase order created successfully",
        data=[],
        status_code=201,
        http_status=201,
    )
    
@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_purchase_order():
    return send_response(
        status="success",
        message="Purchase order fetched successfully",
        data=[],
        status_code=200,
        http_status=200,
    )