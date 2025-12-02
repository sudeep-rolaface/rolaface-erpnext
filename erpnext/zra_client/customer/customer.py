from erpnext.zra_client.generic_api import send_response, send_response_list
from erpnext.zra_client.main import ZRAClient
from frappe import _
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
    print("Fetching existing customer IDs from the database...")
    last_ids = frappe.db.sql("""
        SELECT custom_id FROM `tabCustomer`
        WHERE custom_id LIKE 'CUST-%'
    """, as_dict=True)
    
    print(f"Found {len(last_ids)} existing customer IDs.")

    max_num = 0
    for row in last_ids:
        print(f"Processing row: {row}")
        try:
            num = int(row["custom_id"].split("-")[-1])
            print(f"Extracted numeric part: {num}")
            if num > max_num:
                print(f"Updating max_num: {max_num} -> {num}")
                max_num = num
        except (ValueError, IndexError) as e:
            print(f"Skipping row due to error: {e}")
            continue  

    new_id = f"CUST-{max_num + 1}"
    print(f"Generated new customer ID: {new_id}")
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

        result = ZRA_CLIENT_INSTANCE.create_customer(payload)

        print("Printing result ui", result)
        data = result.json()  
        print("Printing json results",data)

        if data.get("resultCd") != "000":
            send_response(
                status="fail",
                message=data.get("resultMsg", "Customer Sync Failed"),
                status_code=400,
                data=None,
                http_status=400
            )
            return

        customer = frappe.get_doc({
            "doctype": "Customer",
            "custom_id": id,
            "customer_name": customer_name,
            "tax_id": tpin,
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
        }

        send_response(
            status="success",
            message="Customer created successfully.",
            data = data,
            status_code=201,
            http_status=200
        )
        return

    except Exception as e:
        send_response(status="error", message=f"API call failed: {str(e)}", data=None, http_status=500)
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

        all_customers = frappe.get_all(
            "Customer",
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
            ],
            order_by="customer_name asc"
        )

        total_customers = len(all_customers)
        if not all_customers:
            send_response(status="success", message="No customers found.", status_code=200, data=[], http_status=200)
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

@frappe.whitelist(allow_guest=False, methods=["PUT"])
def update_customer_by_id():
    custom_id = (frappe.form_dict.get("id") or "").strip()
    if not custom_id:
        return {
            "status": "fail",
            "message": "Customer id is required (id)",
            "data": None,
            "status_code": 400
        }

    customer = frappe.db.exists("Customer", {"custom_id": custom_id})
    if not customer:
        return {
            "status": "fail",
            "message": "Customer not found",
            "data": None,
            "status_code": 404
        }

    customer = frappe.get_doc("Customer", {"custom_id": custom_id})
    customer_name = (frappe.form_dict.get("name") or "").strip()
    email_id = (frappe.form_dict.get("email") or "").strip()
    mobile_no = (frappe.form_dict.get("mobile") or "").strip()
    customer_type = (frappe.form_dict.get("type") or "").strip()
    customer_currency = (frappe.form_dict.get("currency") or "").strip()
    customer_account_no = (frappe.form_dict.get("accountNumber") or "").strip()
    customer_onboarding_balance = frappe.form_dict.get("onboardingBalance")
    customer_contact_person = (frappe.form_dict.get("contactPerson") or "").strip()
    customer_display_name = (frappe.form_dict.get("displayName") or "").strip()

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
    
    if not validate_customer_type(customer_type):
        return
    field_mapping = {
        "customer_name": customer_name,
        "mobile_no": mobile_no,
        "email_id": email_id,
        "customer_type": customer_type,
        "default_currency": customer_currency,
        "custom_account_number": customer_account_no,
        "custom_onboard_balance": customer_onboarding_balance,
        "custom_billing_adress_line_1": billing_address_line_1,
        "custom_billing_adress_line_2": billing_address_line_2,
        "custom_billing_adress_posta_code": billing_postal_code,
        "custom_billing_adress_city": billing_city,
        "custom_billing_adress_country": billing_country,
        "custom_billing_adress_state": billing_state,
        "custom_shipping_address_line_1_": shipping_address_line_1,
        "custom_shipping_address_line_2_": shipping_address_line_2,
        "custom_shipping_address_posta_code_": shipping_postal_code,
        "custom_shipping_address_city": shipping_city,
        "custom_shipping_address_state": shipping_state,
        "custom_shipping_address_country": shipping_country,
        "custom_contact_person": customer_contact_person,
        "custom_display_name": customer_display_name
    }

    updated_fields = {}
    for key, value in field_mapping.items():
        if value not in (None, ""):
            setattr(customer, key, value)
            updated_fields[key] = value

    if not updated_fields:
        return {
            "status": "fail",
            "message": "No valid fields provided to update.",
            "data": None,
            "status_code": 400
        }

    try:
        customer.ignore_mandatory = True
        customer.flags.ignore_links = True

        customer.save(ignore_permissions=True)
        frappe.db.commit()
        
        customer = frappe.get_doc("Customer", {"custom_id": custom_id})
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
        }


        return {
            "status": "success",
            "message": "Customer updated successfully",
            "data": data,
            "status_code": 200
        }

    except Exception as e:
        return {
            "status": "error",
            "message": _("Failed to update customer: {0}").format(str(e)),
            "data": None,
            "status_code": 500
        }



@frappe.whitelist(allow_guest=False)
def delete_customer_by_id():
    id = (frappe.form_dict.get("id") or "").strip()
    if not id:
        send_response(status="fail", message="Customer id is required", status_code=400, http_status=400)
        return
    try:
        customer = frappe.get_doc("Customer", {"custom_id": id})
        if customer:
            customer.delete()
            frappe.db.commit()
            send_response(status="success", message="Customer with TPIN deleted successfully", status_code=204,http_status=204) 
            return
        else:
            send_response(status="fail", message="Customer not found", status_code=404, http_status=404)
            return

    except frappe.DoesNotExistError:
        send_response(status="fail", message="Customer not found", status_code=404, http_status=404)
        return
    except Exception as e:
        send_response(status="error", message=f"Failed to retrieve customers: {str(e)}", status_code=500, data=None, http_status=500)
        return
