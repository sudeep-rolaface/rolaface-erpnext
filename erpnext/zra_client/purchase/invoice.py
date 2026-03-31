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
from custom_api.helper import get_tax_account

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

def get_or_create_batch(item_code, batch_no, company, expiry_date, manufacturing_date):
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
        "expiry_date":expiry_date,
        "manufacturing_date": manufacturing_date
    })
    new_batch.insert(ignore_permissions=True)
    frappe.db.commit()

    return new_batch.name


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: Link batch to PI + force-write batch_no on PI items
#
#  Called ONCE — after ALL saves (insert + save + createInvoiceTermsAndPayments)
#  so nothing can clear batch_no again after this point.
#
#  Two things happen per item:
#  1. Batch.reference_doctype / reference_name  → PI name
#     Lets status-update find the exact batch by PI name, not by item code.
#  2. frappe.db.set_value on PI Item row
#     Bypasses the ERPNext Document lifecycle that silently clears batch_no
#     when update_stock=0.
# ─────────────────────────────────────────────────────────────────────────────

def _persist_batch_nos(purchase_invoice, invoice_items_to_be_saved):
    for idx, item_data in enumerate(invoice_items_to_be_saved):
        if not item_data.get("batch_no"):
            continue

        pi_item_name = purchase_invoice.items[idx].name
        batch_no     = item_data["batch_no"]
        item_code    = item_data["item_code"]

        # ✅ Link batch → PI for reliable lookup at approval / status-update
        frappe.db.set_value(
            "Batch",
            batch_no,
            {
                "reference_doctype": "Purchase Invoice",
                "reference_name": purchase_invoice.name,
            },
        )

        # ✅ Force-write batch_no — bypasses ERPNext's clearing logic
        frappe.db.set_value(
            "Purchase Invoice Item",
            pi_item_name,
            "batch_no",
            batch_no,
            update_modified=False,
        )

        frappe.logger().info(
            f"[PI CREATE] batch='{batch_no}' linked to PI '{purchase_invoice.name}' "
            f"and force-written on item '{item_code}' (row '{pi_item_name}')"
        )

    frappe.db.commit()


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: Restore batch_no before submit
#
#  Uses the PI reference stored on the Batch doc — always returns the exact
#  batch the user originally sent.  Never guesses, never creates a random batch.
#
#  Also syncs the resolved value onto the in-memory doc object so ERPNext's
#  submit / validate cycle cannot clear it.
# ─────────────────────────────────────────────────────────────────────────────

