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
    valid_currencies = ["ZMW", "USD", "EUR", "GBP","INR"]
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
    
    
@frappe.whitelist(allow_guest=False)
def get_all_customers_api():
    try:
        args = frappe.request.args
        page = args.get("page")
        if not page:
            send_response(status="error", message="'page' parameter is required.", status_code=400, data=None, http_status=400)
            return
        try:
            page = int(page)
            if page < 1:
                raise ValueError
        except ValueError:
            send_response(status="error", message="'page' must be a positive integer.", status_code=400, data=None, http_status=400)
            return

        page_size = args.get("page_size")
        if not page_size:
            send_response(status="error", message="'page_size' parameter is required.", status_code=400, data=None, http_status=400)
            return
        try:
            page_size = int(page_size)
            if page_size < 1:
                raise ValueError
        except ValueError:
            send_response(status="error", message="'page_size' must be a positive integer.", status_code=400, data=None, http_status=400)
            return

        start = (page - 1) * page_size
        end = start + page_size
        
        tax_category_filter = args.get("taxCategory") 
        filters = {}
        if tax_category_filter:
            filters["tax_category"] = tax_category_filter

        all_customers = frappe.get_all(
            "Customer",
            filters=filters,
            fields=[
                "custom_id", 
                "customer_name", 
                "customer_type",
                "tax_id", 
                "mobile_no", 
                "email_id", 
                "default_currency",
                "custom_account_number", 
                "custom_onboard_balance",
                "custom_contact_person",
                "custom_display_name",
                "tax_category",
            ],
            order_by="customer_name asc"
        )

        total_customers = len(all_customers)
        if not all_customers:
            send_response(status="success", message="No customers found.", status_code=404, data=[], http_status=404)
            return

        customers = all_customers[start:end]
        for cust in customers:
            cust["id"] = cust.pop("custom_id")
            cust["tpin"] = cust.pop("tax_id")
            cust["name"] = cust.pop("customer_name")
            cust["contactPerson"] = cust.pop("custom_contact_person")
            cust["displayName"] = cust.pop("custom_display_name")
            cust["mobile"] = cust.pop("mobile_no")
            cust["type"] = cust.pop("customer_type")
            cust["email"] = cust.pop("email_id")
            cust["accountNumber"] = cust.pop("custom_account_number")
            cust["currency"] = cust.pop("default_currency")
            cust["onboardingBalance"] = cust.pop("custom_onboard_balance")
            
            VALID_TAX_CATEGORY = ZRA_CLIENT_INSTANCE.getTaxCategory()

            cust["customerTaxCategory"] = cust.get("tax_category", "")

            if cust["customerTaxCategory"] not in VALID_TAX_CATEGORY:
                cust["customerTaxCategory"] = ""
            cust.pop("tax_category", None)

        total_pages = (total_customers + page_size - 1) // page_size
        
        response_data = {
            "success": True,
            "message": "Customers retrieved successfully",
            "data": customers,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_customers,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        send_response_list(
            status="success",
            message="Customers retrieved successfully",
            status_code=200,
            data=response_data,
            http_status=200
        )
        return

    except Exception as e:
        send_response(status="error", message=f"Failed to retrieve customers: {str(e)}", status_code=500, data=None, http_status=500)
        return



@frappe.whitelist(allow_guest=False)
def get_customer_by_id(custom_id):
    try:
        customer = frappe.get_doc("Customer", {"custom_id": custom_id})
        def safe_attr(obj, attr):
            return getattr(obj, attr, "") or "" 


        VALID_TAX_CATEGORY = ZRA_CLIENT_INSTANCE.getTaxCategory()

        tax_cat = safe_attr(customer, "tax_category").strip()

        if tax_cat not in VALID_TAX_CATEGORY:
            tax_cat = ""
        
        try:
            terms_doc = frappe.get_doc("Customer Terms", {"customer": custom_id})


            payment_phases_docs = frappe.get_all(
                "Payment Terms",
                filters={"customer": custom_id},
                fields=["dueDates", "lateCharges", "tax", "notes"]
            )

            phases_docs = frappe.get_all(
                "Payment Terms Phases",
                filters={"customer": custom_id},  
                fields=["id","phase", "percentage", "condition"]
            )

            phases_list = []
            frappe.logger().debug(f"Phase list: {phases_docs}")
            for p in phases_docs:
                phases_list.append({
                    "id": p.get("id"),
                    "name": p.get("phase"),
                    "percentage": p.get("percentage"),
                    "condition": p.get("condition")
                })

    
            payment_info = {}
            if payment_phases_docs:
                first = payment_phases_docs[0]
                payment_info = {
                    "phases": phases_list,
                    "dueDates": first.get("dueDates"),
                    "lateCharges": first.get("lateCharges"),
                    "taxes": first.get("tax"),
                    "notes": first.get("notes")
                }

            terms = {
                "selling": {
                    "general": safe_attr(terms_doc, "general"),
                    "payment": payment_info,
                    "delivery": safe_attr(terms_doc, "delivery"),
                    "cancellation": safe_attr(terms_doc, "cancellation"),
                    "warranty": safe_attr(terms_doc, "warranty"),
                    "liability": safe_attr(terms_doc, "liability")
                }
            }



        except frappe.DoesNotExistError:
            terms = {}
        data = {
            "id": safe_attr(customer, "custom_id"),
            "tpin": safe_attr(customer, "tax_id"),
            "customerTaxCategory": tax_cat,
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
            "terms": terms
        }

        return send_response(
            status="success",
            message="Customer retrieved successfully",
            status_code=200,
            data=data,
            http_status=200
        )

    except frappe.DoesNotExistError:
        return send_response(
            status="fail",
            message=f"Customer with ID {custom_id} not found",
            status_code=404,
            http_status=404
        )
    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to retrieve customer: {str(e)}",
            status_code=500,
            data=None,
            http_status=500
        )
        


