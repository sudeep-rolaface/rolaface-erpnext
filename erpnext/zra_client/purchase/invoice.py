from erpnext.zra_client.purchase.automatic_purchase_helper import PurchaseHelperAutomatic
from erpnext.zra_client.purchase.purchase_helper import PurchaseHelper
from erpnext.zra_client.generic_api import send_response, send_response_list
from erpnext.zra_client.custom_frappe_client import CustomFrappeClient
from erpnext.zra_client.tax_calcalator.tax import TaxCaller
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.purchase.order import get_company_and_currency
from datetime import date, datetime
from frappe import _
import frappe
import random
import json
import re


CUSTOM_FRAPPE_INSTANCE = CustomFrappeClient()
PURCHASE_HELPER_INSTANCE = PurchaseHelper()
AUTOMATIC_PURCHASE_HELPER = PurchaseHelperAutomatic()
ZRA_INSTANCE = ZRAClient()


def is_zra_enabled():
    """Check if ZRA sync is enabled in site config."""
    return frappe.conf.get("enable_zra_sync", False)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: Get or Create Batch
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_batch(item_code, batch_no, company):
    """
    If batch exists  → return it (stock will update when PI is approved).
    If batch missing → create it and return the new batch name.
    """
    existing_batch = frappe.db.exists("Batch", {"name": batch_no, "item": item_code})

    if existing_batch:
        frappe.logger().info(
            f"[BATCH] Existing batch '{batch_no}' found for item '{item_code}'."
        )
        return batch_no

    frappe.logger().info(
        f"[BATCH] Batch '{batch_no}' not found. Creating new batch for item '{item_code}'."
    )

    new_batch = frappe.get_doc({
        "doctype": "Batch",
        "batch_id": batch_no,
        "item": item_code,
        "company": company,
    })
    new_batch.insert(ignore_permissions=True)
    frappe.db.commit()

    return new_batch.name


# ─────────────────────────────────────────────────────────────────────────────
#  CREATE PURCHASE INVOICE
# ─────────────────────────────────────────────────────────────────────────────

# @frappe.whitelist(allow_guest=False, methods=["POST"])
# def create_purchase_invoice():
#     data = frappe.form_dict
#     supplierId = data.get("supplierId")
#     taxCategory = data.get("taxCategory")
#     destnCountryCd = data.get("destnCountryCd")
#     lpoNumber = data.get("lpoNumber")
#     requiredBy = data.get("requiredBy")
#     spplrInvcNo = data.get("spplrInvcNo")
#     pmtType = data.get("paymentType")
#     pchsSttsCd = data.get("transactionProgress")
#     currency = data.get("currency")
#     status = data.get("status")
#     costCenter = data.get("costCenter")
#     project = data.get("project")
#     shippingRule = data.get("shippingRule")
#     incoterm = data.get("incoterm")
#     placeOfSupply = data.get("placeOfSupply")
#     addresses = data.get("addresses", {})
#     terms = data.get("terms")

#     items = data.get("items", [])
#     metadata = data.get("metadata", {})
#     remarks = metadata.get("remarks", "")

#     if not supplierId:
#         return send_response(
#             status="fail",
#             message="Supplier id must not be null",
#             data=[],
#             status_code=400,
#             http_status=400
#         )

#     supplier_check = frappe.db.get_value(
#         "Supplier",
#         {"custom_supplier_id": supplierId},
#         "name"
#     )

#     if not supplier_check:
#         return send_response(
#             status="fail",
#             message="Supplier not found",
#             data=[],
#             http_status=404,
#         )

#     supplier = frappe.get_doc("Supplier", supplier_check)

#     if not taxCategory:
#         return send_response(
#             status="fail",
#             message="Tax category must not be null",
#             data=[],
#             status_code=400,
#             http_status=400
#         )

#     # ZRA-specific: validate taxCategory against ZRA list
#     if is_zra_enabled():
#         TAX_CAT = CUSTOM_FRAPPE_INSTANCE.GetAvailableTaxCategory()
#         if taxCategory not in TAX_CAT:
#             return send_response(
#                 status="fail",
#                 message=f"Tax Category '{taxCategory}' does not exist.  Available Tax Categories : {TAX_CAT}",
#                 data=[],
#                 status_code=400,
#                 http_status=400
#             )

#     if not pchsSttsCd:
#         return send_response(status="fail", message="Transaction Progress is required.", status_code=400, http_status=400)

#     trx_names = CUSTOM_FRAPPE_INSTANCE.GetTransactionProgressNames()
#     trx_codes = CUSTOM_FRAPPE_INSTANCE.GetTransactionProgressCodes()

#     if pchsSttsCd not in trx_names:
#         return send_response(
#             status="fail",
#             message=f"Invalid transaction progress: {pchsSttsCd}. Available : {trx_names}",
#             status_code=400,
#             http_status=400
#         )

#     index = trx_names.index(pchsSttsCd)
#     trxProgCd = trx_codes[index]

#     if not pmtType:
#         return send_response(status="fail", message="paymentType is required.", status_code=400, http_status=400)

#     payment_names = CUSTOM_FRAPPE_INSTANCE.GetPaymentMethodsName()
#     payment_codes = CUSTOM_FRAPPE_INSTANCE.GetPaymentMethodsCodes()

#     if pmtType not in payment_names:
#         return send_response(
#             status="fail",
#             message=f"Invalid payment method: {pmtType}. Available: {payment_names}",
#             status_code=400,
#             http_status=400
#         )

#     index = payment_names.index(pmtType)
#     pmtTyCd = payment_codes[index]

#     if not spplrInvcNo:
#         return send_response(status="fail", message="spplier Invoice No must not be null", status_code=400, http_status=400)

#     if not spplrInvcNo.isdigit():
#         return send_response(
#             status="fail",
#             message="Supplier Invoice No must contain numbers only",
#             status_code=400,
#             http_status=400
#         )

#     invoice_exists = frappe.db.exists(
#         "Purchase Invoice",
#         {
#             "supplier": supplier_check,
#             "bill_no": spplrInvcNo,
#             "docstatus": ["!=", 2]
#         }
#     )

#     if invoice_exists:
#         return send_response(status="fail", message=f"Supplier Invoice No '{spplrInvcNo}' already exists for this supplier", status_code=400, http_status=400)

#     if not costCenter:
#         return send_response(
#             status="fail",
#             message="Cost center must not be null",
#             data=[],
#             status_code=400,
#             http_status=400
#         )

#     if not project:
#         return send_response(
#             status="fail",
#             message="Project name must not null",
#             data=[],
#             status_code=400,
#             http_status=400
#         )

#     # ------------------------------------------------------------------ #
#     #  Resolve company + currency directly from the cost center            #
#     #  (bypasses all Frappe/Redis caching via raw SQL)                     #
#     # ------------------------------------------------------------------ #
#     cost_center_exists = frappe.db.sql(
#         "SELECT name FROM `tabCost Center` WHERE name = %s LIMIT 1",
#         (costCenter,)
#     )
#     if not cost_center_exists:
#         return send_response(
#             status="fail",
#             message=f"Cost Center '{costCenter}' does not exist.",
#             status_code=400,
#             http_status=400,
#             data=[]
#         )

#     company_name, company_currency = get_company_and_currency(costCenter)

#     frappe.logger().info(
#         f"[PI] costCenter='{costCenter}' -> company='{company_name}', "
#         f"company_currency='{company_currency}', requested_currency='{currency}'"
#     )

#     if not company_name:
#         return send_response(
#             status="fail",
#             message=f"Could not determine the company for cost center '{costCenter}'.",
#             data=[],
#             status_code=400,
#             http_status=400
#         )

#     # ✅ company_name resolved — safe to create project under correct company
#     projectName = CUSTOM_FRAPPE_INSTANCE.GetOrCreateProject(project, company_name)

#     purchase_invoice_items = []
#     invoice_items_to_be_saved = []

#     for i in items:
#         print(i)
#         itemCode = i.get("itemCode")
#         quantity = i.get("quantity")
#         vat_cd = i.get("vatCd")
#         rate = i.get("rate")
#         vat_rate = i.get("vatRate", 0)  # ✅ capture vatRate for local tax calculation
#         item_required_by = i.get("requiredBy")
#         batch_no = i.get("batchNo")     # ✅ capture batchNo from payload

#         if not itemCode:
#             return send_response(
#                 status="fail",
#                 message="Item code must not null",
#                 data=[],
#                 status_code=400,
#                 http_status=400
#             )

#         if not rate:
#             return send_response(
#                 status="fail",
#                 message=f"Item code {itemCode} rate must not be null",
#                 status_code=400,
#                 http_status=400,
#                 data=[],
#             )