def _restore_batch_nos_for_submit(pi_doc, pId):
    pi_items = frappe.get_all(
        "Purchase Invoice Item",
        filters={"parent": pId},
        fields=["name", "item_code", "batch_no"],
    )

    for pi_item in pi_items:
        item_has_batch = frappe.db.get_value("Item", pi_item["item_code"], "has_batch_no")
        if not item_has_batch:
            continue

        if pi_item.get("batch_no"):
            # Already in DB — just sync onto in-memory doc object
            resolved_batch = pi_item["batch_no"]
            frappe.logger().info(
                f"[PI BATCH] batch_no='{resolved_batch}' already in DB "
                f"for item '{pi_item['item_code']}' — no restore needed."
            )
        else:
            # batch_no was cleared — look up via PI reference on the Batch doc
            frappe.logger().warning(
                f"[PI BATCH] batch_no missing for item '{pi_item['item_code']}' "
                f"on PI '{pId}'. Looking up via PI reference on Batch doc."
            )

            resolved_batch = frappe.db.get_value(
                "Batch",
                {
                    "item": pi_item["item_code"],
                    "reference_doctype": "Purchase Invoice",
                    "reference_name": pId,
                    "disabled": 0,
                },
                "name",
            )

            if not resolved_batch:
                # Hard fail — never guess or silently create a random batch
                raise Exception(
                    f"Batch for item '{pi_item['item_code']}' on PI '{pId}' could not be "
                    f"found. The PI may have been created without a valid batchNo. "
                    f"Please re-create the purchase invoice with the correct batchNo."
                )

            # Write correct batch_no back to the DB row
            frappe.db.set_value(
                "Purchase Invoice Item",
                pi_item["name"],
                "batch_no",
                resolved_batch,
                update_modified=False,
            )
            frappe.logger().info(
                f"[PI BATCH] Restored batch_no='{resolved_batch}' via PI reference "
                f"for item '{pi_item['item_code']}' on PI '{pId}'"
            )

        # ✅ Always sync onto in-memory doc object — prevents submit/validate clearing it
        for doc_item in pi_doc.items:
            if doc_item.name == pi_item["name"]:
                doc_item.batch_no = resolved_batch
                break

    frappe.db.commit()

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
    updateStock = data.get("updateStock", True)
    set_warehouse = data.get("warehouse", None)

    supplier_invoice_date = data.get("spplrInvcDt", "")

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
        vat_rate = i.get("vatRate", 0)
        item_required_by = i.get("requiredBy")
        batch_no = i.get("batchNo")
        packing = i.get("packing")
        exp_date = i.get("expDate")
        mfg_date = i.get("mfgDate")
        warehouse = i.get("warehouse", None)
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

        # ── Batch Handling ────────────────────────────────────────────────────
        resolved_batch_no = None

        item_has_batch = frappe.db.get_value("Item", itemCode, "has_batch_no")


        if item_has_batch:
            if not batch_no:
                # ✅ Hard stop — batch is mandatory, user must always provide it
                return send_response(
                    status="fail",
                    message=f"Item '{itemCode}' requires a batch number (batchNo). It is mandatory.",
                    data=[],
                    status_code=400,
                    http_status=400
                )
            # ✅ Use EXACTLY the batch_no the user sent — create only if it doesn't exist yet
            resolved_batch_no = get_or_create_batch(itemCode, batch_no, company_name, exp_date, mfg_date)

        purchase_invoice_items.append({
            "itemCode": itemCode,
            "itemName": item_details.get("itemName"),
            "qty": quantity,
            "itemClassCode": item_details.get("itemClassCd"),
            "packageUnitCode": item_details.get("itemPackingUnitCd"),
            "price": rate,
            "custom_vat": vat_cd,
            "vat_rate": vat_rate,
            "unitOfMeasure": item_details.get("itemUnitCd"),
            "schedule_date": item_required_by,
            "warehouse": warehouse,
            "packing": packing,
            "exp_date": exp_date,
            "mfg_date": mfg_date
        })

        invoice_items_to_be_saved.append({
            "item_code": itemCode,
            "item_name": item_details.get("itemName"),
            "warehouse": warehouse,
            "custom_vat": vat_cd,
            "vat_rate": vat_rate,
            "qty": quantity,
            "rate": rate,
            "schedule_date": item_required_by,
            "batch_no": resolved_batch_no,  # ERPNext clears this when update_stock=0 on save —
            "packing": packing,              # _persist_batch_nos() force-writes it back after all saves
            "exp_date": exp_date,
            "mfg_date": mfg_date
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
        "items": invoice_items_to_be_saved,
        "remarks": remarks,
        "bill_no": spplrInvcNo,
        "update_stock": updateStock,              # ✅ stock moves only on approval
        "set_warehouse": set_warehouse,
        "supplier_address": supplier_addr_name,
        "dispatch_address": dispatch_addr_name,
        "shipping_address": shipping_addr_name,
        "custom_place_of_supply": placeOfSupply,
        "custom_registration_type": "Manual",
        "custom_payment_method": pmtType,
        "custom_transaction_progress": pchsSttsCd,
        "custom_destncountrycd": destnCountryCd,
        "custom_lpo_number": lpoNumber,
        "shipping_rule": shippingRule,
        "supplier_invoice_date": supplier_invoice_date,
        "taxes": [
                    {
                        "charge_type": "Actual",
                        "taxRate": 0,           # rate=0 because we use Actual amount
                        "account_head": get_tax_account(company_name, "Liability"),
                        "description": "Tax and Charges",
                        "tax_amount": total_tax_amount,
                        "cost_center": costCenter
                    }
                ] if total_tax_amount > 0 else []

    })

    purchase_invoice.insert(ignore_permissions=True)
    purchase_invoice.save(ignore_permissions=True)
    frappe.db.commit()

    # ✅ Terms first — may trigger internal saves that would clear batch_no again
    CUSTOM_FRAPPE_INSTANCE.createInvoiceTermsAndPayments(purchase_invoice.name, terms)

    # ✅ Persist batch_no LAST — after ALL saves, nothing can clear it after this.
    # Also links each Batch doc → this PI so status-update / approve can find the
    # exact batch by PI name instead of guessing by item code.
    _persist_batch_nos(purchase_invoice, invoice_items_to_be_saved)

    return send_response(
        status="success",
        message="Purchase invoice created sucessfully",
        status_code=201,
        http_status=201
    )


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

    # ✅ Verify batch still exists for every batch-tracked item
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

        # ✅ Step 2: Fresh reload — picks up update_stock=1
        pi = frappe.get_doc("Purchase Invoice", invoice_name)

        # ✅ Step 3: Restore batch_no on DB rows + in-memory doc using PI reference.
        # Uses the exact batch the user originally sent — no random creation.
        _restore_batch_nos_for_submit(pi, invoice_name)

        frappe.logger().info(
            f"[PI APPROVE] '{invoice_name}' update_stock={pi.update_stock} — submitting."
        )

        # ✅ Step 4: Submit — Stock Ledger Entry created, inventory updated
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
        search          = args.get("search")        # ← NEW
        minOutstanding= args.get("minOutstanding")
        maxOutstanding = args.get("maxOutstanding")

        filters = {}
        if status_filter:
            filters["status"] = status_filter
        if supplier_filter:
            filters["supplier"] = supplier_filter

        if minOutstanding and maxOutstanding:
            filters["outstanding_amount"] = ["between", [float(minOutstanding), float(maxOutstanding)]]
        elif minOutstanding:
            filters["outstanding_amount"] = [">=", float(minOutstanding)]
        elif maxOutstanding:
            filters["outstanding_amount"] = ["<=", float(maxOutstanding)]

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
                "shipping_rule",
                "outstanding_amount",
                "supplier_invoice_date",
                "total_taxes_and_charges"
            ],
            filters=filters,
            order_by="creation desc"
        )

        total_items = len(all_pos)

        # ── Search filter ─────────────────────────────────────────────────────
        if search:
            search_lower = search.lower()
            all_pos = [
                po for po in all_pos
                if search_lower in (po.get("name")             or "").lower()
                or search_lower in (po.get("supplier")         or "").lower()
                or search_lower in (po.get("status")           or "").lower()
                or search_lower in str(po.get("posting_date")  or "").lower()
                or search_lower in str(po.get("due_date")      or "").lower()
                or search_lower in str(po.get("grand_total")   or "").lower()
            ]

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
            base_total = po.pop("grand_total", 0)
            tax = po.pop("total_taxes_and_charges", 0) or 0
            po["grandTotal"] = base_total - tax
            outstanding = po.get("outstanding_amount") or 0
            po["paidAmount"] = (base_total or 0) - outstanding
            po["registrationType"] = po.pop("custom_registration_type")
            po["syncStatus"] = po.pop("custom_sync_status")
            po["shippingRule"] = po.pop("shipping_rule")
            po["grandTotalWithTax"] = base_total
            po["spplrInvcDt"] = po.pop("supplier_invoice_date")
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
                "shipping_rule",
                "supplier_invoice_date", "total_taxes_and_charges"
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
                "custom_vat as VatCd",
                "vat_rate as vatRate",
                "schedule_date as requiredBy",
                "packing",
                "mfg_date as mfgDate",
                "exp_date as expDate",
                "warehouse",
                "batch_no as batchNo",
                "warehouse"
            ]
        )

        total_quantity = sum(item.get("qty", 0) for item in items)
        sub_total = sum(item.get("amount", 0) for item in items)
        #grand_total = po.grand_total or 0
        grand_total = sub_total + float(po.total_taxes_and_charges or 0)
        rounded_total = po.get("rounded_total") or grand_total
        rounding_adjustment = rounded_total - grand_total

        summary = {
            "totalQuantity": total_quantity,
            "subTotal": sub_total,
            "taxTotal": po.total_taxes_and_charges or 0,
            "grandTotal": grand_total,
            "roundingAdjustment": rounding_adjustment,
            "roundedTotal": rounded_total
        }

        taxRate = "16%" if po.tax_category == "Non-Export" else "0%"

        taxes = {
            "type": po.tax_category,
            "taxRate": taxRate,
        }

        def get_purchase_terms():
            """Fetch buying terms from Company settings"""

            company_name = po.get("company")
            if not company_name:
                return {"terms": {"buying": {}}}

            custom_company_id = frappe.db.get_value(
                "Company",
                company_name,
                "custom_company_id"
            )

            if not custom_company_id:
                return {"terms": {"buying": {}}}

            buying_terms_doc = None
            if frappe.db.exists("Company Buying Terms", {"company": custom_company_id}):
                buying_terms_doc = frappe.get_doc("Company Buying Terms", {"company": custom_company_id})

            buying_payment_doc = None
            if frappe.db.exists("Company Buying Payments", {"company": custom_company_id}):
                buying_payment_doc = frappe.get_doc("Company Buying Payments", {"company": custom_company_id})

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
            "shippingRule": po.shipping_rule,
            "spplrInvcDt": po.supplier_invoice_date,
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


