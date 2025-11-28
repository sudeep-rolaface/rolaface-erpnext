from erpnext.selling.doctype.quotation.quotation import Quotation
from erpnext.zra_client.generic_api import send_response
from erpnext.zra_client.main import ZRAClient
from frappe import _
import frappe
import re

def get_customer_details(customer_id):
    if not customer_id:
        return send_response(
            status="fail",
            message="Customer ID is required",
            status_code=400,
            http_status=400
        )

    try:
        customer = frappe.get_all("Customer", filters={"custom_id": customer_id}, limit=1)
        if not customer:
            return send_response(
                status="fail",
                message=f"Customer with ID '{customer_id}' not found",
                status_code=404,
                http_status=404
            )
        
        customer_doc = frappe.get_doc("Customer", customer[0]["name"])

        def safe_attr(obj, attr):
            return getattr(obj, attr, "") or ""

        data = {
            "custom_customer_tpin": safe_attr(customer_doc, "tax_id"),
            "name": safe_attr(customer_doc, "name"),
            "customer_name": safe_attr(customer_doc, "customer_name"),
        }
        return data
    
    except Exception as e:
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )
@frappe.whitelist(allow_guest=False)
def get_all_quotations():
    try:
        quotations = frappe.get_all("Quotation", 
                                    fields=[
                                        "name", 
                                        "customer_name",
                                        "custom_industry_bases",
                                        "transaction_date", 
                                        "valid_till",
                                        "grand_total",
                                        "currency"
                                        ])
        return send_response(
            status="success",
            message=_("Quotations fetched successfully"),
            data=quotations,
            status_code=200,
            http_status=200
        )
    
    except Exception as e:
        send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        ) 
        return  
    

@frappe.whitelist(allow_guest=False)
def get_quotation_details():
    data = frappe.local.form_dict
    quotation_id = data.get("quotation_id")
    if not quotation_id:
        return send_response(
            status="fail",
            message=_("Quotation ID is required"),
            status_code=400,
            http_status=400
        )

    try:
        try:
            quotation = frappe.get_doc("Quotation", quotation_id)
        except frappe.DoesNotExistError:
            return send_response(
                status="fail",
                message=f"Quotation  with id { quotation_id } not found",
                status_code=404,
                http_status=404
            )

        quotation_details = {
            "name": quotation.name,
            "customer_name": quotation.customer_name,
            "currency": quotation.currency,
            "custom_industry_bases": quotation.custom_industry_bases,
            "transaction_date": quotation.transaction_date,
            "valid_till": quotation.valid_till,
            "grand_total": quotation.grand_total,
            "custom_tc": quotation.custom_tc,
            "custom_swift": quotation.custom_swift,
            "custom_bank_name": quotation.custom_bank_name,
            "custom_payment_terms": quotation.custom_payment_terms,
            "custom_payment_method": quotation.custom_payment_method,
            "custom_account_number": quotation.custom_account_number,
            "custom_routing_number": quotation.custom_routing_number,
            "custom_billing_address_line_1": quotation.custom_billing_address_line_1,
            "custom_billing_address_line_2": quotation.custom_billing_address_line_2,
            "custom_billing_address_city": quotation.custom_billing_address_city,
            "custom_billing_address_postal_code" : quotation.custom_billing_address_postal_code,
            "items": [
                {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "quantity": item.qty,
                    "rate": item.rate,
                    "amount": item.amount
                } for item in quotation.items
            ]
        }

        return send_response(
            status="success",
            message=_("Quotation details fetched successfully"),
            data=quotation_details,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=False)
def delete_quotation():
    data = frappe.local.form_dict
    quotation_id = data.get("quotation_id")
    if not quotation_id:
        return send_response(
            status="fail",
            message=_("Quotation ID is required"),
            status_code=400,
            http_status=400
        )

    try:
        try:
            quotation = frappe.get_doc("Quotation", quotation_id)
        except frappe.DoesNotExistError:
            return send_response(
                status="fail",
                message=f"Quotation with id { quotation_id } not found",
                status_code=404,
                http_status=404
            )

        quotation.delete()
        frappe.db.commit()

        return send_response(
            status="success",
            message=_("Quotation deleted successfully"),
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )
        
