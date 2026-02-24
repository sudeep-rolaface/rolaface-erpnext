import json
from erpnext.zra_client.generic_api import send_response, send_response_list
from erpnext.zra_client.main import ZRAClient
from frappe.utils import random_string
from frappe import _
import random
import frappe
import re



ZRA_CLIENT_INSTANCE = ZRAClient()

def validate_address(address, address_type):
    for field_name, value in address.items():
        if not value:
            send_response(
                status="fail",
                message=f"{address_type} {field_name} is required.",
                status_code=400,
                http_status=400
            )
            return False  
    return True

def validate_phone(phone):
    if not phone:
        send_response(
            status="fail",
            message="Phone number is required.",
            status_code=400,
            http_status=400
        )
        return False


    normalized_phone = phone
    existing_customer = frappe.db.exists("Customer", {"mobile_no": normalized_phone})
    if existing_customer:
        send_response(
            status="fail",
            message=f"Phone number already exists: {normalized_phone}",
            status_code=409,
            http_status=409
        )
        return False

    return True


def validate_email(email_id):
    if not email_id:
        send_response(
            status="fail",
            message="Email is required.",
            status_code=400,
            http_status=400
        )
        return False

    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    if not re.fullmatch(pattern, email_id):
        send_response(
            status="fail",
            message=f"Invalid email_id format: {email_id}. Expected format like user@example.com",
            status_code=400,
            http_status=400
        )
        return False

    if frappe.db.exists("Customer", {"email_id": email_id}):
        send_response(
            status="fail",
            message=f"Email already exists: {email_id}",
            status_code=409,
            http_status=409
        )
        return False

    return True


def validate_account(customerAccountNo):
    if frappe.db.exists("Customer", {"custom_customer_customerAccountNo_no": customerAccountNo}):
        send_response(
            status="fail",
            message=f"customerAccountNo number already exists: {customerAccountNo}",
            status_code=409,
            http_status=409
        )
        return 
    return True

def validate_customer_type(customer_type):
    valid_types = ["Individual", "Company", "Partnership"]
    if customer_type not in valid_types:
        send_response(
            status="fail",
            message=f"Invalid customer type. Valid types are: {', '.join(valid_types)}",
            status_code=400,
            http_status=400
        )
        return False
    return True

def validate_currency(currency):
    valid_currencies = ["ZMW", "USD", "EUR", "GBP"]
    if currency not in valid_currencies:
        send_response(
            status="fail",
            message=f"Invalid currency. Valid currencies are: {', '.join(valid_currencies)}",
            status_code=400,
            http_status=400
        )
        return False
    return True



def generate_customer_id():
    frappe.logger().debug("Fetching existing customer IDs from the database...")
    last_ids = frappe.db.sql("""
        SELECT custom_id FROM `tabCustomer`
        WHERE custom_id LIKE 'CUST-%'
    """, as_dict=True)
    
    frappe.logger().debug(f"Found {len(last_ids)} existing customer IDs.")

    max_num = 0
    for row in last_ids:
        frappe.logger().debug(f"Processing row: {row}")
        try:
            num = int(row["custom_id"].split("-")[-1])
            frappe.logger().debug(f"Extracted numeric part: {num}")
            if num > max_num:
                frappe.logger().debug(f"Updating max_num: {max_num} -> {num}")
                max_num = num
        except (ValueError, IndexError) as e:
            frappe.logger().debug(f"Skipping row due to error: {e}")
            continue  

    new_id = f"CUST-{max_num + 1}"
    frappe.logger().debug(f"Generated new customer ID: {new_id}")
    return new_id