#         if rate <= 0:
#             return send_response(
#                 status="fail",
#                 message=(
#                     f"Invalid rate for item Code: {itemCode}. "
#                     "Rate must be a positive number greater than 0."
#                 ),
#                 status_code=400,
#                 http_status=400,
#                 data=[],
#             )

#         if not quantity:
#             return send_response(
#                 status="fail",
#                 message="Item quantity must not be null",
#                 data=[],
#                 status_code=400,
#                 http_status=400,
#             )

#         if not vat_cd:
#             return send_response(
#                 status="fail",
#                 message="Vat Category must not be null",
#                 data=[],
#                 status_code=400,
#                 http_status=400
#             )

#         item_details = CUSTOM_FRAPPE_INSTANCE.GetItemInfo(itemCode)

#         if not item_details:
#             return send_response(
#                 status="fail",
#                 message=f"Item '{itemCode}' does not exist",
#                 status_code=404,
#                 http_status=404
#             )

#         # ✅ ZRA-specific VAT validations — only when ZRA is enabled
#         if is_zra_enabled():
#             VAT_LIST = CUSTOM_FRAPPE_INSTANCE.GetValidTaxTypes()
#             if vat_cd not in VAT_LIST:
#                 return send_response(status="fail", message=f"Invalid VAT code {vat_cd}", status_code=400)

#             if taxCategory == "LPO" and vat_cd != "C2":
#                 return send_response(
#                     status="fail",
#                     message="vatCd must be 'C2' when taxCategory is 'LPO'",
#                     status_code=400,
#                     http_status=400
#                 )

#             if vat_cd == "C1" and not destnCountryCd:
#                 return send_response(status="fail", message="Destination country required for VAT C1", status_code=400)

#             if taxCategory == "Export" and vat_cd != "C1":
#                 return send_response(
#                     status="fail",
#                     message="vatCd must be 'C1' when taxCategory is 'Export'",
#                     status_code=400,
#                     http_status=400
#                 )

#             if taxCategory == "Non-Export" and vat_cd != "A":
#                 return send_response(
#                     status="fail",
#                     message="vatCd must be 'A' when taxCategory is 'Non-Export'",
#                     status_code=400,
#                     http_status=400
#                 )

#             if vat_cd == "A":
#                 if lpoNumber is not None or destnCountryCd is not None:
#                     return send_response(
#                         status="fail",
#                         message="LPO number and destination country must not be provided when VAT code is 'A'.",
#                         status_code=400
#                     )

#         # ── Batch Handling — Create if not exists ─────────────────────────────
#         resolved_batch_no = None

#         if item_details.get("has_batch_no"):
#             if not batch_no:
#                 return send_response(
#                     status="fail",
#                     message=f"Item '{itemCode}' requires a batch number (batchNo).",
#                     data=[],
#                     status_code=400,
#                     http_status=400
#                 )
#             # ✅ Reuse existing batch or create a new one
#             resolved_batch_no = get_or_create_batch(itemCode, batch_no, company_name)

#         purchase_invoice_items.append({
#             "itemCode": itemCode,
#             "itemName": item_details.get("itemName"),
#             "qty": quantity,
#             "itemClassCode": item_details.get("itemClassCd"),
#             "packageUnitCode": item_details.get("itemPackingUnitCd"),
#             "price": rate,
#             "VatCd": vat_cd,
#             "unitOfMeasure": item_details.get("itemUnitCd"),
#             "schedule_date": item_required_by,
#             "warehouse": CUSTOM_FRAPPE_INSTANCE.GetDefaultWareHouse(company_name)
#         })

#         invoice_items_to_be_saved.append({
#             "item_code": itemCode,
#             "item_name": item_details.get("itemName"),
#             "warehouse": CUSTOM_FRAPPE_INSTANCE.GetDefaultWareHouse(company_name),
#             "custom_vat": vat_cd,
#             "qty": quantity,
#             "rate": rate,
#             "schedule_date": item_required_by,
#             "batch_no": resolved_batch_no,  # ✅ None if item doesn't use batches
#         })

#     supplierName = supplier.supplier_name
#     supplierTpin = supplier.tax_id

#     if not shippingRule:
#         return send_response(
#             status="fail",
#             message="Shipping rule must not be null",
#             data=[],
#             http_status=400,
#             status_code=400,
#         )

#     if not incoterm:
#         return send_response(
#             status="fail",
#             message="Incoterm must not be null",
#             data=[],
#             http_status=400,
#             status_code=400
#         )

#     # if not requiredBy:
#     #     return send_response(
#     #         status="fail",
#     #         message="Required By date must not be null.",
#     #         data=[],
#     #         status_code=400,
#     #     )
#     if requiredBy:
#         requiredBy = datetime.strptime(requiredBy, "%Y-%m-%d").date()
#         today = date.today()

#         if requiredBy < today:
#             return send_response(
#                 status="fail",
#                 message=f"Required By '{requiredBy}' cannot be before today's date '{today}'.",
#                 data=[],
#                 status_code=400,
#                 http_status=400
#             )

#     incotermName = CUSTOM_FRAPPE_INSTANCE.GetOrCreateIncoterm(incoterm)
#     supplier_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateSupplierAddress(addresses, supplier_check)
#     dispatch_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateDispatchAddress(addresses, supplier_check)
#     shipping_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateShippingAddress(addresses, supplier_check)
#     print(supplier_addr_name, dispatch_addr_name, shipping_addr_name)

#     # ------------------------------------------------------------------ #
#     #  ZRA sync OR local tax calculation                                   #
#     # ------------------------------------------------------------------ #
#     if is_zra_enabled():
#         purchase_invoice_payload = {
#             "supplierName": supplierName,
#             "supplierTpin": supplierTpin,
#             "supplierId": supplierId,
#             "spplrInvcNo": spplrInvcNo,
#             "pmtTyCd": pmtTyCd,
#             "pchsSttsCd": trxProgCd,
#             "items": purchase_invoice_items
#         }

#         results = PURCHASE_HELPER_INSTANCE.send_purchase_data(purchase_invoice_payload)
#         print("Results: ", results)
#         resultCd = results.get("resultCd")
#         resultMsg = results.get("resultMsg")
#         payload = results.get("payload")

#         if resultCd != "000":
#             return send_response(
#                 status="fail",
#                 message=resultMsg,
#                 data=[],
#                 status_code=400,
#                 http_status=400
#             )

#         total_taxable_amount = payload.get("totTaxblAmt", 0)
#         total_tax_amount = payload.get("totTaxAmt", 0)

#     else:
#         # ✅ ZRA disabled — calculate tax locally using vatRate from each item
#         total_taxable_amount = 0
#         total_tax_amount = 0

#         for i in items:
#             qty = i.get("quantity", 0)
#             rate = i.get("rate", 0)
#             vat_rate = i.get("vatRate", 0)

#             line_total = qty * rate
#             line_tax = round(line_total * vat_rate / 100, 2)

#             total_taxable_amount += line_total
#             total_tax_amount += line_tax

#         total_taxable_amount = round(total_taxable_amount, 2)
#         total_tax_amount = round(total_tax_amount, 2)

#         frappe.logger().info(
#             f"[PI] ZRA disabled — local tax calc: "
#             f"taxable={total_taxable_amount}, tax={total_tax_amount}"
#         )

#     # ------------------------------------------------------------------ #
#     #  Save the Purchase Invoice (Draft — NO stock movement yet)           #
#     # ------------------------------------------------------------------ #
#     purchase_invoice = frappe.get_doc({
#         "doctype": "Purchase Invoice",
#         "supplier": supplier_check,
#         "company": company_name,
#         "currency": currency or company_currency,
#         "cost_center": costCenter,
#         "project": projectName,
#         "schedule_date": requiredBy,
#         "incoterm": incotermName,
#         "status": status,
#         "tax_category": taxCategory,
#         "custom_total_taxble_amount": total_taxable_amount,
#         "custom_total_tax_amount": total_tax_amount,
#         "items": invoice_items_to_be_saved,
#         "remarks": remarks,
#         "bill_no": spplrInvcNo,
#         "update_stock": 0,              # ✅ stock moves only on approval (approve endpoint)
#         "supplier_address": supplier_addr_name,
#         "dispatch_address": dispatch_addr_name,
#         "shipping_address": shipping_addr_name,
#         "custom_place_of_supply": placeOfSupply,
#         "custom_registration_type": "Manual",
#         "custom_payment_method": pmtType,
#         "custom_transaction_progress": pchsSttsCd,
#         "custom_destncountrycd": destnCountryCd,
#         "custom_lpo_number": lpoNumber
#     })