@frappe.whitelist(allow_guest=False)
def create_quotation():
    data = frappe.local.form_dict

    customer_id = data.get("customer_id")
    company_id = data.get("company_id")
    currency = data.get("currency")
    valid_till = data.get("valid_till")
    transaction_date = data.get("transaction_date")
    custom_industry_bases = data.get("custom_industry_bases")
    custom_tc = data.get("custom_tc")
    custom_swift = data.get("custom_swift")
    custom_bank_name = data.get("custom_bank_name")
    custom_payment_terms = data.get("custom_payment_terms")
    custom_payment_method = data.get("custom_payment_method")
    custom_account_number = data.get("custom_account_number")
    custom_routing_number = data.get("custom_routing_number")
    custom_billing_address_line_1 = data.get("custom_billing_address_line_1")
    custom_billing_address_line_2 = data.get("custom_billing_address_line_2")
    custom_billing_address_city = data.get("custom_billing_address_city")
    custom_billing_address_postal_code = data.get("custom_billing_address_postal_code")


    items = data.get("items")
    
    next_name = Quotation.get_next_quotation_name()
    
    
    
    if not custom_industry_bases:
        return send_response(
            status="fail",
            message=_("Industry Base is required"),
            status_code=400,
            http_status=400
        )
    
    VALID_INDUSTRY_BASES = ["Service", "Product", "Manufacturing"]
    if custom_industry_bases not in VALID_INDUSTRY_BASES:
        return send_response(
            status="fail",
            message=_("Invalid Industry Base. Must be one of: {}").format(", ".join(VALID_INDUSTRY_BASES)),
            status_code=400,
            http_status=400
        )
    if not valid_till:
        return send_response(
            status="fail",
            message=_("Valid Till date is required"),
            status_code=400,
            http_status=400
        )
        
    if valid_till and not re.match(r"^\d{4}-\d{2}-\d{2}$", valid_till):
        return send_response(
            status="fail",
            message=_("Valid Till date must be in YYYY-MM-DD format"),
            status_code=400,
            http_status=400
        )
        
    
    if valid_till and transaction_date and valid_till < transaction_date:
        return send_response(
            status="fail",
            message=_("Valid Till date cannot be earlier than Transaction Date"),
            status_code=400,
            http_status=400
        )
    if not currency:
        return send_response(
            status="fail",
            message=_("Currency is required"),
            status_code=400,
            http_status=400
        )

    if not customer_id:
        return send_response(
            status="fail",
            message=_("Customer is required"),
            status_code=400,
            http_status=400
        )

    customer_data = get_customer_details(customer_id)
    if not customer_data or customer_data.get("status") == "fail":
        return customer_data

    customer_name = customer_data.get("customer_name")

    if not company_id:
        return send_response(
            status="fail",
            message=_("Company is required"),
            status_code=400,
            http_status=400
        )

    company_check = frappe.get_all("Company", filters={"custom_company_id": company_id}, limit=1)
    if not company_check:
        return send_response(
            status="fail",
            message=_("Company with ID '{}' does not exist").format(company_id),
            status_code=404,
            http_status=404
        )

    company_name = company_check[0]["name"]

    custom_tc = data.get("custom_tc")
    if not custom_tc:
        return send_response(
            status="fail",
            message="Missing required field: custom_tc",
            status_code=400
        )

    custom_swift = data.get("custom_swift")
    if not custom_swift:
        return send_response(
            status="fail",
            message="Missing required field: custom_swift",
            status_code=400
        )

    custom_bank_name = data.get("custom_bank_name")
    if not custom_bank_name:
        return send_response(
            status="fail",
            message="Missing required field: custom_bank_name",
            status_code=400
        )

    custom_payment_terms = data.get("custom_payment_terms")
    if not custom_payment_terms:
        return send_response(
            status="fail",
            message="Missing required field: custom_payment_terms",
            status_code=400
        )

    custom_payment_method = data.get("custom_payment_method")
    if not custom_payment_method:
        return send_response(
            status="fail",
            message="Missing required field: custom_payment_method",
            status_code=400
        )

    custom_account_number = data.get("custom_account_number")
    if not custom_account_number:
        return send_response(
            status="fail",
            message="Missing required field: custom_account_number",
            status_code=400
        )

    custom_routing_number = data.get("custom_routing_number")
    if not custom_routing_number:
        return send_response(
            status="fail",
            message="Missing required field: custom_routing_number",
            status_code=400
        )

    custom_billing_address_line_1 = data.get("custom_billing_address_line_1")
    if not custom_billing_address_line_1:
        return send_response(
            status="fail",
            message="Missing required field: custom_billing_address_line_1",
            status_code=400
        )

    # Optional field
    custom_billing_address_line_2 = data.get("custom_billing_address_line_2")

    custom_billing_address_city = data.get("custom_billing_address_city")
    if not custom_billing_address_city:
        return send_response(
            status="fail",
            message="Missing required field: custom_billing_address_city",
            status_code=400
        )

    custom_billing_address_postal_code = data.get("custom_billing_address_postal_code")
    if not custom_billing_address_postal_code:
        return send_response(
            status="fail",
            message="Missing required field: custom_billing_address_postal_code",
            status_code=400
        )


    if not items:
        return send_response(
            status="fail",
            message=_("Items are required"),
            status_code=400,
            http_status=400
        )

    if isinstance(items, str):
        try:
            items = frappe.parse_json(items)
        except:
            return send_response(
                status="fail",
                message=_("Items format is invalid"),
                status_code=400,
                http_status=400
            )

    if not isinstance(items, list) or len(items) == 0:
        return send_response(
            status="fail",
            message=_("Items must be a non-empty list"),
            status_code=400,
            http_status=400
        )

    for i, item in enumerate(items):
        item_code = item.get("item_code")
        qty = item.get("qty")
        rate = item.get("rate")

        if not item_code:
            return send_response(
                status="fail",
                message=_("Item #{} is missing item_code").format(i + 1),
                status_code=400,
                http_status=400
            )

        if not frappe.db.exists("Item", item_code):
            return send_response(
                status="fail",
                message=_("Item {} does not exist").format(item_code),
                status_code=400,
                http_status=400
            )

        if qty is None:
            return send_response(
                status="fail",
                message=_("Item #{} is missing qty").format(i + 1),
                status_code=400,
                http_status=400
            )

        if rate is None:
            return send_response(
                status="fail",
                message=_("Item #{} is missing rate").format(i + 1),
                status_code=400,
                http_status=400
            )

        try:
            if float(qty) <= 0:
                return send_response(
                    status="fail",
                    message=_("Item #{} qty must be greater than 0").format(i + 1),
                    status_code=400,
                    http_status=400
                )
            if float(rate) < 0:
                return send_response(
                    status="fail",
                    message=_("Item #{} rate cannot be negative").format(i + 1),
                    status_code=400,
                    http_status=400
                )
        except:
            return send_response(
                status="fail",
                message=_("Qty and rate must be numeric values for item #{}").format(i + 1),
                status_code=400,
                http_status=400
            )

    try:
        if not transaction_date:
            transaction_date = frappe.utils.nowdate()

        quotation = frappe.get_doc({
            "doctype": "Quotation",
            "name": next_name,
            "customer": customer_name,
            "company": company_name,
            "currency": currency,
            "valid_till": valid_till,
            "custom_tc": custom_tc,
            "custom_industry_bases": custom_industry_bases,
            "transaction_date": transaction_date,
            "items": items
        })

        quotation.insert()   
        frappe.db.commit()

        return send_response(
            status="success",
            message=_("Quotation created successfully"),
            data={"quotation_id": quotation.name},
            status_code=201,
            http_status=201
        )

    except Exception as e:
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )
        