@frappe.whitelist(allow_guest=False, methods=["PATCH"])
def update_customer_by_id():
    custom_id = (frappe.form_dict.get("id") or "").strip()
    if not custom_id:
        return {
            "status": "fail",
            "message": "Customer id is required (id)",
            "data": None,
            "status_code": 400
        }

    if not frappe.db.exists("Customer", {"custom_id": custom_id}):
        return {
            "status": "fail",
            "message": "Customer not found",
            "data": None,
            "status_code": 404
        }
    customerTaxCategory = (frappe.form_dict.get("customerTaxCategory") or "").strip()
    if customerTaxCategory:
        VALID_TAX_CATEGORY = ZRA_CLIENT_INSTANCE.getTaxCategory()
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
                return {
                    "status": "error",
                    "message": f"Failed to create Tax Category: {str(e)}",
                    "status_code": 500,
                    "http_status": 500
                }


    customer = frappe.get_doc("Customer", {"custom_id": custom_id})
    field_mapping = {
        "customer_name": frappe.form_dict.get("name"),
        "mobile_no": frappe.form_dict.get("mobile"),
        "tax_category": customerTaxCategory,
        "email_id": frappe.form_dict.get("email"),
        "customer_type": frappe.form_dict.get("type"),
        "default_currency": frappe.form_dict.get("currency"),
        "custom_account_number": frappe.form_dict.get("accountNumber"),
        "custom_onboard_balance": frappe.form_dict.get("onboardingBalance"),
        "custom_billing_address_line_1": frappe.form_dict.get("billingAddressLine1"),
        "custom_billing_address_line_2": frappe.form_dict.get("billingAddressLine2"),
        "custom_billing_address_postal_code": frappe.form_dict.get("billingPostalCode"),
        "custom_billing_address_city": frappe.form_dict.get("billingCity"),
        "custom_billing_address_state": frappe.form_dict.get("billingState"),
        "custom_billing_address_country": frappe.form_dict.get("billingCountry"),
        "custom_shipping_address_line_1": frappe.form_dict.get("shippingAddressLine1"),
        "custom_shipping_address_line_2": frappe.form_dict.get("shippingAddressLine2"),
        "custom_shipping_address_postal_code": frappe.form_dict.get("shippingPostalCode"),
        "custom_shipping_address_city": frappe.form_dict.get("shippingCity"),
        "custom_shipping_address_state": frappe.form_dict.get("shippingState"),
        "custom_shipping_address_country": frappe.form_dict.get("shippingCountry"),
        "custom_contact_person": frappe.form_dict.get("contactPerson"),
        "custom_display_name": frappe.form_dict.get("displayName")
    }

    # Update fields
    for key, value in field_mapping.items():
        if value not in (None, ""):
            setattr(customer, key, value)

    # Validate customer type
    if not validate_customer_type(customer.customer_type):
        return {
            "status": "fail",
            "message": "Invalid customer type",
            "data": None,
            "status_code": 400
        }

    # Save customer before processing terms
    customer.ignore_mandatory = True
    customer.flags.ignore_links = True
    customer.save(ignore_permissions=True)
    frappe.db.commit()

    # Process terms if provided
    terms = frappe.form_dict.get("terms") or {}
    selling = terms.get("selling") or {}
    if selling:
        terms_doc_list = frappe.get_all("Customer Terms", filters={"customer": custom_id}, limit_page_length=1)
        if terms_doc_list:
            terms_doc = frappe.get_doc("Customer Terms", terms_doc_list[0].name)
        else:
            terms_doc = frappe.get_doc({"doctype": "Customer Terms", "customer": custom_id})

        terms_doc.general = selling.get("general") or ""
        terms_doc.delivery = selling.get("delivery") or ""
        terms_doc.cancellation = selling.get("cancellation") or ""
        terms_doc.warranty = selling.get("warranty") or ""
        terms_doc.liability = selling.get("liability") or ""
        terms_doc.save(ignore_permissions=True)

        payment = selling.get("payment") or {}
        if payment:
            payment_doc_list = frappe.get_all("Payment Terms", filters={"customer": custom_id}, limit_page_length=1)
            if payment_doc_list:
                payment_doc = frappe.get_doc("Payment Terms", payment_doc_list[0].name)
            else:
                payment_doc = frappe.get_doc({"doctype": "Payment Terms", "customer": custom_id})

            payment_doc.duedates = payment.get("dueDates", "")
            payment_doc.latecharges = payment.get("lateCharges", "")
            payment_doc.tax = payment.get("taxes", "")
            payment_doc.notes = payment.get("notes", "")
            payment_doc.save(ignore_permissions=True)

            phases = payment.get("phases", [])
            for phase in phases:
                phase_id = phase.get("id")
                phase_name = phase.get("name")
                phase_percentage = phase.get("percentage")
                phase_condition = phase.get("condition")
                is_delete = phase.get("isDelete", 0)

                existing = frappe.get_all("Payment Terms Phases", filters={"customer": custom_id, "id": phase_id}, limit=1)

                if existing:
                    phase_doc = frappe.get_doc("Payment Terms Phases", existing[0].name)
                    if is_delete:
                        frappe.delete_doc("Payment Terms Phases", phase_doc.name, ignore_permissions=True)
                        continue
                    phase_doc.phase = phase_name
                    phase_doc.percentage = phase_percentage
                    phase_doc.condition = phase_condition
                    phase_doc.save(ignore_permissions=True)
                else:
                    if is_delete:
                        continue
                    random_id = "{:06d}".format(random.randint(0, 999999))
                    phase_doc = frappe.get_doc({
                        "doctype": "Payment Terms Phases",
                        "customer": custom_id,
                        "id": random_id,
                        "phase": phase_name,
                        "percentage": phase_percentage,
                        "condition": phase_condition
                    })
                    phase_doc.insert(ignore_permissions=True)
            frappe.db.commit()

    return send_response(
        status = "success",
        message = "Customer updated successfully",
        status_code = 200,
        http_status = 200
    )


