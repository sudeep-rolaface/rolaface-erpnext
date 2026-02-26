from erpnext.zra_client.generic_api import send_response, send_response_list
from erpnext.zra_client.custom_frappe_client import CustomFrappeClient
from erpnext.zra_client.tax_calcalator.tax import TaxCaller
from erpnext.zra_client.main import ZRAClient
from frappe import _
import frappe
import random
import json
import re

ZRA_CLIENT_INSTANCE = ZRAClient()
CUSTOM_FRAPPE_INSTANCE = CustomFrappeClient()
TAX_CALLER_INSTANCE = TaxCaller()


def is_zra_enabled():
    """Return True only when ZRA sync is explicitly enabled in site config."""
    return bool(frappe.conf.get("enable_zra_sync", False))


def get_company_and_currency(cost_center=None):
    """
    Resolve company name and its default currency using raw SQL to bypass
    all Frappe/Redis caching layers.

    Priority:
      1. Derive from cost_center (most reliable - already in the PO payload)
      2. User-level default company
      3. Global Defaults table
      4. First company in the system
    """
    company = None

    # Strategy 1: derive from cost center - 100% accurate, no guessing
    if cost_center:
        result = frappe.db.sql(
            "SELECT company FROM `tabCost Center` WHERE name = %s LIMIT 1",
            (cost_center,)
        )
        if result:
            company = result[0][0]

    # Strategy 2: user-level default
    if not company:
        company = frappe.defaults.get_user_default("Company")

    # Strategy 3: Global Defaults table (raw SQL, no cache)
    if not company:
        result = frappe.db.sql(
            "SELECT defvalue FROM `tabDefaultValue` "
            "WHERE defkey = 'default_company' LIMIT 1"
        )
        company = result[0][0] if result else None

    # Strategy 4: first company in DB
    if not company:
        result = frappe.db.sql("SELECT name FROM `tabCompany` LIMIT 1")
        company = result[0][0] if result else None

    if not company:
        return None, None

    # Raw SQL - always reads live DB value, never Redis/Frappe cache
    result = frappe.db.sql(
        "SELECT default_currency FROM `tabCompany` WHERE name = %s LIMIT 1",
        (company,)
    )
    currency = result[0][0] if result else None
    return company, currency


def get_conversion_rate(from_currency, to_currency, transaction_date=None):
    """
    Fetch the exchange rate between two currencies.
    Priority:
      1. Same currency  -> 1.0 immediately
      2. Currency Exchange doctype (exact date match)
      3. Currency Exchange doctype (latest record)
      4. Frappe built-in get_exchange_rate utility
      5. Returns None - caller must handle
    """
    if from_currency == to_currency:
        return 1.0

    # 1. Exact date match
    if transaction_date:
        result = frappe.db.sql(
            "SELECT exchange_rate FROM `tabCurrency Exchange` "
            "WHERE from_currency = %s AND to_currency = %s AND date = %s LIMIT 1",
            (from_currency, to_currency, transaction_date)
        )
        if result:
            return float(result[0][0])

    # 2. Latest record regardless of date
    result = frappe.db.sql(
        "SELECT exchange_rate FROM `tabCurrency Exchange` "
        "WHERE from_currency = %s AND to_currency = %s "
        "ORDER BY date DESC LIMIT 1",
        (from_currency, to_currency)
    )
    if result:
        return float(result[0][0])

    # 3. Frappe built-in (may hit external API if configured)
    try:
        from erpnext.setup.utils import get_exchange_rate as erp_get_rate
        rate = erp_get_rate(from_currency, to_currency, transaction_date)
        if rate:
            return float(rate)
    except Exception:
        pass

    return None