@frappe.whitelist(allow_guest=False, methods=["PATCH"])
def update_purchase_invoices_status():
    try:
        data = frappe.request.get_json()
        pId = data.get("id")
        new_status = data.get("status")

        if not pId:
            return send_response(status="fail", message="'id' is required.", data=None, status_code=400, http_status=400)

        if not new_status:
            return send_response(status="fail", message="'status' is required.", data=None, status_code=400, http_status=400)

        if not frappe.db.exists("Purchase Invoice", pId):
            return send_response(status="fail", message=f"Purchase Invoice '{pId}' not found.", data=None, status_code=404, http_status=404)

        pi_doc = frappe.get_doc("Purchase Invoice", pId)

        valid_statuses = CUSTOM_FRAPPE_INSTANCE.PurchaseInvoiceStatuses()

        if new_status not in valid_statuses:
            return send_response(
                status="fail",
                message=f"'status' must be one of: {', '.join(valid_statuses)}.",
                data=None,
                status_code=400,
                http_status=400
            )

        if new_status == "Submitted":
            if pi_doc.docstatus != 0:
                return send_response(status="fail", message="Only Draft invoices can be submitted.", data=None, status_code=400, http_status=400)
            pi_doc.submit()

        elif new_status == "Cancelled":
            if pi_doc.docstatus != 1:
                return send_response(status="fail", message="Only Submitted invoices can be cancelled.", data=None, status_code=400, http_status=400)
            pi_doc.cancel()

        else:
            frappe.db.sql("""
                    UPDATE `tabPurchase Invoice`
                    SET status = %s,
                        modified = NOW(),
                        modified_by = %s
                    WHERE name = %s
                """, (new_status, frappe.session.user, pId))

        frappe.db.commit()

        updated_status = frappe.db.get_value("Purchase Invoice", pId, "status")

        return send_response(
            status="success",
            message="Purchase Invoice status updated successfully.",
            data={"id": pId, "status": updated_status},
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Update Purchase Invoice Status Error")
        return send_response(
            status="fail",
            message=str(e),
            data=None,
            status_code=500,
            http_status=500
        )