#     purchase_invoice.insert(ignore_permissions=True)
#     purchase_invoice.save(ignore_permissions=True)
#     frappe.db.commit()

#     CUSTOM_FRAPPE_INSTANCE.createInvoiceTermsAndPayments(purchase_invoice.name, terms)

#     return send_response(
#         status="success",
#         message="Purchase invoice created sucessfully",
#         status_code=201,
#         http_status=201
#     )


# # ─────────────────────────────────────────────────────────────────────────────
# #  APPROVE PURCHASE INVOICE — sets update_stock=1 then submits
# # ─────────────────────────────────────────────────────────────────────────────

# @frappe.whitelist(allow_guest=False, methods=["PATCH"])
# def approve_purchase_invoice():
#     data = frappe.form_dict
#     invoice_name = data.get("invoiceName")

#     if not invoice_name:
#         return send_response(
#             status="fail",
#             message="invoiceName is required.",
#             status_code=400,
#             http_status=400
#         )

#     if not frappe.db.exists("Purchase Invoice", invoice_name):
#         return send_response(
#             status="fail",
#             message=f"Purchase Invoice '{invoice_name}' does not exist.",
#             status_code=404,
#             http_status=404
#         )

#     pi = frappe.get_doc("Purchase Invoice", invoice_name)

#     if pi.docstatus == 1:
#         return send_response(
#             status="fail",
#             message=f"Purchase Invoice '{invoice_name}' is already submitted.",
#             status_code=400,
#             http_status=400
#         )

#     if pi.docstatus == 2:
#         return send_response(
#             status="fail",
#             message=f"Purchase Invoice '{invoice_name}' is cancelled and cannot be approved.",
#             status_code=400,
#             http_status=400
#         )

#     # ✅ Validate batch items before approving
#     for item in pi.items:
#         item_has_batch = frappe.db.get_value("Item", item.item_code, "has_batch_no")

#         if item_has_batch and not item.batch_no:
#             return send_response(
#                 status="fail",
#                 message=f"Item '{item.item_code}' requires a batch number before approval.",
#                 status_code=400,
#                 http_status=400
#             )

#         if item.batch_no and not frappe.db.exists("Batch", {"name": item.batch_no, "item": item.item_code}):
#             return send_response(
#                 status="fail",
#                 message=f"Batch '{item.batch_no}' no longer exists for item '{item.item_code}'.",
#                 status_code=400,
#                 http_status=400
#             )

#     try:
#         # ✅ Step 1: Write update_stock=1 directly to DB — bypasses Frappe cache
#         frappe.db.set_value("Purchase Invoice", invoice_name, "update_stock", 1, update_modified=False)
#         frappe.db.commit()

#         # ✅ Step 2: Fresh reload from DB — guaranteed to pick up update_stock=1
#         pi = frappe.get_doc("Purchase Invoice", invoice_name)

#         frappe.logger().info(
#             f"[PI APPROVE] '{invoice_name}' update_stock={pi.update_stock} — submitting."
#         )

#         # ✅ Step 3: Submit — Stock Ledger Entry created, inventory updated
#         pi.submit()
#         frappe.db.commit()

#         frappe.logger().info(
#             f"[PI APPROVE] '{invoice_name}' submitted successfully. Inventory updated."
#         )

#     except Exception as e:
#         frappe.db.rollback()
#         frappe.log_error(frappe.get_traceback(), "Approve Purchase Invoice Error")
#         return send_response(
#             status="fail",
#             message=f"Failed to approve invoice: {str(e)}",
#             status_code=500,
#             http_status=500
#         )

#     return send_response(
#         status="success",
#         message="Purchase invoice approved and inventory updated successfully.",
#         status_code=200,
#         http_status=200
#     )