@frappe.whitelist(allow_guest=False)
def update_quotation():
    data = frappe.local.form_dict
    quotation_id = data.get("quotation_id")

    if not quotation_id:
        return send_response(
            status="fail",
            message="Quotation ID is required",
            status_code=400,
            http_status=400,
        )

    try:
        quotation = frappe.get_doc("Quotation", quotation_id)
    except frappe.DoesNotExistError:
        return send_response(
            status="fail",
            message=f"Quotation {quotation_id} not found",
            status_code=404,
            http_status=404,
        )

    if quotation.docstatus != 0:
        return send_response(
            status="fail",
            message="Cannot update submitted or cancelled Quotation",
            status_code=400,
            http_status=400,
        )


    optional_fields = [
        "customer",
        "transaction_date",
        "custom_swift",
        "custom_bank_name",
        "custom_payment_terms",
        "custom_payment_method",
        "custom_account_number",
        "custom_routing_number",
        "custom_billing_address_line_1",
        "custom_billing_address_line_2",
        "custom_billing_address_city",
        "custom_billing_address_postal_code",
    ]

    for field in optional_fields:
        if field in data:
            quotation.set(field, data.get(field))
    if "items" in data:
        quotation.items = []   
        for item in data.get("items"):
            quotation.append("items", {
                "item_code": item.get("item_code"),
                "qty": item.get("qty"),
                "rate": item.get("rate"),
            })

    try:
        quotation.save(ignore_permissions=True)
    except Exception as e:
        return send_response(
            status="fail",
            message=f"Failed to update: {str(e)}",
            status_code=500,
            http_status=500,
        )

    return send_response(
        status="success",
        message="Quotation updated successfully",
        status_code=200,
        http_status=200,
    )
