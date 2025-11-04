from erpnext.zra_client.generic_api import send_response
from erpnext.zra_client.main import ZRAClient
import frappe
from frappe import _

ZRA_CLIENT_INSTANCE = ZRAClient()

@frappe.whitelist(allow_guest=False)
def create_customer_api():
    tpin = frappe.form_dict.get("custom_customer_tpin")
    customer_name = (frappe.form_dict.get("customer_name") or "").strip()
    email_id = (frappe.form_dict.get("email_id") or "").strip()
    mobile_no = (frappe.form_dict.get("mobile_no") or "").strip()
    

    if not tpin:
        send_response(status="error", message="TPIN is required (custom_customer_tpin)", status_code = 400,  http_status=400)
        return
    
    if not customer_name:
        send_response(status="fail", message="Customer name is required(customer_name)", status_code=400, http_status=400)
        return
    if not mobile_no:
        send_response(status="fail", message="Customer mobile number is required (mobile_no)", status_code=400, http_status=400)


    existing_customer = frappe.db.get_value(
        "Customer", {"tax_id": tpin}, ["name", "customer_name", "email_id", "mobile_no"]
    )
    if existing_customer:
        send_response(status="error", message=f"A customer with TPIN {tpin} already exists.", status_code = 400, http_status=400)
        return

    try:
        payload = {
            "tpin": ZRA_CLIENT_INSTANCE.get_tpin(),
            "bhfId": ZRA_CLIENT_INSTANCE.get_branch_code(),
            "custNo": mobile_no,
            "custTpin": tpin,
            "custNm":customer_name,
            "useYn": "Y",
            "regrNm": frappe.session.user,
            "regrId": frappe.session.user,
            }

        result = ZRA_CLIENT_INSTANCE.create_customer(payload)
        print(result)
        data = result.json()
        if data.get("resultCd") != "000":
            send_response(status="error", message=result.get("resultMsg", "Customer Sync Failed"), status_code = 400, data=None, http_status=400)
            return

        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": customer_name,
            "tax_id": tpin,
            "email_id": email_id,
            "mobile_no": mobile_no
        })
        customer.insert()
        frappe.db.commit()
        customer.reload()

        data = {
            "name": customer.name,
            "customer_name": customer.customer_name,
            "mobile_no": customer.mobile_no
        }

        send_response(status="success", message="Customer created successfully.", status_code = 201, data=data, http_status=200)
        return

    except Exception as e:
        send_response(status="error", message=f"API call failed: {str(e)}", data=None, http_status=500)
        return
    

@frappe.whitelist(allow_guest=False)
def get_all_customers_api():
    try:
        customers = frappe.get_all(
            "Customer",
            fields=["name", "customer_name", "tax_id", "mobile_no"],
            order_by="customer_name asc"
        )
        if not customers:
            send_response(status="success", message="No customers found.", status_code=200, data=[], http_status=200)
            return

        send_response(status="success", message="Customers retrieved successfully", status_code=200, data=customers, http_status=200)
        return

    except Exception as e:
        send_response(status="error", message=f"Failed to retrieve customers: {str(e)}", status_code=500, data=None, http_status=500)
        return


@frappe.whitelist(allow_guest=False)
def get_customer_by_tpin(tpin):
    try:
        customer = frappe.get_doc("Customer", {"tax_id": tpin})
        data = {
            "name": customer.name,
            "tpin": customer.tax_id,
            "customer_name": customer.customer_name,
            "mobile_no": customer.mobile_no
        }

        send_response(status="success", message="Customer retrieved successfully", status_code=200, data=data ,http_status=200)

    except frappe.DoesNotExistError:
        send_response(status="fail", message="Customer not found", status_code=404, http_status=404)
    except Exception as e:
        send_response(status="error", message=f"Failed to retrieve customers: {str(e)}", status_code=500, data=None, http_status=500)
        return


@frappe.whitelist(allow_guest=False)
def update_customer_by_tpin(**kwargs):
    ALLOWED_FIELDS = ["customer_name", "customer_group", "mobile_no"]

    tpin = kwargs.get("customer_tpin")
    if not tpin:
        send_response(status="fail", message="Customer tpin is required (customer_tpin)", status_code=400, http_status=400)
        return
    try:
        customer = frappe.get_doc("Customer", {"tax_id": tpin})

        if not customer:
            send_response(status="fail", message="Customer not found", status_code=400, http_status=400)
            return

        updated_fields = {}
        for key, value in kwargs.items():
            if key in ALLOWED_FIELDS:
                setattr(customer, key, value)
                updated_fields[key] = value

        if not updated_fields:
            send_response(status="fail", message="The only required updated fields are mobile number (mobile_no) and  customer name (customer_name)")

        customer.save()
        frappe.db.commit()

        send_response(status="success", message="Customer updated successfully", status_code=204, http_status=204)
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