# ─────────────────────────────────────────────────────────────────────────────
#  CREATE PURCHASE INVOICE
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_purchase_invoice():
    data = frappe.form_dict
    supplierId = data.get("supplierId")
    taxCategory = data.get("taxCategory")
    destnCountryCd = data.get("destnCountryCd")
    lpoNumber = data.get("lpoNumber")
    requiredBy = data.get("requiredBy")
    spplrInvcNo = data.get("spplrInvcNo")
    pmtType = data.get("paymentType")
    pchsSttsCd = data.get("transactionProgress")
    currency = data.get("currency")
    status = data.get("status")
    costCenter = data.get("costCenter")
    project = data.get("project")
    shippingRule = data.get("shippingRule")
    incoterm = data.get("incoterm")
    placeOfSupply = data.get("placeOfSupply")
    addresses = data.get("addresses", {})
    terms = data.get("terms")

    items = data.get("items", [])
    metadata = data.get("metadata", {})
    remarks = metadata.get("remarks", "")

    if not supplierId:
        return send_response(
            status="fail",
            message="Supplier id must not be null",
            data=[],
            status_code=400,
            http_status=400
        )

    supplier_check = frappe.db.get_value(
        "Supplier",
        {"custom_supplier_id": supplierId},
        "name"
    )

    if not supplier_check:
        return send_response(
            status="fail",
            message="Supplier not found",
            data=[],
            http_status=404,
        )

    supplier = frappe.get_doc("Supplier", supplier_check)

    if not taxCategory:
        return send_response(
            status="fail",
            message="Tax category must not be null",
            data=[],
            status_code=400,
            http_status=400
        )

    # ZRA-specific: validate taxCategory against ZRA list
    if is_zra_enabled():
        TAX_CAT = CUSTOM_FRAPPE_INSTANCE.GetAvailableTaxCategory()
        if taxCategory not in TAX_CAT:
            return send_response(
                status="fail",
                message=f"Tax Category '{taxCategory}' does not exist.  Available Tax Categories : {TAX_CAT}",
                data=[],
                status_code=400,
                http_status=400
            )

    if not pchsSttsCd:
        return send_response(status="fail", message="Transaction Progress is required.", status_code=400, http_status=400)

    trx_names = CUSTOM_FRAPPE_INSTANCE.GetTransactionProgressNames()
    trx_codes = CUSTOM_FRAPPE_INSTANCE.GetTransactionProgressCodes()

    if pchsSttsCd not in trx_names:
        return send_response(
            status="fail",
            message=f"Invalid transaction progress: {pchsSttsCd}. Available : {trx_names}",
            status_code=400,
            http_status=400
        )

    index = trx_names.index(pchsSttsCd)
    trxProgCd = trx_codes[index]

    if not pmtType:
        return send_response(status="fail", message="paymentType is required.", status_code=400, http_status=400)

    payment_names = CUSTOM_FRAPPE_INSTANCE.GetPaymentMethodsName()
    payment_codes = CUSTOM_FRAPPE_INSTANCE.GetPaymentMethodsCodes()

    if pmtType not in payment_names:
        return send_response(
            status="fail",
            message=f"Invalid payment method: {pmtType}. Available: {payment_names}",
            status_code=400,
            http_status=400
        )

    index = payment_names.index(pmtType)
    pmtTyCd = payment_codes[index]

    if not spplrInvcNo:
        return send_response(status="fail", message="spplier Invoice No must not be null", status_code=400, http_status=400)

    if not spplrInvcNo.isdigit():
        return send_response(
            status="fail",
            message="Supplier Invoice No must contain numbers only",
            status_code=400,
            http_status=400
        )

    invoice_exists = frappe.db.exists(
        "Purchase Invoice",
        {
            "supplier": supplier_check,
            "bill_no": spplrInvcNo,
            "docstatus": ["!=", 2]
        }
    )

    if invoice_exists:
        return send_response(status="fail", message=f"Supplier Invoice No '{spplrInvcNo}' already exists for this supplier", status_code=400, http_status=400)

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

    # ------------------------------------------------------------------ #
    #  Resolve company + currency directly from the cost center            #
    #  (bypasses all Frappe/Redis caching via raw SQL)                     #
    # ------------------------------------------------------------------ #
    cost_center_exists = frappe.db.sql(
        "SELECT name FROM `tabCost Center` WHERE name = %s LIMIT 1",
        (costCenter,)
    )
    if not cost_center_exists:
        return send_response(
            status="fail",
            message=f"Cost Center '{costCenter}' does not exist.",
            status_code=400,
            http_status=400,
            data=[]
        )

    company_name, company_currency = get_company_and_currency(costCenter)

    frappe.logger().info(
        f"[PI] costCenter='{costCenter}' -> company='{company_name}', "
        f"company_currency='{company_currency}', requested_currency='{currency}'"
    )

    if not company_name:
        return send_response(
            status="fail",
            message=f"Could not determine the company for cost center '{costCenter}'.",
            data=[],
            status_code=400,
            http_status=400
        )

    # ✅ company_name resolved — safe to create project under correct company
    projectName = CUSTOM_FRAPPE_INSTANCE.GetOrCreateProject(project, company_name)

    purchase_invoice_items = []
    invoice_items_to_be_saved = []

    for i in items:
        print(i)
        itemCode = i.get("itemCode")
        quantity = i.get("quantity")
        vat_cd = i.get("vatCd")
        rate = i.get("rate")
        vat_rate = i.get("vatRate", 0)  # ✅ capture vatRate for local tax calculation
        item_required_by = i.get("requiredBy")
        batch_no = i.get("batchNo")     # ✅ capture batchNo from payload

        if not itemCode:
            return send_response(
                status="fail",
                message="Item code must not null",
                data=[],
                status_code=400,
                http_status=400
            )

        if not rate:
            return send_response(
                status="fail",
                message=f"Item code {itemCode} rate must not be null",
                status_code=400,
                http_status=400,
                data=[],
            )

        if rate <= 0:
            return send_response(
                status="fail",
                message=(
                    f"Invalid rate for item Code: {itemCode}. "
                    "Rate must be a positive number greater than 0."
                ),
                status_code=400,
                http_status=400,
                data=[],
            )

        if not quantity:
            return send_response(
                status="fail",
                message="Item quantity must not be null",
                data=[],
                status_code=400,
                http_status=400,
            )

        if not vat_cd:
            return send_response(
                status="fail",
                message="Vat Category must not be null",
                data=[],
                status_code=400,
                http_status=400
            )

        item_details = CUSTOM_FRAPPE_INSTANCE.GetItemInfo(itemCode)

        if not item_details:
            return send_response(
                status="fail",
                message=f"Item '{itemCode}' does not exist",
                status_code=404,
                http_status=404
            )

        # ✅ ZRA-specific VAT validations — only when ZRA is enabled
        if is_zra_enabled():
            VAT_LIST = CUSTOM_FRAPPE_INSTANCE.GetValidTaxTypes()
            if vat_cd not in VAT_LIST:
                return send_response(status="fail", message=f"Invalid VAT code {vat_cd}", status_code=400)

            if taxCategory == "LPO" and vat_cd != "C2":
                return send_response(
                    status="fail",
                    message="vatCd must be 'C2' when taxCategory is 'LPO'",
                    status_code=400,
                    http_status=400
                )

            if vat_cd == "C1" and not destnCountryCd:
                return send_response(status="fail", message="Destination country required for VAT C1", status_code=400)

            if taxCategory == "Export" and vat_cd != "C1":
                return send_response(
                    status="fail",
                    message="vatCd must be 'C1' when taxCategory is 'Export'",
                    status_code=400,
                    http_status=400
                )

            if taxCategory == "Non-Export" and vat_cd != "A":
                return send_response(
                    status="fail",
                    message="vatCd must be 'A' when taxCategory is 'Non-Export'",
                    status_code=400,
                    http_status=400
                )

            if vat_cd == "A":
                if lpoNumber is not None or destnCountryCd is not None:
                    return send_response(
                        status="fail",
                        message="LPO number and destination country must not be provided when VAT code is 'A'.",
                        status_code=400
                    )

        # ── Batch Handling — Create if not exists ─────────────────────────────
        resolved_batch_no = None

        if item_details.get("has_batch_no"):
            if not batch_no:
                return send_response(
                    status="fail",
                    message=f"Item '{itemCode}' requires a batch number (batchNo).",
                    data=[],
                    status_code=400,
                    http_status=400
                )
            # ✅ Reuse existing batch or create a new one
            resolved_batch_no = get_or_create_batch(itemCode, batch_no, company_name)

        purchase_invoice_items.append({
            "itemCode": itemCode,
            "itemName": item_details.get("itemName"),
            "qty": quantity,
            "itemClassCode": item_details.get("itemClassCd"),
            "packageUnitCode": item_details.get("itemPackingUnitCd"),
            "price": rate,
            "VatCd": vat_cd,
            "unitOfMeasure": item_details.get("itemUnitCd"),
            "schedule_date": item_required_by,
            "warehouse": CUSTOM_FRAPPE_INSTANCE.GetDefaultWareHouse(company_name)
        })

        invoice_items_to_be_saved.append({
            "item_code": itemCode,
            "item_name": item_details.get("itemName"),
            "warehouse": CUSTOM_FRAPPE_INSTANCE.GetDefaultWareHouse(company_name),
            "custom_vat": vat_cd,
            "qty": quantity,
            "rate": rate,
            "schedule_date": item_required_by,
            "batch_no": resolved_batch_no,  # ✅ None if item doesn't use batches
        })

    supplierName = supplier.supplier_name
    supplierTpin = supplier.tax_id

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

    # if not requiredBy:
    #     return send_response(
    #         status="fail",
    #         message="Required By date must not be null.",
    #         data=[],
    #         status_code=400,
    #     )
    if requiredBy:
        requiredBy = datetime.strptime(requiredBy, "%Y-%m-%d").date()
        today = date.today()

        if requiredBy < today:
            return send_response(
                status="fail",
                message=f"Required By '{requiredBy}' cannot be before today's date '{today}'.",
                data=[],
                status_code=400,
                http_status=400
            )

    incotermName = CUSTOM_FRAPPE_INSTANCE.GetOrCreateIncoterm(incoterm)
    supplier_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateSupplierAddress(addresses, supplier_check)
    dispatch_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateDispatchAddress(addresses, supplier_check)
    shipping_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateShippingAddress(addresses, supplier_check)
    print(supplier_addr_name, dispatch_addr_name, shipping_addr_name)

    # ------------------------------------------------------------------ #
    #  ZRA sync OR local tax calculation                                   #
    # ------------------------------------------------------------------ #
    if is_zra_enabled():
        purchase_invoice_payload = {
            "supplierName": supplierName,
            "supplierTpin": supplierTpin,
            "supplierId": supplierId,
            "spplrInvcNo": spplrInvcNo,
            "pmtTyCd": pmtTyCd,
            "pchsSttsCd": trxProgCd,
            "items": purchase_invoice_items
        }

        results = PURCHASE_HELPER_INSTANCE.send_purchase_data(purchase_invoice_payload)
        print("Results: ", results)
        resultCd = results.get("resultCd")
        resultMsg = results.get("resultMsg")
        payload = results.get("payload")

        if resultCd != "000":
            return send_response(
                status="fail",
                message=resultMsg,
                data=[],
                status_code=400,
                http_status=400
            )

        total_taxable_amount = payload.get("totTaxblAmt", 0)
        total_tax_amount = payload.get("totTaxAmt", 0)

    else:
        # ✅ ZRA disabled — calculate tax locally using vatRate from each item
        total_taxable_amount = 0
        total_tax_amount = 0

        for i in items:
            qty = i.get("quantity", 0)
            rate = i.get("rate", 0)
            vat_rate = i.get("vatRate", 0)

            line_total = qty * rate
            line_tax = round(line_total * vat_rate / 100, 2)

            total_taxable_amount += line_total
            total_tax_amount += line_tax

        total_taxable_amount = round(total_taxable_amount, 2)
        total_tax_amount = round(total_tax_amount, 2)

        frappe.logger().info(
            f"[PI] ZRA disabled — local tax calc: "
            f"taxable={total_taxable_amount}, tax={total_tax_amount}"
        )

    # ------------------------------------------------------------------ #
    #  Save the Purchase Invoice (Draft — NO stock movement yet)           #
    # ------------------------------------------------------------------ #
    purchase_invoice = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "supplier": supplier_check,
        "company": company_name,
        "currency": currency or company_currency,
        "cost_center": costCenter,
        "project": projectName,
        "schedule_date": requiredBy,
        "incoterm": incotermName,
        "status": status,
        "tax_category": taxCategory,
        "custom_total_taxble_amount": total_taxable_amount,
        "custom_total_tax_amount": total_tax_amount,
        "items": invoice_items_to_be_saved,
        "remarks": remarks,
        "bill_no": spplrInvcNo,
        "update_stock": 0,              # ✅ stock moves only on approval (approve endpoint)
        "supplier_address": supplier_addr_name,
        "dispatch_address": dispatch_addr_name,
        "shipping_address": shipping_addr_name,
        "custom_place_of_supply": placeOfSupply,
        "custom_registration_type": "Manual",
        "custom_payment_method": pmtType,
        "custom_transaction_progress": pchsSttsCd,
        "custom_destncountrycd": destnCountryCd,
        "custom_lpo_number": lpoNumber
    })

    purchase_invoice.insert(ignore_permissions=True)
    purchase_invoice.save(ignore_permissions=True)
    frappe.db.commit()

    CUSTOM_FRAPPE_INSTANCE.createInvoiceTermsAndPayments(purchase_invoice.name, terms)

    return send_response(
        status="success",
        message="Purchase invoice created sucessfully",
        status_code=201,
        http_status=201
    )