@frappe.whitelist(allow_guest=False)
def delete_customer_by_id():
    id = (frappe.form_dict.get("id") or "").strip()

    if not id:
        send_response(
            status="fail",
            message="Customer id is required",
            status_code=400,
            http_status=400
        )
        return

    try:
        customer = frappe.get_doc("Customer", {"custom_id": id})

        if not customer:
            send_response(
                status="fail",
                message="Customer not found",
                status_code=404,
                http_status=404
            )
            return
        terms_list = frappe.get_all(
            "Payment Terms",
            filters={"customer": id},
            pluck="name"
        )

        for term in terms_list:
            frappe.delete_doc("Payment Terms", term, force=1)

        phases_list = frappe.get_all(
            "Payment Terms Phases",
            filters={"customer": id},
            pluck="name"
        )

        for phase in phases_list:
            frappe.delete_doc("Payment Terms Phases", phase, force=1)

        customer.delete()
        frappe.db.commit()

        send_response(
            status="success",
            message="Customer and all related terms/conditions/phases deleted successfully",
            status_code=200,
            http_status=200
        )
        return

    except frappe.DoesNotExistError:
        send_response(
            status="fail",
            message="Customer not found",
            status_code=404,
            http_status=404
        )
        return

    except Exception as e:
        send_response(
            status="error",
            message=f"Failed to delete customer: {str(e)}",
            status_code=500,
            http_status=500
        )
        return