@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_purchase_order():
    data = frappe.form_dict
    supplierId = data.get("supplierId")
    requiredBy = data.get("requiredBy")
    currency = data.get("currency")
    status = data.get("status")
    destnCountryCd = frappe.form_dict.get("destnCountryCd")
    lpoNumber = frappe.form_dict.get("lpoNumber")
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
            status_code=400,
        )

    supplier = frappe.db.get_value(
        "Supplier",
        {"custom_supplier_id": supplierId},
        "name",
    )

    if not supplier:
        return send_response(
            status="fail",
            message="Supplier not found",
            data=[],
            http_status=404,
            status_code=404,
        )

    # ------------------------------------------------------------------ #
    #  ZRA-specific: validate taxCategory only when ZRA sync is enabled    #
    # ------------------------------------------------------------------ #
    if is_zra_enabled():
        TAX_CAT = CUSTOM_FRAPPE_INSTANCE.GetAvailableTaxCategory()
        if taxCategory not in TAX_CAT:
            return send_response(
                status="fail",
                message=f"Tax Category '{taxCategory}' does not exist. Available Tax Categories: {TAX_CAT}",
                data=[],
                status_code=400,
                http_status=400,
            )

    if not costCenter:
        return send_response(
            status="fail",
            message="Cost center must not be null",
            data=[],
            status_code=400,
            http_status=400,
        )

    if not project:
        return send_response(
            status="fail",
            message="Project name must not be null",
            data=[],
            status_code=400,
            http_status=400,
        )

    # Check cost center exists directly in DB
    cost_center_exists = frappe.db.sql(
        "SELECT name FROM `tabCost Center` WHERE name = %s OR cost_center_name = %s LIMIT 1",
        (costCenter, costCenter)
    )
    if not cost_center_exists:
        return send_response(
            status="fail",
            message=f"Cost Center '{costCenter}' does not exist.",
            status_code=400,
            http_status=400,
            data=[],
        )

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
            status_code=400,
        )

    # ERPNext limits Incoterm 'code' field to 3 characters max
    incoterm_code = incoterm[:3].upper() if incoterm else incoterm
    incotermName = CUSTOM_FRAPPE_INSTANCE.GetOrCreateIncoterm(incoterm_code)

    # ------------------------------------------------------------------ #
    #  Resolve company + currency directly from the cost center            #
    #  (bypasses all Frappe/Redis caching via raw SQL)                     #
    #  MUST happen before projectName and any company-dependent logic      #
    # ------------------------------------------------------------------ #
    company_name, company_currency = get_company_and_currency(costCenter)

    # Log for easy debugging
    frappe.logger().info(
        f"[PO] costCenter='{costCenter}' -> company='{company_name}', "
        f"company_currency='{company_currency}', requested_currency='{currency}'"
    )

    if not company_currency:
        return send_response(
            status="fail",
            message=(
                f"Could not determine the default currency for the company linked to "
                f"cost center '{costCenter}'. Please ensure the company has a "
                f"Default Currency set in ERPNext (Setup -> Company)."
            ),
            data=[],
            status_code=400,
            http_status=400,
        )

    # Normalise: uppercase and strip, fall back to company currency if not provided
    company_currency = company_currency.strip().upper()
    if not currency:
        currency = company_currency
    else:
        currency = currency.strip().upper()

    # Explicit override from payload always takes priority
    explicit_rate = data.get("conversionRate") or data.get("conversion_rate")

    if explicit_rate:
        try:
            conversion_rate = float(explicit_rate)
            if conversion_rate <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return send_response(
                status="fail",
                message="'conversionRate' must be a positive number.",
                data=[],
                status_code=400,
                http_status=400,
            )
    elif currency == company_currency:
        # Same currency - no exchange record needed at all
        conversion_rate = 1.0
    else:
        # Different currency - try to resolve automatically
        conversion_rate = get_conversion_rate(currency, company_currency, requiredBy)
        if conversion_rate is None:
            return send_response(
                status="fail",
                message=(
                    f"Exchange rate not found for {currency} to {company_currency}. "
                    f"You can either:\n"
                    f"  (1) Add \"conversionRate\": <rate> to your request payload, OR\n"
                    f"  (2) Create a Currency Exchange record in ERPNext: "
                    f"Accounting -> Currency Exchange -> From {currency} To {company_currency}."
                ),
                data=[],
                status_code=400,
                http_status=400,
            )

    # ✅ company_name is now resolved — safe to create project under correct company
    projectName = ZRA_CLIENT_INSTANCE.GetOrCreateProject(project, company_name)

    invoice_items = []
    tax_items = []
    for i in items:
        print(i)
        itemCode = i.get("itemCode")
        quantity = i.get("quantity")
        vat_cd = i.get("vatCd")
        rate = i.get("rate")
        item_required_by = i.get("requiredBy")
        if not itemCode:
            return send_response(
                status="fail",
                message="Item code must not be null",
                data=[],
                status_code=400,
                http_status=400,
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
                http_status=400,
            )

        item_details = CUSTOM_FRAPPE_INSTANCE.GetItemDetails(itemCode)
        if not item_details:
            return send_response(
                status="fail",
                message=f"Item '{itemCode}' does not exist",
                status_code=404,
                http_status=404,
            )

        # ------------------------------------------------------------------ #
        #  ZRA-specific vatCd / taxCategory pairing — skipped when ZRA is OFF #
        # ------------------------------------------------------------------ #
        if is_zra_enabled():
            VAT_LIST = CUSTOM_FRAPPE_INSTANCE.GetValidTaxTypes()
            if vat_cd not in VAT_LIST:
                return send_response(
                    status="fail",
                    message=f"Invalid VAT code {vat_cd}",
                    status_code=400,
                )

            if taxCategory == "LPO" and vat_cd != "C2":
                return send_response(
                    status="fail",
                    message="vatCd must be 'C2' when taxCategory is 'LPO'",
                    status_code=400,
                    http_status=400,
                )

            if vat_cd == "C1" and not destnCountryCd:
                return send_response(
                    status="fail",
                    message="Destination country required for VAT C1",
                    status_code=400,
                )

            if taxCategory == "Export" and vat_cd != "C1":
                return send_response(
                    status="fail",
                    message="vatCd must be 'C1' when taxCategory is 'Export'",
                    status_code=400,
                    http_status=400,
                )

            if taxCategory == "Non-Export" and vat_cd != "A":
                return send_response(
                    status="fail",
                    message="vatCd must be 'A' when taxCategory is 'Non-Export'",
                    status_code=400,
                    http_status=400,
                )

            if vat_cd == "A":
                if lpoNumber is not None or destnCountryCd is not None:
                    return send_response(
                        status="fail",
                        message="LPO number and destination country must not be provided when VAT code is 'A'.",
                        status_code=400,
                    )

        tax_items.append({
            "itemCode": itemCode,
            "itemName": item_details.get("itemName"),
            "qty": quantity,
            "itemClassCode": item_details.get("itemClassCd"),
            "itemTypeCd": item_details.get("itemType"),
            "packageUnitCode": item_details.get("itemPackingUnitCd"),
            "price": rate,
            "VatCd": vat_cd,
            "unitOfMeasure": item_details.get("itemUnitCd"),
            "schedule_date": item_required_by
        })

        invoice_items.append({
            "item_code": itemCode,
            "item_name": item_details.get("itemName"),
            "warehouse": CUSTOM_FRAPPE_INSTANCE.GetDefaultWareHouse(company_name),
            "qty": quantity,
            "rate": rate if rate is not None else item_details.get("standardRate", 0),
            "expense_account": CUSTOM_FRAPPE_INSTANCE.getDefaultExpenseAccount(),
            "schedule_date": item_required_by

        })

    # ------------------------------------------------------------------ #
    #  ZRA tax API call — skipped when ZRA sync is disabled               #
    #  When disabled, compute totals from taxes[] payload or item vatRate #
    # ------------------------------------------------------------------ #
    if is_zra_enabled():
        sale_payload = {
            "name": 1,
            "customerName": "Tax",
            "customer_tpin": "Tax",
            "destnCountryCd": destnCountryCd,
            "lpoNumber": lpoNumber,
            "currencyCd": "ZMK",
            "exchangeRt": 1,
            "created_by": "admin",
            "items": tax_items,
        }
        tax_response = TAX_CALLER_INSTANCE.send_sale_data(sale_payload)
        print(tax_response)
    else:
        # Strategy 1: compute from explicit taxes[] array in payload
        total_taxable_amount = sum(float(t.get("taxableAmount") or 0) for t in taxes)
        total_tax_amount = sum(float(t.get("taxAmount") or 0) for t in taxes)

        # Strategy 2: if taxes[] was empty, derive from items[].vatRate
        if not taxes:
            total_taxable_amount = 0.0
            total_tax_amount = 0.0
            for i in items:
                item_rate = float(i.get("rate") or 0)
                item_qty = float(i.get("quantity") or 0)
                vat_rate_pct = float(i.get("vatRate") or 0)
                line_taxable = item_rate * item_qty
                line_tax = round(line_taxable * vat_rate_pct / 100, 2)
                total_taxable_amount += line_taxable
                total_tax_amount += line_tax

            # Build synthetic taxes[] so the PO append loop below works
            if total_tax_amount > 0:
                # Query a tax/valuation account scoped to the SAME company as the PO
                tax_account_result = frappe.db.sql(
                    """
                    SELECT name FROM `tabAccount`
                    WHERE company = %s
                      AND account_type IN ('Tax', 'Expenses Included In Valuation')
                      AND is_group = 0
                    ORDER BY account_type DESC
                    LIMIT 1
                    """,
                    (company_name,)
                )
                if not tax_account_result:
                    # Fallback: any expense account for this company
                    tax_account_result = frappe.db.sql(
                        """
                        SELECT name FROM `tabAccount`
                        WHERE company = %s
                          AND root_type = 'Expense'
                          AND is_group = 0
                        LIMIT 1
                        """,
                        (company_name,)
                    )

                tax_account_head = tax_account_result[0][0] if tax_account_result else None

                if not tax_account_head:
                    return send_response(
                        status="fail",
                        message=(
                            f"No suitable tax/valuation account found for company '{company_name}'. "
                            f"Please create an account with type 'Tax' or 'Expenses Included In Valuation' "
                            f"under company '{company_name}' in ERPNext Chart of Accounts."
                        ),
                        data=[],
                        status_code=400,
                        http_status=400,
                    )

                taxes = [{
                    "type": "Actual",
                    "accountHead": tax_account_head,
                    "taxRate": 0,           # rate=0 because we use Actual amount
                    "taxableAmount": total_taxable_amount,
                    "taxAmount": total_tax_amount,
                }]

        tax_response = {
            "totTaxblAmt": total_taxable_amount,
            "totTaxAmt": total_tax_amount,
        }

    supplier_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateSupplierAddress(addresses, supplier)
    dispatch_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateDispatchAddress(addresses, supplier)
    shipping_addr_name = CUSTOM_FRAPPE_INSTANCE.CreateShippingAddress(addresses, supplier)
    print(supplier_addr_name, dispatch_addr_name, shipping_addr_name)

    po_doc = frappe.get_doc({
        "doctype": "Purchase Order",
        "supplier": supplier,
        "company": company_name,          # ✅ correct company from cost center
        "currency": currency,
        "conversion_rate": conversion_rate,
        "cost_center": costCenter,
        "project": projectName,
        "schedule_date": requiredBy,
        "incoterm": incotermName,
        "status": status,
        "custom_placeofsupply": placeOfSupply,
        "custom_remarks": remarks,
        "tax_category": taxCategory,
        "custom_total_taxble_amount": tax_response.get("totTaxblAmt", 0),
        "custom_total_tax_amount": tax_response.get("totTaxAmt", 0),
        "items": invoice_items,
    })

    for t in taxes:
        tax_type = (t.get("type") or "").strip()
        account_head = (t.get("accountHead") or "").strip()
        rate = float(t.get("taxRate") or 0)
        taxable = float(t.get("taxableAmount") or 0)
        amount = float(t.get("taxAmount") or 0)

        # Only validate tax type and account head against ZRA-specific lists when ZRA is enabled.
        # When ZRA is off, the synthetic tax row already has a company-scoped account — skip validation.
        if is_zra_enabled():
            valid_tax_types = CUSTOM_FRAPPE_INSTANCE.GetTaxesChargesRate()
            VALID_ACCOUNTS_HEAD = CUSTOM_FRAPPE_INSTANCE.GetExpensesValuationAccount()

            if tax_type not in valid_tax_types:
                return send_response(
                    status="fail",
                    message=f"Invalid Tax Type: {tax_type}. Allowed: {', '.join(valid_tax_types)}",
                    status_code=400,
                    http_status=400,
                )

            if account_head not in VALID_ACCOUNTS_HEAD:
                return send_response(
                    status="fail",
                    message=f"Invalid Account Head: {account_head}. Allowed: {', '.join(VALID_ACCOUNTS_HEAD)}",
                    status_code=400,
                    http_status=400,
                )

        po_doc.append("taxes", {
            "charge_type": tax_type,
            "account_head": account_head,
            "rate": rate,
            "tax_amount": amount,
            "total": taxable,
            "description": tax_type,
        })

    po_doc.insert(ignore_permissions=True)
    po_doc.save(ignore_permissions=True)

    frappe.db.sql(
        """
        UPDATE `tabPurchase Order`
        SET supplier_address = %s,
            dispatch_address = %s,
            shipping_address = %s
        WHERE name = %s
        """,
        (supplier_addr_name, dispatch_addr_name, shipping_addr_name, po_doc.name),
    )

    frappe.db.commit()

    CUSTOM_FRAPPE_INSTANCE.createInvoiceTermsAndPayments(po_doc.name, terms)

    return send_response(
        status="success",
        message="Purchase order created successfully",
        data={"poId": po_doc.name},
        status_code=201,
        http_status=201,
    )


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_purchase_orders():
    try:
        args = frappe.request.args
        page = args.get("page")
        if not page:
            return send_response(
                status="error",
                message="'page' parameter is required.",
                data=None,
                status_code=400,
                http_status=400,
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
                http_status=400,
            )

        page_size = args.get("page_size")
        if not page_size:
            return send_response(
                status="error",
                message="'page_size' parameter is required.",
                data=None,
                status_code=400,
                http_status=400,
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
                http_status=400,
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
            "Purchase Order",
            fields=["name", "supplier", "transaction_date", "schedule_date", "grand_total", "status"],
            filters=filters,
            order_by="creation desc",
        )

        total_items = len(all_pos)

        if total_items == 0:
            return send_response(
                status="success",
                message="No purchase orders found.",
                data=[],
                status_code=200,
                http_status=200,
            )

        pos = all_pos[start:end]

        for po in pos:
            po["poId"] = po.pop("name")
            po["supplierName"] = po.pop("supplier")
            po["poDate"] = str(po.pop("transaction_date")) if po.get("transaction_date") else None
            po["deliveryDate"] = str(po.pop("schedule_date")) if po.get("schedule_date") else None
            po["grandTotal"] = po.pop("grand_total")

        total_pages = (total_items + page_size - 1) // page_size

        response_data = {
            "success": True,
            "message": "Purchase orders retrieved successfully",
            "data": pos,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

        return send_response_list(
            status="success",
            message="Purchase orders retrieved successfully",
            status_code=200,
            data=response_data,
            http_status=200,
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Get Purchase Orders API Error")
        return send_response(
            status="fail",
            message="Failed to fetch purchase orders",
            data={"error": str(e)},
            status_code=500,
            http_status=500,
        )


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_purchase_order():
    try:
        args = frappe.request.args
        poId = args.get("id")

        if not poId:
            return send_response(
                status="fail",
                message="'id' parameter is required.",
                data=[],
                status_code=400,
                http_status=400,
            )

        po = frappe.db.get_value(
            "Purchase Order",
            poId,
            [
                "name", "supplier", "transaction_date", "schedule_date",
                "grand_total", "status", "currency", "conversion_rate",
                "tax_category", "custom_placeofsupply", "custom_remarks",
                "supplier_address", "dispatch_address", "shipping_address",
                "incoterm", "project", "cost_center",
                "custom_total_tax_amount", "custom_total_taxble_amount",
                "owner", "creation", "modified",
            ],
            as_dict=True,
        )

        if not po:
            return send_response(
                status="fail",
                message=f"Purchase Order '{poId}' not found.",
                data=[],
                status_code=404,
                http_status=404,
            )

        items = frappe.get_all(
            "Purchase Order Item",
            filters={"parent": poId},
            fields=["item_code", "item_name", "qty", "uom", "rate", "amount"],
        )

        total_quantity = sum(item.get("qty", 0) for item in items)
        sub_total = sum(item.get("amount", 0) for item in items)
        grand_total = po.grand_total or 0
        rounded_total = po.rounded_total or grand_total
        rounding_adjustment = rounded_total - grand_total

        summary = {
            "totalQuantity": total_quantity,
            "subTotal": sub_total,
            "taxTotal": po.custom_total_tax_amount,
            "grandTotal": grand_total,
            "roundingAdjustment": rounding_adjustment,
            "roundedTotal": rounded_total,
        }

        taxRate = "16%" if po.tax_category == "Non-Export" else "0%"
        # If tax amount exists but taxRate would show 0%, compute real effective rate
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
            "taxAmount": po.custom_total_tax_amount,
        }

        terms_doc = (
            frappe.get_doc("Sale Invoice Selling Terms", {"invoiceno": po.name})
            if frappe.db.exists("Sale Invoice Selling Terms", {"invoiceno": po.name})
            else None
        )

        payment_doc = (
            frappe.get_doc("Sale Invoice Selling Payment", {"invoiceno": po.name})
            if frappe.db.exists("Sale Invoice Selling Payment", {"invoiceno": po.name})
            else None
        )

        phases = frappe.get_all(
            "Sale Invoice Selling Payment Phases",
            filters={"invoiceno": po.name},
            fields=["phase_name as name", "percentage", "condition"],
        )

        def purchase_terms():
            return {
                "terms": {
                    "selling": {
                        "general": getattr(terms_doc, "general", ""),
                        "delivery": getattr(terms_doc, "delivery", ""),
                        "cancellation": getattr(terms_doc, "cancellation", ""),
                        "warranty": getattr(terms_doc, "warranty", ""),
                        "liability": getattr(terms_doc, "liability", ""),
                        "payment": {
                            "dueDates": getattr(payment_doc, "duedates", ""),
                            "lateCharges": getattr(payment_doc, "latecharges", ""),
                            "taxes": getattr(payment_doc, "taxes", ""),
                            "notes": getattr(payment_doc, "notes", ""),
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

            result = {
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
                result["phone"] = addr.phone
                result["email"] = addr.email_id

            return result

        supplier_addr = get_address_details(po.supplier_address, include_contact=True)
        dispatch_addr = get_address_details(po.dispatch_address, include_contact=False)
        shipping_addr = get_address_details(po.shipping_address, include_contact=False)

        response_data = {
            "poId": po.name,
            "supplierName": po.supplier,
            "poDate": str(po.transaction_date) if po.transaction_date else None,
            "requiredBy": str(po.schedule_date) if po.schedule_date else None,
            "currency": po.currency,
            "conversionRate": po.conversion_rate,
            "status": po.status,
            "grandTotal": po.grand_total,
            "taxCategory": po.tax_category,
            "placeOfSupply": po.custom_placeofsupply,
            "incoterm": po.incoterm,
            "project": po.project,
            "costCenter": po.cost_center,
            "addresses": {
                "supplierAddress": supplier_addr,
                "dispatchAddress": dispatch_addr,
                "shippingAddress": shipping_addr,
            },
            "terms": purchase_terms(),
            "items": items,
            "tax": taxes,
            "summary": summary,
            "metadata": {
                "createdBy": po.owner or "",
                "remarks": po.custom_remarks or "",
                "createdAt": (po.creation.isoformat() + "Z") if po.creation else "",
                "updatedAt": (po.modified.isoformat() + "Z") if po.modified else "",
            },
        }

        return send_response(
            status="success",
            message="Purchase order retrieved successfully",
            data=response_data,
            status_code=200,
            http_status=200,
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Get Purchase Order By ID API Error")
        return send_response(
            status="fail",
            message="Failed to fetch purchase order",
            data={"error": str(e)},
            status_code=500,
            http_status=500,
        )


@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_purchase_order():
    try:
        args = frappe.request.args
        poId = args.get("id")

        if not poId:
            return send_response(
                status="fail",
                message="'id' parameter is required.",
                data=None,
                status_code=400,
                http_status=400,
            )

        if not frappe.db.exists("Purchase Order", poId):
            return send_response(
                status="fail",
                message=f"Purchase Order '{poId}' not found.",
                data=None,
                status_code=404,
                http_status=404,
            )

        po_doc = frappe.get_doc("Purchase Order", poId)
        if po_doc.docstatus == 1:
            return send_response(
                status="fail",
                message="Cannot delete a submitted Purchase Order. Cancel it first.",
                data=None,
                status_code=400,
                http_status=400,
            )

        frappe.db.delete("Sale Invoice Selling Terms", {"invoiceno": poId})
        frappe.db.delete("Sale Invoice Selling Payment", {"invoiceno": poId})
        frappe.db.delete("Sale Invoice Selling Payment Phases", {"invoiceno": poId})

        po_doc.delete(ignore_permissions=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Purchase Order '{poId}' deleted successfully",
            data={},
            status_code=200,
            http_status=200,
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(message=str(e), title="Delete Purchase Order API Error")
        return send_response(
            status="fail",
            message="Failed to delete purchase order",
            data={"error": str(e)},
            status_code=500,
            http_status=500,
        )


@frappe.whitelist(allow_guest=False, methods=["PATCH"])
def update_purchase_order_status():
    try:
        data = frappe.form_dict
        poId = data.get("id")
        new_status = data.get("status")

        if not poId:
            return send_response(
                status="fail",
                message="'id' parameter is required.",
                data=None,
                status_code=400,
                http_status=400,
            )

        if not new_status:
            return send_response(
                status="fail",
                message="'status' parameter is required.",
                data=None,
                status_code=400,
                http_status=400,
            )

        if not frappe.db.exists("Purchase Order", poId):
            return send_response(
                status="fail",
                message=f"Purchase Order '{poId}' not found.",
                data=None,
                status_code=404,
                http_status=404,
            )

        frappe.db.sql(
            """
            UPDATE `tabPurchase Order`
            SET status = %s,
                modified = NOW(),
                modified_by = %s
            WHERE name = %s
            """,
            (new_status, frappe.session.user, poId),
        )

        frappe.db.commit()

        return send_response(
            status="success",
            message="Purchase Order status updated successfully",
            data={"poId": poId, "status": new_status},
            status_code=200,
            http_status=200,
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(message=str(e), title="Update Purchase Order Status API Error")
        return send_response(
            status="fail",
            message="Failed to update purchase order status",
            data={"error": str(e)},
            status_code=500,
            http_status=500,
        )