# ─────────────────────────────────────────────────────────────────────────────
#  APPROVE PURCHASE INVOICE — sets update_stock=1 then submits
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False, methods=["PATCH"])
def approve_purchase_invoice():
    data = frappe.form_dict
    invoice_name = data.get("invoiceName")

    if not invoice_name:
        return send_response(
            status="fail",
            message="invoiceName is required.",
            status_code=400,
            http_status=400
        )

    if not frappe.db.exists("Purchase Invoice", invoice_name):
        return send_response(
            status="fail",
            message=f"Purchase Invoice '{invoice_name}' does not exist.",
            status_code=404,
            http_status=404
        )

    pi = frappe.get_doc("Purchase Invoice", invoice_name)

    if pi.docstatus == 1:
        return send_response(
            status="fail",
            message=f"Purchase Invoice '{invoice_name}' is already submitted.",
            status_code=400,
            http_status=400
        )

    if pi.docstatus == 2:
        return send_response(
            status="fail",
            message=f"Purchase Invoice '{invoice_name}' is cancelled and cannot be approved.",
            status_code=400,
            http_status=400
        )

    # ✅ Batch was already validated and created during create_purchase_invoice
    # ✅ Only verify batch still exists if batch_no is assigned on the PI item
    for item in pi.items:
        if item.batch_no:
            if not frappe.db.exists("Batch", {"name": item.batch_no, "item": item.item_code}):
                return send_response(
                    status="fail",
                    message=f"Batch '{item.batch_no}' no longer exists for item '{item.item_code}'.",
                    status_code=400,
                    http_status=400
                )

    try:
        # ✅ Step 1: Write update_stock=1 directly to DB — bypasses Frappe cache
        frappe.db.set_value("Purchase Invoice", invoice_name, "update_stock", 1, update_modified=False)
        frappe.db.commit()

        # ✅ Step 2: Fresh reload from DB — guaranteed to pick up update_stock=1
        pi = frappe.get_doc("Purchase Invoice", invoice_name)

        frappe.logger().info(
            f"[PI APPROVE] '{invoice_name}' update_stock={pi.update_stock} — submitting."
        )

        # ✅ Step 3: Submit — Stock Ledger Entry created, inventory updated
        pi.submit()
        frappe.db.commit()

        frappe.logger().info(
            f"[PI APPROVE] '{invoice_name}' submitted successfully. Inventory updated."
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Approve Purchase Invoice Error")
        return send_response(
            status="fail",
            message=f"Failed to approve invoice: {str(e)}",
            status_code=500,
            http_status=500
        )

    return send_response(
        status="success",
        message="Purchase invoice approved and inventory updated successfully.",
        status_code=200,
        http_status=200
    )


# ─────────────────────────────────────────────────────────────────────────────
#  GET ALL PURCHASE INVOICES
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_all_purchase_invoices():
    try:
        args = frappe.request.args
        page = args.get("page")
        if not page:
            return send_response(
                status="error",
                message="'page' parameter is required.",
                data=None,
                status_code=400,
                http_status=400
            )

        try:
            page = int(page)
            if page < 1:
                raise ValueError
        except ValueError:
            return send_response(
                status="error",
                message="'page' must be a positive integer.",
                data=None,
                status_code=400,
                http_status=400
            )

        page_size = args.get("page_size")
        if not page_size:
            return send_response(
                status="error",
                message="'page_size' parameter is required.",
                data=None,
                status_code=400,
                http_status=400
            )

        try:
            page_size = int(page_size)
            if page_size < 1:
                raise ValueError
        except ValueError:
            return send_response(
                status="error",
                message="'page_size' must be a positive integer.",
                data=None,
                status_code=400,
                http_status=400
            )

        start = (page - 1) * page_size
        end = start + page_size

        status_filter = args.get("status")
        supplier_filter = args.get("supplier")

        filters = {}
        if status_filter:
            filters["status"] = status_filter
        if supplier_filter:
            filters["supplier"] = supplier_filter

        all_pos = frappe.get_all(
            "Purchase Invoice",
            fields=[
                "name",
                "supplier",
                "posting_date",
                "due_date",
                "grand_total",
                "custom_registration_type",
                "custom_sync_status",
                "status",
            ],
            filters=filters,
            order_by="creation desc"
        )

        total_items = len(all_pos)

        if total_items == 0:
            return send_response(
                status="success",
                message="No purchase invoice found.",
                data=[],
                status_code=200,
                http_status=200
            )

        pos = all_pos[start:end]

        for po in pos:
            po["pId"] = po.pop("name")
            po["supplierName"] = po.pop("supplier")
            po["poDate"] = str(po.pop("posting_date")) if po.get("posting_date") else None
            po["deliveryDate"] = str(po.pop("due_date")) if po.get("due_date") else None
            po["grandTotal"] = po.pop("grand_total")
            po["registrationType"] = po.pop("custom_registration_type")
            po["syncStatus"] = po.pop("custom_sync_status")

        total_pages = (total_items + page_size - 1) // page_size

        response_data = {
            "success": True,
            "message": "Purchase invoice retrieved successfully",
            "data": pos,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }

        return send_response_list(
            status="success",
            message="Purchase orders retrieved successfully",
            status_code=200,
            data=response_data,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Get Purchase Orders API Error")
        return send_response(
            status="fail",
            message="Failed to fetch purchase orders",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )


# ─────────────────────────────────────────────────────────────────────────────
#  GET PURCHASE INVOICE BY ID
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_purchase_invoice_by_id():
    try:
        args = frappe.request.args
        pId = args.get("id")

        if not pId:
            return send_response(
                status="fail",
                message="'id' parameter is required.",
                data=[],
                status_code=400,
                http_status=400
            )

        po = frappe.db.get_value(
            "Purchase Invoice",
            pId,
            [
                "name",
                "supplier",
                "posting_date",
                "due_date",
                "grand_total",
                "status",
                "currency",
                "tax_category",
                "custom_place_of_supply",
                "remarks",
                "supplier_address",
                "dispatch_address",
                "shipping_address",
                "incoterm",
                "project",
                "cost_center",
                "custom_total_tax_amount",
                "custom_total_taxble_amount",
                "owner",
                "creation",
                "modified",
                "bill_no",
                "custom_registration_type",
                "custom_payment_method",
                "custom_transaction_progress",
                "custom_destncountrycd",
                "custom_lpo_number",
                "custom_sync_status",
                "company",
            ],
            as_dict=True
        )

        if not po:
            return send_response(
                status="fail",
                message=f"Purchase Invoice '{pId}' not found.",
                data=[],
                status_code=404,
                http_status=404
            )

        items = frappe.get_all(
            "Purchase Invoice Item",
            filters={"parent": pId},
            fields=[
                "item_code",
                "item_name",
                "qty",
                "uom",
                "rate",
                "amount",
                "custom_vat as VatCd"
            ]
        )

        total_quantity = sum(item.get("qty", 0) for item in items)
        sub_total = sum(item.get("amount", 0) for item in items)
        grand_total = po.grand_total or 0
        rounded_total = po.get("rounded_total") or grand_total
        rounding_adjustment = rounded_total - grand_total

        summary = {
            "totalQuantity": total_quantity,
            "subTotal": sub_total,
            "taxTotal": po.custom_total_tax_amount,
            "grandTotal": grand_total,
            "roundingAdjustment": rounding_adjustment,
            "roundedTotal": rounded_total
        }

        taxRate = "16%" if po.tax_category == "Non-Export" else "0%"
        
        # Calculate effective tax rate if available
        if po.custom_total_taxble_amount and float(po.custom_total_taxble_amount or 0) > 0:
            effective_rate = (
                float(po.custom_total_tax_amount or 0)
                / float(po.custom_total_taxble_amount)
                * 100
            )
            if effective_rate > 0:
                taxRate = f"{round(effective_rate, 2)}%"
        
        taxes = {
            "type": po.tax_category,
            "taxRate": taxRate,
            "taxableAmount": po.custom_total_taxble_amount,
            "taxAmount": po.custom_total_tax_amount
        }

        def get_purchase_terms():
            """Fetch buying terms from Company settings"""
            
            # Get company from Purchase Invoice
            company_name = po.get("company")
            if not company_name:
                return {"terms": {"buying": {}}}
            
            # Get custom_company_id from Company
            custom_company_id = frappe.db.get_value(
                "Company",
                company_name,
                "custom_company_id"
            )
            
            if not custom_company_id:
                return {"terms": {"buying": {}}}
            
            # ── Get Buying Terms ──────────────────────────────────────────────
            buying_terms_doc = None
            if frappe.db.exists("Company Buying Terms", {"company": custom_company_id}):
                buying_terms_doc = frappe.get_doc("Company Buying Terms", {"company": custom_company_id})
            
            # ── Get Buying Payment ────────────────────────────────────────────
            buying_payment_doc = None
            if frappe.db.exists("Company Buying Payments", {"company": custom_company_id}):
                buying_payment_doc = frappe.get_doc("Company Buying Payments", {"company": custom_company_id})
            
            # ── Get Buying Payment Phases ─────────────────────────────────────
            phases = frappe.get_all(
                "Company Buying Payments Phases",
                filters={"company": custom_company_id},
                fields=["id", "phase_name as name", "percentage", "condition"],
            )
            
            return {
                "terms": {
                    "buying": {
                        "general": getattr(buying_terms_doc, "general", "") if buying_terms_doc else "",
                        "delivery": getattr(buying_terms_doc, "delivery", "") if buying_terms_doc else "",
                        "cancellation": getattr(buying_terms_doc, "cancellation", "") if buying_terms_doc else "",
                        "warranty": getattr(buying_terms_doc, "warranty", "") if buying_terms_doc else "",
                        "liability": getattr(buying_terms_doc, "liability", "") if buying_terms_doc else "",
                        "payment": {
                            "type": getattr(buying_payment_doc, "type", "") if buying_payment_doc else "",
                            "dueDates": getattr(buying_payment_doc, "duedates", "") if buying_payment_doc else "",
                            "lateCharges": getattr(buying_payment_doc, "latecharges", "") if buying_payment_doc else "",
                            "taxes": getattr(buying_payment_doc, "taxes", "") if buying_payment_doc else "",
                            "notes": getattr(buying_payment_doc, "specialnotes", "") if buying_payment_doc else "",
                            "phases": phases,
                        },
                    }
                }
            }

        def get_address_details(address_name, include_contact=False):
            if not address_name:
                return None

            fields = [
                "name", "address_title", "address_type",
                "address_line1", "address_line2",
                "city", "state", "country", "pincode",
            ]
            if include_contact:
                fields += ["phone", "email_id"]

            addr = frappe.db.get_value("Address", address_name, fields, as_dict=True)
            if not addr:
                return None

            data = {
                "addressId": addr.name,
                "addressTitle": addr.address_title,
                "addressType": addr.address_type,
                "addressLine1": addr.address_line1,
                "addressLine2": addr.address_line2,
                "city": addr.city,
                "state": addr.state,
                "country": addr.country,
                "postalCode": addr.pincode,
            }
            if include_contact:
                data["phone"] = addr.phone
                data["email"] = addr.email_id

            return data

        supplier_addr = get_address_details(po.supplier_address, include_contact=True)
        dispatch_addr = get_address_details(po.dispatch_address, include_contact=False)
        shipping_addr = get_address_details(po.shipping_address, include_contact=False)

        response_data = {
            "pId": po.name,
            "supplierName": po.supplier,
            "spplrInvcNo": po.bill_no,
            "pDate": str(po.posting_date) if po.posting_date else None,
            "requiredBy": str(po.due_date) if po.due_date else None,
            "currency": po.currency,
            "status": po.status,
            "grandTotal": po.grand_total,
            "taxCategory": po.tax_category,
            "placeOfSupply": po.custom_place_of_supply,
            "incoterm": po.incoterm,
            "project": po.project,
            "registrationType": po.custom_registration_type,
            "syncStatus": po.custom_sync_status,
            "paymentMethod": po.custom_payment_method,
            "transactionProgress": po.custom_transaction_progress,
            "destnCountryCd": po.custom_destncountrycd,
            "lpoNumber": po.custom_lpo_number,
            "costCenter": po.cost_center,
            "addresses": {
                "supplierAddress": supplier_addr,
                "dispatchAddress": dispatch_addr,
                "shippingAddress": shipping_addr
            },
            "terms": get_purchase_terms(),
            "items": items,
            "tax": taxes,
            "summary": summary,
            "metadata": {
                "createdBy": po.owner or "",
                "remarks": po.remarks or "",
                "createdAt": (po.creation.isoformat() + "Z") if po.creation else "",
                "updatedAt": (po.modified.isoformat() + "Z") if po.modified else ""
            }
        }

        return send_response(
            status="success",
            message="Purchase Invoice retrieved successfully",
            data=response_data,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Get Purchase Invoice By ID API Error")
        return send_response(
            status="fail",
            message="Failed to fetch purchase Invoice",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )


# ─────────────────────────────────────────────────────────────────────────────
#  DELETE PURCHASE INVOICE
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_purchase_invoice():
    try:
        args = frappe.request.args
        pInvoice = args.get("id")

        if not pInvoice:
            return send_response(
                status="fail",
                message="'id' parameter is required.",
                data=None,
                status_code=400,
                http_status=400
            )

        if not frappe.db.exists("Purchase Invoice", pInvoice):
            return send_response(
                status="fail",
                message=f"Purchase Invoice '{pInvoice}' not found.",
                data=None,
                status_code=404,
                http_status=404
            )

        po_doc = frappe.get_doc("Purchase Invoice", pInvoice)
        if po_doc.docstatus == 1:
            return send_response(
                status="fail",
                message="Cannot delete a submitted Purchase Invoice. Cancel it first.",
                data=None,
                status_code=400,
                http_status=400
            )

        frappe.db.delete("Sale Invoice Selling Terms", {"invoiceno": pInvoice})
        frappe.db.delete("Sale Invoice Selling Payment", {"invoiceno": pInvoice})
        frappe.db.delete("Sale Invoice Selling Payment Phases", {"invoiceno": pInvoice})

        po_doc.delete(ignore_permissions=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Purchase Invoice '{pInvoice}' deleted successfully",
            data={},
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(message=str(e), title="Delete Purchase Invoice API Error")
        return send_response(
            status="fail",
            message="Failed to delete purchase invoice",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )


# ─────────────────────────────────────────────────────────────────────────────
#  GET AUTOMATIC PURCHASE INVOICE
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False, methods=["PUT"])
def get_automatic_purchase_invoice():
    data = frappe.form_dict

    spplrTpin = data.get("spplrTpin")
    spplrNm = data.get("spplrNm")
    rcptTyCd = data.get("rcptTyCd")
    pmtTyCd = data.get("pmtTyCd")
    remark = data.get("remark")
    spplrInvcNo = data.get("spplrInvcNo")
    totTaxblAmt = data.get("totTaxblAmt")
    totTaxAmt = data.get("totTaxAmt")
    items = data.get("itemList", [])

    supplier_name = spplrNm

    if not frappe.db.exists("Supplier", supplier_name):
        newSupplierId = CUSTOM_FRAPPE_INSTANCE.GetNextCustomSupplierId()

        supplier_doc = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": spplrNm,
            "default_currency": frappe.defaults.get_global_default("currency"),
            "custom_supplier_id": newSupplierId,
            "tax_category": "Non-Export",
            "country": frappe.defaults.get_global_default("country"),
            "tax_id": spplrTpin,
            "custom_status": "Active"
        })
        supplier_doc.insert(ignore_permissions=True)
        supplier_name = supplier_doc.name

    purchase_invoice = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "supplier": supplier_name,
        "currency": frappe.defaults.get_global_default("currency"),
        "tax_category": "Non-Export",
        "custom_total_taxble_amount": totTaxblAmt,
        "custom_total_tax_amount": totTaxAmt,
        "remarks": remark,
        "bill_no": spplrInvcNo,
        "custom_sync_status": "0",
        "custom_place_of_supply": frappe.defaults.get_global_default("country"),
        "custom_registration_type": "Automatic",
        "custom_payment_method": "CASH",
    })

    for row in items:
        itemCd = row.get("itemCd")
        itemClsCd = row.get("itemClsCd")
        itemNm = row.get("itemNm")
        pkgUnitCd = row.get("pkgUnitCd")
        qtyUnitCd = row.get("qtyUnitCd")
        qty = row.get("qty")
        prc = row.get("prc")
        vatCatCd = row.get("vatCatCd")
        pkg = row.get("pkg")

        if not frappe.db.exists("Item", itemCd):
            item_doc = frappe.get_doc({
                "doctype": "Item",
                "item_name": itemNm,
                "item_code": itemCd,
                "item_group": "All Item Groups",
                "stock_uom": qtyUnitCd,
                "custom_itemclscd": itemClsCd,
                "custom_itemtycd": "1",
                "custom_orgnnatcd": "ZM",
                "custom_pkgunitcd": pkgUnitCd,
                "standard_rate": prc,
                "custom_purchase_amount": prc,
                "custom_buying_price": prc,
                "custom_kg": pkg,
                "custom_vendor": supplier_name,
                "custom_tax_type": "Non-Export",
                "custom_tax_code": "A",
                "custom_tax_name": "Standard Rated 16%",
                "custom_tax_description": "Category applies to products and services which attract VAT at 16 % by nature",
                "custom_tax_perct": "16",
                "custom_sales_account": "0000000000000",
                "custom_purchase_account": "0000000000",
                "custom_tax_preference": "Taxable",
                "custom_tax_category": "Non-Export",
            })
            item_doc.insert(ignore_permissions=True)

        purchase_invoice.append("items", {
            "item_code": itemCd,
            "item_name": itemNm,
            "qty": qty,
            "rate": prc,
            "custom_vat": vatCatCd,
            "uom": qtyUnitCd,
        })

    purchase_invoice.insert(ignore_permissions=True)
    frappe.db.commit()

    return send_response(
        status="success",
        message="Purchase Invoice received successfully.",
        status_code=200,
        http_status=200,
        data={}
    )


