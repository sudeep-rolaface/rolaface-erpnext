from erpnext.zra_client.generic_api import send_response
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
        return False
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
    tpin = (frappe.form_dict.get("custom_customer_tpin") or "")
    customer_name = (frappe.form_dict.get("customer_name") or "").strip()
    email_id = (frappe.form_dict.get("customer_email") or "").strip()
    mobile_no = (frappe.form_dict.get("mobile_no") or "")
    customerType = (frappe.form_dict.get("customer_type") or "").strip()
    customerEmail = (frappe.form_dict.get("customer_email") or "").strip()
    customerCurrency = (frappe.form_dict.get("customer_currency") or "").strip()
    customerAccountNo = (frappe.form_dict.get("customer_account_no") or "")
    customerOnboardingBalance = (frappe.form_dict.get("customer_onboarding_balance") or "").strip()
    customerTermsAndCondtions = (frappe.form_dict.get("customer_terms"))

    billingAddress = {
    "Line1": (frappe.form_dict.get("customer_billing_address_line1") or "").strip(),
    "Line2": (frappe.form_dict.get("customer_billing_address_line2") or "").strip(),
    "PostalCode": (frappe.form_dict.get("customer_billing_postal_code") or "").strip(),
    "City": (frappe.form_dict.get("customer_billing_city") or "").strip(),
    "Country": (frappe.form_dict.get("customer_billing_country") or "").strip(),
    "State": (frappe.form_dict.get("customer_billing_state") or "").strip(),
    "County": (frappe.form_dict.get("customer_billing_country") or "").strip()
    }

    shippingAddress = {
        "Line1": (frappe.form_dict.get("customer_shipping_address_line1") or "").strip(),
        "Line2": (frappe.form_dict.get("customer_shipping_address_line2") or "").strip(),
        "PostalCode": (frappe.form_dict.get("customer_shipping_postal_code") or "").strip(),
        "City": (frappe.form_dict.get("customer_shipping_city") or "").strip(),
        "Country": (frappe.form_dict.get("customer_shipping_country") or "").strip(),
        "State": (frappe.form_dict.get("customer_shipping_state") or "").strip()
    }

    if not validate_address(billingAddress, "Billing Address"):
        return
    if not validate_address(shippingAddress, "Shipping Address"):
        return


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
        }

        result = ZRA_CLIENT_INSTANCE.create_customer(payload)
        data = result.json()  

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
            "custom_onboard_balance": customerOnboardingBalance,
            "custom_billing_adress_line_1": billingAddress["Line1"],
            "custom_billing_adress_line_2": billingAddress["Line2"],
            "custom_billing_adress_posta_code": billingAddress["PostalCode"],
            "custom_billing_adress_city": billingAddress["City"],
            "custom_billing_adress_country": billingAddress["Country"],
            "custom_billing_adress_state": billingAddress["State"],
            "custom_billing_adress_county": billingAddress.get("County", ""),
            "custom_shipping_address_line_1_": shippingAddress["Line1"],
            "custom_shipping_address_line_2": shippingAddress["Line2"],
            "custom_shipping_address_posta_code_": shippingAddress["PostalCode"],
            "custom_shipping_address_city": shippingAddress["City"],
            "custom_shipping_address_state": shippingAddress["State"],
            "custom_shipping_address_country": shippingAddress["Country"],
            "custom_tc": customerTermsAndCondtions
        })

        customer.insert()
        frappe.db.commit()

        send_response(
            status="success",
            message="Customer created successfully.",
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
        customers = frappe.get_all(
            "Customer",
            fields=[
                "custom_id", "name", "customer_name", "customer_type",
                "tax_id", "mobile_no", "email_id", "default_currency",
                "custom_account_number", "custom_onboard_balance",
                "custom_billing_adress_line_1",
                "custom_billing_adress_line_2",
                "custom_billing_adress_posta_code",
                "custom_billing_adress_city",
                "custom_billing_adress_country",
                "custom_billing_adress_state",
                "custom_billing_adress_county",
                "custom_shipping_address_line_1_",
                "custom_shipping_address_line_2",
                "custom_shipping_address_posta_code_",
                "custom_shipping_address_city",
                "custom_shipping_address_state",
                "custom_shipping_address_country"
            ],
            order_by="customer_name asc"
        )

        if not customers:
            send_response(status="success", message="No customers found.", status_code=200, data=[], http_status=200)
            return

        for cust in customers:
            cust["custom_customer_tpin"] = cust.pop("tax_id")
            cust["customer_onboarding_balance"] = cust.pop("custom_onboard_balance")
            cust["customer_account_no"] = cust.pop("custom_account_number")
            cust["customer_currency"] = cust.pop("default_currency")

            
            cust["billing"] = {
                "line1": cust.pop("custom_billing_adress_line_1"),
                "line2": cust.pop("custom_billing_adress_line_2"),
                "postal_code": cust.pop("custom_billing_adress_posta_code"),
                "city": cust.pop("custom_billing_adress_city"),
                "country": cust.pop("custom_billing_adress_country"),
                "state": cust.pop("custom_billing_adress_state"),
                "county": cust.pop("custom_billing_adress_county"),
            }


            cust["shipping"] = {
                "line1": cust.pop("custom_shipping_address_line_1_"),
                "line2": cust.pop("custom_shipping_address_line_2"),
                "postal_code": cust.pop("custom_shipping_address_posta_code_"),
                "city": cust.pop("custom_shipping_address_city"),
                "state": cust.pop("custom_shipping_address_state"),
                "country": cust.pop("custom_shipping_address_country"),
            }

        send_response(
            status="success",
            message="Customers retrieved successfully",
            status_code=200,
            data=customers,
            http_status=200
        )
        return

    except Exception as e:
        send_response(
            status="error",
            message=f"Failed to retrieve customers: {str(e)}",
            status_code=500,
            data=None,
            http_status=500
        )
        return


@frappe.whitelist(allow_guest=False)
def get_customer_by_id(custom_id):
    try:
        customer = frappe.get_doc("Customer", {"custom_id": custom_id})
        def safe_attr(obj, attr):
            return getattr(obj, attr, None)
        data = {
            "custom_customer_tpin": safe_attr(customer, "tax_id"),
            "name": safe_attr(customer, "name"),
            "customer_name": safe_attr(customer, "customer_name"),
            "customer_type": safe_attr(customer, "customer_type"),
            "mobile_no": safe_attr(customer, "mobile_no"),
            "email_id": safe_attr(customer, "email_id"),
            "customer_currency": safe_attr(customer, "default_currency"),
            "customer_account_no": safe_attr(customer, "custom_account_number"),
            "customer_onboarding_balance": safe_attr(customer, "custom_onboard_balance"),
            "billing": {
                "line1": safe_attr(customer, "custom_billing_address_line_1"),
                "line2": safe_attr(customer, "custom_billing_address_line_2"),
                "postal_code": safe_attr(customer, "custom_billing_address_postal_code"),
                "city": safe_attr(customer, "custom_billing_address_city"),
                "state": safe_attr(customer, "custom_billing_address_state"),
                "country": safe_attr(customer, "custom_billing_address_country"),
                "county": safe_attr(customer, "custom_billing_address_county"),
            },
            "shipping": {
                "line1": safe_attr(customer, "custom_shipping_address_line_1"),
                "line2": safe_attr(customer, "custom_shipping_address_line_2"),
                "postal_code": safe_attr(customer, "custom_shipping_address_postal_code"),
                "city": safe_attr(customer, "custom_shipping_address_city"),
                "state": safe_attr(customer, "custom_shipping_address_state"),
                "country": safe_attr(customer, "custom_shipping_address_country"),
            }
        }
        send_response(
            status="success",
            message="Customer retrieved successfully",
            status_code=200,
            data=data,
            http_status=200
        )

    except frappe.DoesNotExistError:
        send_response(
            status="fail",
            message=f"Customer with ID {custom_id} not found",
            status_code=404,
            http_status=404
        )
    except Exception as e:
        send_response(
            status="error",
            message=f"Failed to retrieve customer: {str(e)}",
            status_code=500,
            data=None,
            http_status=500
        )


@frappe.whitelist(allow_guest=False)
def update_customer_by_id():
    custom_id = (frappe.form_dict.get("id") or "").strip()
    if not custom_id:
        send_response(
            status="fail",
            message="Customer id is required (id)",
            status_code=400,
            http_status=400
        )
        return

    customer_name = (frappe.form_dict.get("customer_name") or "").strip()
    email_id = (frappe.form_dict.get("customer_email") or "").strip()
    mobile_no = (frappe.form_dict.get("mobile_no") or "").strip()
    customerType = (frappe.form_dict.get("customer_type") or "").strip()
    customerCurrency = (frappe.form_dict.get("customer_currency") or "").strip()
    customerAccountNo = (frappe.form_dict.get("customer_account_no") or "").strip()
    customerOnboardingBalance = (frappe.form_dict.get("customer_onboarding_balance") or "").strip()
    customerTermsAndCondtions = (frappe.form_dict.get("customer_terms") or "").strip()

    billingAddress = {
        "Line1": (frappe.form_dict.get("customer_billing_address_line1") or "").strip(),
        "Line2": (frappe.form_dict.get("customer_billing_address_line2") or "").strip(),
        "PostalCode": (frappe.form_dict.get("customer_billing_postal_code") or "").strip(),
        "City": (frappe.form_dict.get("customer_billing_city") or "").strip(),
        "Country": (frappe.form_dict.get("customer_billing_country") or "").strip(),
        "State": (frappe.form_dict.get("customer_billing_state") or "").strip(),
        "County": (frappe.form_dict.get("customer_billing_county") or "").strip()
    }


    shippingAddress = {
        "Line1": (frappe.form_dict.get("customer_shipping_address_line1") or "").strip(),
        "Line2": (frappe.form_dict.get("customer_shipping_address_line2") or "").strip(),
        "PostalCode": (frappe.form_dict.get("customer_shipping_postal_code") or "").strip(),
        "City": (frappe.form_dict.get("customer_shipping_city") or "").strip(),
        "Country": (frappe.form_dict.get("customer_shipping_country") or "").strip(),
        "State": (frappe.form_dict.get("customer_shipping_state") or "").strip()
    }

    try:
        customer = frappe.get_doc("Customer", {"custom_id": custom_id})
        if not customer:
            send_response(status="fail", message="Customer not found", status_code=400, http_status=400)
            return

        updated_fields = {}
        field_mapping = {
            "customer_name": customer_name,
            "mobile_no": mobile_no,
            "email_id": email_id,
            "customer_type": customerType,
            "default_currency": customerCurrency,
            "custom_account_number": customerAccountNo,
            "custom_onboard_balance": customerOnboardingBalance,
            "custom_billing_adress_line_1": billingAddress["Line1"],
            "custom_billing_adress_line_2": billingAddress["Line2"],
            "custom_billing_adress_posta_code": billingAddress["PostalCode"],
            "custom_billing_adress_city": billingAddress["City"],
            "custom_billing_adress_country": billingAddress["Country"],
            "custom_billing_adress_state": billingAddress["State"],
            "custom_billing_adress_county": billingAddress["County"],
            "custom_shipping_address_line_1_": shippingAddress["Line1"],
            "custom_shipping_address_line_2_": shippingAddress["Line2"],
            "custom_shipping_address_posta_code_": shippingAddress["PostalCode"],
            "custom_shipping_address_city": shippingAddress["City"],
            "custom_shipping_address_state": shippingAddress["State"],
            "custom_shipping_address_country": shippingAddress["Country"],
            "custom_tc": customerTermsAndCondtions
        }

        for key, value in field_mapping.items():
            if value: 
                setattr(customer, key, value)
                updated_fields[key] = value

        if not updated_fields:
            send_response(
                status="fail",
                message="No valid fields provided to update.",
                status_code=400,
                http_status=400
            )
            return

        customer.save()
        frappe.db.commit()

        send_response(
            status="success",
            message="Customer updated successfully",
            status_code=200,
            http_status=200
        )

    except frappe.DoesNotExistError:
        send_response(status="fail", message="Customer not found", status_code=400, http_status=400)

    except Exception as e:
        return {
            "status": "error",
            "message": _("Failed to update customer: {0}").format(str(e)),
            "data": None,
            "status_code": 500
        }


@frappe.whitelist(allow_guest=False)
def delete_customer_by_tpin(tpin):
    if not tpin:
        send_response(status="fail", message="Customer tpin is required", status_code=400, http_status=400)
    try:
        customer = frappe.get_doc("Customer", {"tax_id": tpin})
        customer.delete()
        frappe.db.commit()

        send_response(status="success", message="Customer with TPIN deleted successfully", status_code=204,http_status=204)

    except frappe.DoesNotExistError:
        send_response(status="fail", message="Customer not found", status_code=404, http_status=404)
    except Exception as e:
        send_response(status="error", message=f"Failed to retrieve customers: {str(e)}", status_code=500, data=None, http_status=500)
        return
