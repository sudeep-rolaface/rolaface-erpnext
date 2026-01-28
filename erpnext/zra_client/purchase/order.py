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
    taxesChargesTemplate = data.get("taxesChargesTemplate")
    placeOfSupply = data.get("placeOfSupply")
    addresses = data.get("addresses", {})
    supplierAddress = addresses.get("supplierAddress", {})
    dispatchAddress = addresses.get("dispatchAddress", {})
    shippingAddress = addresses.get("shippingAddress", {})
    companyBillingAddress = addresses.get("companyBillingAddress", {})
    
    supplierAddressTitle = supplierAddress.get("addressTitle")
    supplierAddressType = supplierAddress.get("addressType")
    supplierAddressLine1 = supplierAddress.get("addressLine1")
    supplierAddressLine2 = supplierAddress.get("addressLine2")
    supplierAddressCity = supplierAddress.get("city")
    supplierAddressState = supplierAddress.get("state")
    supplierAddressCountry = supplierAddress.get("country")
    supplierAddressPostalCode = supplierAddress.get("postalCode")
    supplierAddressPhone = supplierAddress.get("phone")
    supplierAddressEmail = supplierAddress.get("email")
    
    dispatchAddressTitle = dispatchAddress.get("addressTitle")
    dispatchAddressType = dispatchAddress.get("addressType")
    dispatchAddressLine1 = dispatchAddress.get("addressLine1")
    dispatchAddressLine2 = dispatchAddress.get("addressLine2")
    dispatchAddressCity = dispatchAddress.get("city")
    dispatchAddressState = dispatchAddress.get("state")
    dispatchAddressCountry = dispatchAddress.get("country")
    dispatchAddressPostalCode = dispatchAddress.get("postalCode")
    
    
    shippingAddressTitle = shippingAddress.get("addressTitle")
    shippingAddressType = shippingAddress.get("addressType")
    shippingAddressLine1 = shippingAddress.get("addressLine1")
    shippingAddressLine2 = shippingAddress.get("addressLine2")
    shippingAddressCity = shippingAddress.get("city")
    shippingAddressState = shippingAddress.get("state")
    shippingAddressCountry = shippingAddress.get("country")
    shippingAddressPostalCode = shippingAddress.get("postalCode")
    
    
    shippingAddressTitle = shippingAddress.get("addressTitle")
    shippingAddressType = shippingAddress.get("addressType")
    shippingAddressLine1 = shippingAddress.get("addressLine1")
    shippingAddressLine2 = shippingAddress.get("addressLine2")
    shippingAddressCity = shippingAddress.get("city")
    shippingAddressState = shippingAddress.get("state")
    shippingAddressCountry = shippingAddress.get("country")
    shippingAddressPostalCode = shippingAddress.get("postalCode")

    
    paymentTermsTemplate = data.get("paymentTermsTemplate")
    terms = data.get("terms")
    selling = terms.get("selling") or {}

    general = (selling.get("general") or "").strip()
    delivery = (selling.get("delivery") or "").strip()
    cancellation = (selling.get("cancellation") or "").strip()
    warranty = (selling.get("warranty") or "").strip()
    liability = (selling.get("liability") or "").strip()
    payment_terms_data = selling.get("payment") or {}
    dueDates = payment_terms_data.get("dueDates", "")
    lateCharges = payment_terms_data.get("lateCharges", "")
    tax = payment_terms_data.get("taxes", "")
    notes = payment_terms_data.get("notes", "")
    phases = payment_terms_data.get("phases", [])

    items = data.get("items", [])
        
    taxes = data.get("taxes", [])
    for t in taxes:
        tax_type = t.get("type")
        account = t.get("accountHead")
        rate = t.get("taxRate", 0)
        taxable = t.get("taxableAmount", 0)
        amount = t.get("taxAmount", 0)
        
    payments = data.get("payments", [])
    for p in payments:
        paymentTerm = p.get("paymentTerm", ""),
        description = p.get("description", ""),
        dueDate = p.get("dueDate", ""),
        invoicePortion =p.get("invoicePortion", 0),
        paymentAmount = p.get("paymentAmount", 0)
        
    metadata = data.get("metadata", {})
    created_by = metadata.get("createdBy", "")
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
    
    print("Name: ", costCenterName)
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
            "rate": rate,
            "description": description,
            "expense_account": CUSTOM_FRAPPE_INSTANCE.getDefaultExpenseAccount(),
        
        })
    
    po_doc = frappe.get_doc({
        "doctype": "Purchase Order",
        "supplier": supplier,
        "currency": currency,
        "cost_center": costCenterName,
        "project": projectName,
        "schedule_date": requiredBy,
        "incoterm": incotermName,
        "status": status,
        "items": invoice_items

        
    })
    po_doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return send_response(
        status="sucess",
        message="Purchase order created successfully",
        data=[],
        status_code=201,
        http_status=201,
    )
    
@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_purchase_order():
    return send_response(
        status="sucess",
        message="Purchase order fetched successfully",
        data=[],
        status_code=200,
        http_status=200,
    )