# ─────────────────────────────────────────────────────────────────────────────
#  UPDATE PURCHASE INVOICE STATUS
#  - If status is "Paid" or "Approved" and PI is Draft → submit with stock
#  - All other statuses → raw SQL update only
# ─────────────────────────────────────────────────────────────────────────────

# @frappe.whitelist(allow_guest=False, methods=["PATCH"])
# def update_purchase_invoices_status():
#     data = frappe.form_dict
#     pId = data.get("id")         # ✅ "id" from payload = "name" in Frappe
#     new_status = data.get("status")

#     STATUSES = CUSTOM_FRAPPE_INSTANCE.PurchaseInvoiceStatuses()

#     # ── Basic validations ─────────────────────────────────────────────────────
#     if not pId:
#         return send_response(status="fail", message="'id' parameter is required.", data=None, status_code=400, http_status=400)

#     if not new_status:
#         return send_response(status="fail", message="'status' parameter is required.", data=None, status_code=400, http_status=400)

#     if new_status not in STATUSES:
#         return send_response(
#             status="fail",
#             message=f"Invalid status '{new_status}'. Allowed statuses are: {', '.join(STATUSES)}.",
#             status_code=400,
#             http_status=400,
#         )

#     if not frappe.db.exists("Purchase Invoice", pId):
#         return send_response(status="fail", message=f"Purchase Invoice '{pId}' not found.", data=None, status_code=404, http_status=404)