@frappe.whitelist(allow_guest=False)
def create_customer_api():
    tpin = (frappe.form_dict.get("tpin") or "")
    customer_name = (frappe.form_dict.get("name") or "").strip()
    email_id = (frappe.form_dict.get("email") or "").strip()
    mobile_no = (frappe.form_dict.get("mobile") or "")
    customerType = (frappe.form_dict.get("type") or "").strip()
    customerEmail = (frappe.form_dict.get("email") or "").strip()
    customerCurrency = (frappe.form_dict.get("currency") or "").strip()
    customerAccountNo = (frappe.form_dict.get("accountNumber") or "")
    customer_onboarding_balance = frappe.form_dict.get("onboardingBalance") or "0"
    customerTaxCategory = (frappe.form_dict.get("customerTaxCategory") or "").strip()
    
    
    VALID_TAX_CATEGORY = ZRA_CLIENT_INSTANCE.getTaxCategory()
    if not customerTaxCategory:
        return send_response(
            status="fail",
            message="Tax category is required (customerTaxCategory)",
            status_code=400,
            http_status=400
        )

    if customerTaxCategory not in VALID_TAX_CATEGORY:
        return send_response(
            status="fail",
            message=f"Invalid tax category. Should be of {VALID_TAX_CATEGORY}",
            status_code=400,
            http_status=400
        )
    tax_category_doc = frappe.db.get_value("Tax Category", {"name": customerTaxCategory})
    if not tax_category_doc:
        try:
            frappe.get_doc({
                "doctype": "Tax Category",
                "title": customerTaxCategory
            }).insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            return send_response(status="error", message=f"Failed to create Tax Category: {str(e)}", status_code=500, http_status=500)

    try:
        customer_onboarding_balance = float(customer_onboarding_balance)
    except ValueError:
        customer_onboarding_balance = 0.0  

    billing_address_line_1 = (frappe.form_dict.get("billingAddressLine1") or "").strip()
    billing_address_line_2 = (frappe.form_dict.get("billingAddressLine2") or "").strip()
    billing_postal_code = (frappe.form_dict.get("billingPostalCode") or "").strip()
    billing_city = (frappe.form_dict.get("billingCity") or "").strip()
    billing_state = (frappe.form_dict.get("billingState") or "").strip()
    billing_country = (frappe.form_dict.get("billingCountry") or "").strip()

    shipping_address_line_1 = (frappe.form_dict.get("shippingAddressLine1") or "").strip()
    shipping_address_line_2 = (frappe.form_dict.get("shippingAddressLine2") or "").strip()
    shipping_postal_code = (frappe.form_dict.get("shippingPostalCode") or "").strip()
    shipping_city = (frappe.form_dict.get("shippingCity") or "").strip()
    shipping_state = (frappe.form_dict.get("shippingState") or "").strip()
    shipping_country = (frappe.form_dict.get("shippingCountry") or "").strip()
    
    terms = frappe.form_dict.get("terms") or {}
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

    
    frappe.logger().debug(f"TERMS: {terms}")
    frappe.logger().debug(f"GENERAL: {general}")
    frappe.logger().debug(f"DELIVERY: {delivery}")
    frappe.logger().debug(f"CANCELLATION: {cancellation}")
    frappe.logger().debug(f"WARRANTY: {warranty}")
    frappe.logger().debug(f"LIABILITY: {liability}")
    
    if not mobile_no.isdigit() or len(mobile_no) != 10:
        send_response(status="fail", message="Mobile number must be 10 digits only", status_code=400, http_status=400)
        return

    
    if not billing_address_line_1:
        send_response(status="fail", message="Billing address line 1 is required (billingAddressLine1)", status_code=400, http_status=400)
        return

    if not billing_postal_code:
        send_response(status="fail", message="Billing postal code is required (billingPostalCode)", status_code=400, http_status=400)
        return

    if not billing_city:
        send_response(status="fail", message="Billing city is required (billingCity)", status_code=400, http_status=400)
        return

    if not billing_state:
        send_response(status="fail", message="Billing state is required (billingState)", status_code=400, http_status=400)
        return

    if not billing_country:
        send_response(status="fail", message="Billing country is required (billingCountry)", status_code=400, http_status=400)
        return

    if not shipping_address_line_1:
        send_response(status="fail", message="Shipping address line 1 is required (shippingAddressLine1)", status_code=400, http_status=400)
        return

    if not shipping_postal_code:
        send_response(status="fail", message="Shipping postal code is required (shippingPostalCode)", status_code=400, http_status=400)
        return

    if not shipping_city:
        send_response(status="fail", message="Shipping city is required (shippingCity)", status_code=400, http_status=400)
        return

    if not shipping_state:
        send_response(status="fail", message="Shipping state is required (shippingState)", status_code=400, http_status=400)
        return

    if not shipping_country:
        send_response(status="fail", message="Shipping country is required (shippingCountry)", status_code=400, http_status=400)
        return


    contactPerson = (frappe.form_dict.get("contactPerson") or "").strip()
    displayName = (frappe.form_dict.get("displayName") or "").strip()


    if not customerCurrency:
        send_response(status="fail", message="Customer currency is required (customer_currency)", status_code=400, http_status=400)
        return
    if not validate_currency(customerCurrency):
        return

    if not customerType:
        send_response(status="fail", message="Customer type is required (customer_type)", status_code=400, http_status=400)
        return
    if not validate_customer_type(customerType):
        return

    if not tpin:
        send_response(status="fail", message="TPIN is required (custom_customer_tpin)", status_code=400, http_status=400)
        return
    if not customer_name:
        send_response(status="fail", message="Customer name is required (customer_name)", status_code=400, http_status=400)
        return
    if not mobile_no:
        send_response(status="fail", message="Customer mobile number is required (mobile_no)", status_code=400, http_status=400)
        return

    existing_customer = frappe.db.get_value(
        "Customer", {"tax_id": tpin}, ["name"]
    )
    if existing_customer:
        send_response(status="fail", message=f"A customer with TPIN {tpin} already exists.", status_code=400, http_status=400)
        return
    id = generate_customer_id()
    if not (validate_phone(mobile_no) and validate_email(email_id) and validate_account(customerAccountNo)):
        return 
    
    try:
        # Try to sync with ZRA, but don't fail if it's unavailable
        zra_sync_success = False
        zra_sync_message = ""
        
        try:
            payload = {
                "tpin": ZRA_CLIENT_INSTANCE.get_tpin(),
                "bhfId": ZRA_CLIENT_INSTANCE.get_branch_code(),
                "custNo": mobile_no,
                "custTpin": tpin,
                "custNm": customer_name,
                "useYn": "Y",
                "regrNm": frappe.session.user,
                "regrId": frappe.session.user,
                "modrNm": frappe.session.user,
                "modrId": frappe.session.user,
            }
            frappe.logger().debug(f"ZRA Payload: {json.dumps(payload, indent=4)}")

            result = ZRA_CLIENT_INSTANCE.create_customer(payload)

            frappe.logger().debug(f"ZRA API result: {result}")
            data = result.json()  
            frappe.logger().debug(f"ZRA API json results: {data}")

            if data.get("resultCd") == "000":
                zra_sync_success = True
                zra_sync_message = "Customer synced with ZRA successfully"
            else:
                zra_sync_message = f"ZRA sync failed: {data.get('resultMsg', 'Unknown error')}"
                frappe.logger().warning(zra_sync_message)
        except Exception as zra_error:
            zra_sync_message = f"ZRA API unavailable: {str(zra_error)}"
            frappe.logger().warning(f"ZRA sync failed but continuing: {zra_sync_message}")
            # Continue with customer creation even if ZRA fails

        customer = frappe.get_doc({
            "doctype": "Customer",
            "custom_id": id,
            "customer_name": customer_name,
            "tax_id": tpin,
            "tax_category": customerTaxCategory,
            "mobile_no": mobile_no,
            "customer_type": customerType,
            "email_id": customerEmail or email_id, 
            "default_currency": customerCurrency,
            "custom_account_number": customerAccountNo,
            "custom_onboard_balance": customer_onboarding_balance,
            "custom_billing_adress_line_1": billing_address_line_1,
            "custom_billing_adress_line_2": billing_address_line_2,
            "custom_billing_adress_posta_code": billing_postal_code,
            "custom_billing_adress_city": billing_city,
            "custom_billing_adress_country": billing_country,
            "custom_billing_adress_state": billing_state,
            "custom_shipping_address_line_1_": shipping_address_line_1,
            "custom_shipping_address_line_2": shipping_address_line_2,
            "custom_shipping_address_posta_code_": shipping_postal_code,
            "custom_shipping_address_city": shipping_city,
            "custom_shipping_address_state": shipping_state,
            "custom_shipping_address_country": shipping_country,
            "custom_contact_person":contactPerson,
            "custom_display_name":displayName
        })

        customer.insert()

        terms_doc = frappe.get_doc({
            "doctype": "Customer Terms",
            "customer": id,
            "general": general,
            "delivery": delivery,
            "cancellation": cancellation,
            "warranty": warranty,
            "liability": liability
        })
        terms_doc.insert()
        frappe.db.commit()
        
        if payment_terms_data:
            payment_doc = frappe.get_doc({
                "doctype": "Payment Terms",
                "customer": id,
                "duedates": dueDates,     
                "latecharges": lateCharges, 
                "tax": tax,
                "notes": notes
            })
            payment_doc.insert()
            frappe.db.commit()
        if phases:
            for phase in phases:
                
                random_id = "{:06d}".format(random.randint(0, 999999)) 
                phase_doc = frappe.get_doc({
                    "doctype": "Payment Terms Phases",
                    "id": random_id,
                    "customer": id, 
                    "phase": phase.get("name"),
                    "percentage": phase.get("percentage", ""),
                    "condition": phase.get("condition", "")
                })
                phase_doc.insert()
                frappe.db.commit()


        
        customer = frappe.get_doc("Customer", {"custom_id": id})
        def safe_attr(obj, attr):
            return getattr(obj, attr, "") or "" 
        data = {
            "id": safe_attr(customer, "custom_id"),
            "tpin": safe_attr(customer, "tax_id"),
            "name": safe_attr(customer, "customer_name"),
            "type": safe_attr(customer, "customer_type"),
            "mobile": safe_attr(customer, "mobile_no"),
            "email": safe_attr(customer, "email_id"),
            "contactPerson": safe_attr(customer, "custom_contact_person"),
            "displayName": safe_attr(customer, "custom_display_name"),
            "currency": safe_attr(customer, "default_currency"),
            "accountNumber": safe_attr(customer, "custom_account_number"),
            "onboardingBalance": safe_attr(customer, "custom_onboard_balance"),
            "billingAddressLine1": safe_attr(customer, "custom_billing_adress_line_1"),
            "billingAddressLine2": safe_attr(customer, "custom_billing_adress_line_2"),
            "billingPostalCode": safe_attr(customer, "custom_billing_adress_posta_code"),
            "billingCity": safe_attr(customer, "custom_billing_adress_city"),
            "billingState": safe_attr(customer, "custom_billing_adress_state"),
            "billingCountry": safe_attr(customer, "custom_billing_adress_country"),
            "shippingAddressLine1": safe_attr(customer, "custom_shipping_address_line_1_"),
            "shippingAddressLine2": safe_attr(customer, "custom_shipping_address_line_2"),
            "shippingPostalCode": safe_attr(customer, "custom_shipping_address_posta_code_"),
            "shippingCity": safe_attr(customer, "custom_shipping_address_city"),
            "shippingState": safe_attr(customer, "custom_shipping_address_state"),
            "shippingCountry": safe_attr(customer, "custom_shipping_address_country"),
            "zra_sync_status": "success" if zra_sync_success else "failed",
            "zra_sync_message": zra_sync_message
        }

        message = "Customer created successfully."
        if not zra_sync_success:
            message += f" (Warning: {zra_sync_message})"

        send_response(
            status="success",
            message=message,
            data = data,
            status_code=201,
            http_status=200
        )
        return

    except Exception as e:
        send_response(status="error", message=f"Failed to create customer: {str(e)}", data=None, http_status=500)
        return