#     # ── Fetch document ────────────────────────────────────────────────────────
#     pi_doc = frappe.get_doc("Purchase Invoice", pId)

#     # ── Status triggers that require stock movement ───────────────────────────
#     # status  = your custom field ("Paid", "Approved", "Draft" etc.)
#     # docstatus = Frappe internal (0=Draft, 1=Submitted, 2=Cancelled)
#     STOCK_TRIGGER_STATUSES = ["Approved", "Paid"]

#     if new_status in STOCK_TRIGGER_STATUSES:

#         if pi_doc.docstatus == 0:
#             # ── Document is Draft → validate batches, submit, hit stock ──────

#             # ✅ Validate all batch items before submitting
#             for item in pi_doc.items:
#                 item_has_batch = frappe.db.get_value("Item", item.item_code, "has_batch_no")

#                 if item_has_batch and not item.batch_no:
#                     return send_response(
#                         status="fail",
#                         message=f"Item '{item.item_code}' requires a batch number before approval.",
#                         status_code=400,
#                         http_status=400
#                     )

#                 if item.batch_no and not frappe.db.exists("Batch", {"name": item.batch_no, "item": item.item_code}):
#                     return send_response(
#                         status="fail",
#                         message=f"Batch '{item.batch_no}' no longer exists for item '{item.item_code}'.",
#                         status_code=400,
#                         http_status=400
#                     )

#             try:
#                 # ✅ Step 1: Force update_stock=1 directly in DB — bypasses cache
#                 frappe.db.set_value(
#                     "Purchase Invoice",
#                     pId,
#                     "update_stock",
#                     1,
#                     update_modified=False
#                 )
#                 frappe.db.commit()

#                 # ✅ Step 2: Fresh reload from DB — picks up update_stock=1
#                 pi_doc = frappe.get_doc("Purchase Invoice", pId)

#                 frappe.logger().info(
#                     f"[PI STATUS] '{pId}' docstatus=0 → submitting with update_stock=1."
#                 )

#                 # ✅ Step 3: Submit — Stock Ledger Entry created, batch balance updated
#                 pi_doc.submit()

#                 # ✅ Step 4: Force status="Paid" — ERPNext auto-sets "Unpaid" on submit
#                 frappe.db.sql("""
#                     UPDATE `tabPurchase Invoice`
#                     SET status = %s,
#                         modified = NOW(),
#                         modified_by = %s
#                     WHERE name = %s
#                 """, (new_status, frappe.session.user, pId))

#                 frappe.db.commit()

#                 frappe.logger().info(
#                     f"[PI STATUS] '{pId}' submitted. status='{new_status}'. Inventory updated."
#                 )

#             except Exception as e:
#                 frappe.db.rollback()
#                 frappe.log_error(frappe.get_traceback(), "Update Purchase Invoice Status - Stock Error")
#                 return send_response(
#                     status="fail",
#                     message=f"Failed to update stock for invoice '{pId}': {str(e)}",
#                     status_code=500,
#                     http_status=500
#                 )

#         elif pi_doc.docstatus == 1:
#             # ── Document already Submitted → just update status field via SQL ─
#             frappe.logger().info(
#                 f"[PI STATUS] '{pId}' docstatus=1 (already submitted) → updating status='{new_status}' only."
#             )

#             frappe.db.sql("""
#                 UPDATE `tabPurchase Invoice`
#                 SET status = %s,
#                     modified = NOW(),
#                     modified_by = %s
#                 WHERE name = %s
#             """, (new_status, frappe.session.user, pId))

#             frappe.db.commit()

#         else:
#             # ── docstatus=2 → Cancelled, cannot update ───────────────────────
#             return send_response(
#                 status="fail",
#                 message=f"Purchase Invoice '{pId}' is cancelled and cannot be updated.",
#                 status_code=400,
#                 http_status=400
#             )

#     else:
#         # ✅ Non-stock-triggering status — raw SQL update only (as before)
#         frappe.db.sql("""
#             UPDATE `tabPurchase Invoice`
#             SET status = %s,
#                 modified = NOW(),
#                 modified_by = %s
#             WHERE name = %s
#         """, (new_status, frappe.session.user, pId))

#         frappe.db.commit()

#     return send_response(status="success", message="The purchase invoice status was updated successfully.", data=[], status_code=200, http_status=200)



# ─────────────────────────────────────────────────────────────────────────────
#  UPDATE PURCHASE INVOICE STATUS
#  - If status is "Paid" or "Approved" and PI is Draft → submit with stock
#  - All other statuses → raw SQL update only
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False, methods=["PATCH"])
def update_purchase_invoices_status():
    data = frappe.form_dict
    pId = data.get("id")         # ✅ "id" from payload = "name" in Frappe
    new_status = data.get("status")

    STATUSES = CUSTOM_FRAPPE_INSTANCE.PurchaseInvoiceStatuses()

    # ── Basic validations ─────────────────────────────────────────────────────
    if not pId:
        return send_response(status="fail", message="'id' parameter is required.", data=None, status_code=400, http_status=400)

    if not new_status:
        return send_response(status="fail", message="'status' parameter is required.", data=None, status_code=400, http_status=400)

    if new_status not in STATUSES:
        return send_response(
            status="fail",
            message=f"Invalid status '{new_status}'. Allowed statuses are: {', '.join(STATUSES)}.",
            status_code=400,
            http_status=400,
        )

    if not frappe.db.exists("Purchase Invoice", pId):
        return send_response(status="fail", message=f"Purchase Invoice '{pId}' not found.", data=None, status_code=404, http_status=404)

    # ── Fetch document ────────────────────────────────────────────────────────
    pi_doc = frappe.get_doc("Purchase Invoice", pId)

    # ── Status triggers that require stock movement ───────────────────────────
    # status  = your custom field ("Paid", "Approved", "Draft" etc.)
    # docstatus = Frappe internal (0=Draft, 1=Submitted, 2=Cancelled)
    STOCK_TRIGGER_STATUSES = ["Approved", "Paid"]

    if new_status in STOCK_TRIGGER_STATUSES:

        if pi_doc.docstatus == 0:
            # ── Document is Draft → submit with stock ────────────────────────
            # ✅ Batch was already validated and created during create_purchase_invoice
            # ✅ Only validate batch if item has batch_no assigned on PI item
            for item in pi_doc.items:
                if item.batch_no:
                    if not frappe.db.exists("Batch", {"name": item.batch_no, "item": item.item_code}):
                        return send_response(
                            status="fail",
                            message=f"Batch '{item.batch_no}' no longer exists for item '{item.item_code}'.",
                            status_code=400,
                            http_status=400
                        )

            try:
                # ✅ Step 1: Force update_stock=1 directly in DB — bypasses cache
                frappe.db.set_value(
                    "Purchase Invoice",
                    pId,
                    "update_stock",
                    1,
                    update_modified=False
                )
                frappe.db.commit()

                # ✅ Step 2: Fresh reload from DB — picks up update_stock=1
                pi_doc = frappe.get_doc("Purchase Invoice", pId)

                frappe.logger().info(
                    f"[PI STATUS] '{pId}' docstatus=0 → submitting with update_stock=1."
                )

                # ✅ Step 3: Submit — Stock Ledger Entry created, batch balance updated
                pi_doc.submit()

                # ✅ Step 4: Force status="Paid" — ERPNext auto-sets "Unpaid" on submit
                frappe.db.sql("""
                    UPDATE `tabPurchase Invoice`
                    SET status = %s,
                        modified = NOW(),
                        modified_by = %s
                    WHERE name = %s
                """, (new_status, frappe.session.user, pId))

                frappe.db.commit()

                frappe.logger().info(
                    f"[PI STATUS] '{pId}' submitted. status='{new_status}'. Inventory updated."
                )

            except Exception as e:
                frappe.db.rollback()
                frappe.log_error(frappe.get_traceback(), "Update Purchase Invoice Status - Stock Error")
                return send_response(
                    status="fail",
                    message=f"Failed to update stock for invoice '{pId}': {str(e)}",
                    status_code=500,
                    http_status=500
                )

        elif pi_doc.docstatus == 1:
            # ── Document already Submitted → just update status field via SQL ─
            frappe.logger().info(
                f"[PI STATUS] '{pId}' docstatus=1 (already submitted) → updating status='{new_status}' only."
            )

            frappe.db.sql("""
                UPDATE `tabPurchase Invoice`
                SET status = %s,
                    modified = NOW(),
                    modified_by = %s
                WHERE name = %s
            """, (new_status, frappe.session.user, pId))

            frappe.db.commit()

        else:
            # ── docstatus=2 → Cancelled, cannot update ───────────────────────
            return send_response(
                status="fail",
                message=f"Purchase Invoice '{pId}' is cancelled and cannot be updated.",
                status_code=400,
                http_status=400
            )

    else:
        # ✅ Non-stock-triggering status — raw SQL update only (as before)
        frappe.db.sql("""
            UPDATE `tabPurchase Invoice`
            SET status = %s,
                modified = NOW(),
                modified_by = %s
            WHERE name = %s
        """, (new_status, frappe.session.user, pId))

        frappe.db.commit()

    return send_response(status="success", message="The purchase invoice status was updated successfully.", data=[], status_code=200, http_status=200)


# ─────────────────────────────────────────────────────────────────────────────
#  SYNC AUTO PURCHASE INVOICES
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False, methods=["PATCH"])
def sync_auto_purchase_invoices():
    data = frappe.form_dict
    pId = data.get("id")
    pchsSttsCd = data.get("transactionProgress")

    if not pId:
        return send_response(
            status="fail",
            message="Purchase id must not be null",
            data=[],
            http_status=400,
            status_code=400
        )

    trx_names = CUSTOM_FRAPPE_INSTANCE.GetTransactionProgressNames()
    trx_codes = CUSTOM_FRAPPE_INSTANCE.GetTransactionProgressCodes()

    if pchsSttsCd not in trx_names:
        return send_response(
            status="fail",
            message=f"Invalid transaction progress: {pchsSttsCd}. Available : {trx_names}",
            status_code=400,
            http_status=400
        )

    index = trx_names.index(pchsSttsCd)
    trxProgCd = trx_codes[index]

    p = frappe.db.get_value(
        "Purchase Invoice",
        pId,
        [
            "name", "supplier", "posting_date", "due_date", "grand_total",
            "status", "currency", "tax_category", "custom_place_of_supply",
            "remarks", "supplier_address", "dispatch_address", "shipping_address",
            "incoterm", "project", "cost_center", "custom_total_tax_amount",
            "custom_total_taxble_amount", "owner", "creation", "modified",
            "bill_no", "custom_registration_type", "custom_payment_method",
            "custom_transaction_progress", "custom_destncountrycd", "custom_lpo_number",
        ],
        as_dict=True
    )

    if not p:
        return send_response(
            status="fail",
            message=f"Purchase Invoice '{pId}' not found.",
            data=[],
            status_code=404,
            http_status=404
        )

    pmtType = p.custom_payment_method

    payment_names = CUSTOM_FRAPPE_INSTANCE.GetPaymentMethodsName()
    payment_codes = CUSTOM_FRAPPE_INSTANCE.GetPaymentMethodsCodes()

    index = payment_names.index(pmtType)
    pmtTyCd = payment_codes[index]

    supplier = frappe.db.get_value(
        "Supplier",
        p.get("supplier"),
        [
            "name", "supplier_name", "supplier_type", "tax_id",
            "mobile_no", "email_id", "supplier_group", "country"
        ],
        as_dict=True
    )

    if not supplier:
        return send_response(
            status="fail",
            message=f"Supplier '{p.get('supplier')}' not found.",
            data=[],
            status_code=404,
            http_status=404
        )

    items = frappe.get_all(
        "Purchase Invoice Item",
        filters={"parent": p.name},
        fields=[
            "item_code", "item_name", "qty", "rate", "amount",
            "description", "uom", "net_amount", "custom_vat",
        ]
    )

    if not items:
        return send_response(
            status="fail",
            message="No items found for this Purchase Invoice.",
            data=[],
            status_code=404,
            http_status=404
        )

    purchase_invoice_items = []

    for i in items:
        itemCode = i.item_code
        item_details = CUSTOM_FRAPPE_INSTANCE.GetItemInfo(itemCode)

        purchase_invoice_items.append({
            "itemCode": itemCode,
            "itemName": item_details.get("itemName"),
            "qty": i.qty,
            "itemClassCode": item_details.get("itemClassCd"),
            "packageUnitCode": item_details.get("itemPackingUnitCd"),
            "price": i.rate,
            "VatCd": i.custom_vat,
            "unitOfMeasure": item_details.get("itemUnitCd"),
        })

    # ------------------------------------------------------------------ #
    #  ZRA sync OR skip based on site config                               #
    # ------------------------------------------------------------------ #
    if is_zra_enabled():
        purchase_invoice_payload = {
            "supplierName": supplier.supplier_name,
            "supplierTpin": supplier.tax_id,
            "pmtTyCd": pmtTyCd,
            "pchsSttsCd": trxProgCd,
            "spplrInvcNo": p.bill_no,
            "items": purchase_invoice_items
        }

        print("Auto Purchase Payload: ", purchase_invoice_payload)
        results = AUTOMATIC_PURCHASE_HELPER.send_purchase_data(purchase_invoice_payload)
        print("Results: ", results)
        resultCd = results.get("resultCd")
        resultMsg = results.get("resultMsg")
        payload = results.get("payload")
        sync_status = 1
    else:
        # ✅ ZRA disabled — skip ZRA API call, mark as synced with empty payload
        frappe.logger().info(f"[PI] ZRA disabled — skipping sync for {pId}")
        payload = {}
        sync_status = 1

    frappe.db.set_value(
        "Purchase Invoice",
        pId,
        {
            "custom_sync_status": sync_status,
            "custom_transaction_progress": pchsSttsCd
        }
    )

    frappe.db.commit()

    return send_response(
        status="success",
        message="Purchase invoice synchronized successfully.",
        data=payload,
        status_code=200,
        http_status=200
    )