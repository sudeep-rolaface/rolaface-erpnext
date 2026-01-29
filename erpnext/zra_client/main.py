from erpnext.zra_client.generic_api import send_response
import os
import subprocess
import threading
import time
from urllib.parse import quote
from frappe import throw, _
from datetime import datetime
from datetime import date
import requests
import frappe
import json
from pathlib import Path



ZRA_LOCAL_BASE_URL = "http://127.0.0.1:8080/sandboxvsdc1.0.8.0/"
ZRA_GET_PRINCIPAL = "/trnsSales/selectPrincipals"
ZRA_CREATE_ITEM = "/items/saveItem"
ZRA_SAVE_STOCK_URL = "/stock/saveStockItems"
ZRA_UPDATE_ITEM = "/items/updateItem"
ZRA_SAVE_STOCK_MASTER = "/stockMaster/saveStockMaster"
ZRA_SAVE_PURCHASE = "/trnsPurchase/savePurchase"
ZRA_CREATE_CUSTOMER = "/branches/saveBrancheCustomers"
ZRA_SALE = "/trnsSales/saveSales"
UPDATE_IMPORT = "/imports/updateImportItems"
SAVE_ITEM_COMPOSITION = "/items/saveItemComposition"
INTERNAL_URL = "http://0.0.0.0:7000/"
CURRENT_SITE = "erpnext.localhost"
BRANCH_CODE = "000"
TPIN = "2484778002"
ORIGIN_SCD_ID = "SDC0010002709"
COMPANY_NAME = "IZYANE INOVSOLUTIONS LIMITED"
COMPANY_PHONE_NO = "+260 777 123456"
COMPANY_EMAIL = "info@izyane.com"
SET_USER = "Administrator"

class ZRAClient:
    def __init__(self):
        self.base_url = ZRA_LOCAL_BASE_URL
        self.internal_base_url = INTERNAL_URL 
        self.create_item_url  = f"{self.base_url}{ZRA_CREATE_ITEM}" 
        self.update_url = f"{self.base_url}{ZRA_UPDATE_ITEM}"
        self.save_stock_url = f"{self.base_url}{ZRA_SAVE_STOCK_URL}"
        self.save_stock_master_url = f"{self.base_url}{ZRA_SAVE_STOCK_MASTER}"
        self.save_purchase_url = f"{self.base_url}{ZRA_SAVE_PURCHASE}"
        self.sale_url = f"{self.base_url}{ZRA_SALE}"
        self.create_customer_url = f"{self.base_url}{ZRA_CREATE_CUSTOMER}"
        self.update_import_url = f"{self.base_url}{UPDATE_IMPORT}"
        self.save_item_composition_url = f"{self.base_url}{SAVE_ITEM_COMPOSITION}"
        self.get_principal_url = f"{self.base_url}{ZRA_GET_PRINCIPAL}"
        self.tpin = TPIN
        self.branch_code = BRANCH_CODE
        self.org_sdc_id = ORIGIN_SCD_ID
        self.site_url = CURRENT_SITE
        self.company_name = COMPANY_NAME
        self.company_phone_number = COMPANY_PHONE_NO
        self.company_email = COMPANY_EMAIL
        self.admin_user = SET_USER
        

    def get_tpin(self):
        return self.tpin
    
    def get_current_user(self):
        return self.admin_user
    
    def get_current_site(self):
        return self.site_url

    def get_origin_sdc_id(self):
        return self.org_sdc_id

    def get_company_name(self):
        return self.company_name

    def get_company_phone_no(self):
        return self.company_phone_number
    
    def get_company_email(self):
        return self.company_email

    def todays_date(self):
        today = date.today()
        return today.strftime("%Y-%m-%d")

    def get_branch_code(self):
        return self.branch_code

    def get_site_url(self):
        return self.site_url

    def create_item_stock_zra_client(self, payload):
        response = requests.post(url=self.save_stock_url, json=payload, timeout=300)
        response.raise_for_status()
        return response
    
    def create_item_zra_client(self, payload):    
        response = requests.post(url=self.create_item_url, json=payload, timeout=300)
        response.raise_for_status() 
        return response 
    
    def create_customer(self, payload):
        response = requests.post(self.create_customer_url, json=payload, timeout=300)
        response.raise_for_status() 
        return response
    
    def update_item_zra_client(self, payload):
        response = requests.post(self.update_url, json=payload, timeout=300)
        response.raise_for_status()
        return response

    def create_sale_zra_client(self, payload):
        response = requests.post(self.sale_url, json=payload, timeout=300)
        response.raise_for_status()
        return response

    def update_stock_zra_client(self, payload):
        response = requests.post(url= self.save_stock_url, json=payload, timeout=300)
        response.raise_for_status()
        return response.json()

    def save_stock_master_zra_client(self, payload):
        response = requests.post(url=self.save_stock_master_url, json=payload, timeout=300)
        response.raise_for_status()
        return response.json()
    
    def get_next_sales_invoice_name(self):
        from datetime import datetime
        year = datetime.now().year
        prefix = "ACC-SINV"
        
        invoices = frappe.db.get_all(
            "Sales Invoice",
            filters={"name": ["like", f"{prefix}-{year}-%"]},
            fields=["name"]
        )
    
        numbers = []
        for inv in invoices:
            try:
                number = int(inv["name"].split("-")[-1])
                numbers.append(number)
            except ValueError:
                continue
    
        next_number = max(numbers) + 1 if numbers else 1
        next_number_str = str(next_number).zfill(5)
        
        return f"{prefix}-{year}-{next_number_str}"


    def run_stock_update_in_background(self, update_stock_payload, update_stock_master_items, created_by):
        print("Started background updates")
        def background_task():
            try:
                response = self.update_stock_zra_client(update_stock_payload)
                if response.get("resultCd") == "000":
                    print("Stock updated.")
                    response = self.save_stock_master_zra_client(update_stock_master_items)
                    if response.get("resultCd") == "000":
                        print("Stock master updated")
                    else:
                        print("Failed to update stock master:", response)
                else:
                    print(f"Failed to update stock: {response.get('resultMsg')}")
            except Exception as e:
                print(f"Exception in background stock update task: {e}")

        thread = threading.Thread(target=background_task)
        thread.daemon = True  
        thread.start()
        

    def update_sales_rcptno_by_inv_no(self, sales_inv_no, rcptNo, site="erpnext.localhost"):
        def worker():
            site_to_use = "erpnext.localhost" 

            try:
                frappe.init(site=site_to_use)
                frappe.connect()
                frappe.set_user("Administrator")

                print(f"Waiting 40 seconds before updating Sales Invoice '{sales_inv_no}'...")
                time.sleep(40) 

                sales_list = frappe.get_all("Sales Invoice", filters={"name": sales_inv_no}, limit=1)
                if not sales_list:
                    print(f"No Sales Invoice found with code '{sales_inv_no}'.")
                    return

                item_doc = frappe.get_doc("Sales Invoice", sales_list[0].name)
                item_doc.custom_rcptno = rcptNo
                item_doc.flags.ignore_validate_update_after_submit = True
                item_doc.save(ignore_permissions=True)
                frappe.db.commit()

                print(f"Sales Invoice '{sales_inv_no}' custom_rcptno updated to '{rcptNo}'.")
            except Exception as e:
                print(f" Error updating Sales Invoice '{sales_inv_no}': {e}")
            finally:
                frappe.destroy()

        threading.Thread(target=worker, daemon=False).start()
        
    def get_sales_rcptno_by_inv_no(self, sales_inv_no, site="erpnext.localhost"):
        try:
            frappe.init(site=site)
            frappe.connect()
            frappe.set_user("Administrator")

            invoice_doc = frappe.get_doc("Sales Invoice", sales_inv_no)
            print("Invoice :", invoice_doc, "RecptNo :", invoice_doc.custom_rcptno)
            return invoice_doc.custom_rcptno
        except Exception as e:
            print(f"Error fetching Sales Invoice '{sales_inv_no}': {e}")
            send_response(
                status="fail",
                message=f"Error fetching Sales Invoice '{sales_inv_no}': {e}",
                status_code=404,
                http_status=404
            )
    def get_sales_rcptno_by_inv_no_c(self, invoice_no):
        if not invoice_no:
            return None

        invoice_no = str(invoice_no).strip()
        query = """
            SELECT `custom_rcptno`
            FROM `tabSales Invoice`
            WHERE `name` = %s
            LIMIT 1
        """
        result = frappe.db.sql(query, (invoice_no,), as_dict=True)
        print(f"[DEBUG] SQL result: {result}") 

        if result and result[0].get("custom_rcptno"):
            rcpt_no = result[0]["custom_rcptno"]
            print(f"[INFO] Found receipt number '{rcpt_no}' for invoice '{invoice_no}'")
            return rcpt_no

        print(f"[WARN] No receipt number found for invoice '{invoice_no}'")
        return None
    

    def check_stock(self, item_code, required_qty):
        warehouse = "Finished Goods - Izyane"

        try:
            required_qty = float(required_qty)
        except (TypeError, ValueError):
            return {
                "status": "fail",
                "message": "Required quantity must be a valid number"
            }, 400

        if not item_code:
            return {
                "status": "fail",
                "message": "Item code is required"
            }, 400

        if required_qty <= 0:
            return {
                "status": "fail",
                "message": "Required quantity must be greater than 0"
            }, 400

        if not frappe.db.exists("Item", {"name": item_code, "disabled": 0}):
            return {
                "status": "fail",
                "message": f"Item {item_code} does not exist or is disabled"
            }, 404

        if not frappe.db.exists("Warehouse", warehouse):
            return {
                "status": "fail",
                "message": f"Warehouse {warehouse} does not exist"
            }, 404

        bin_doc = frappe.db.get_value(
            "Bin",
            {"item_code": item_code, "warehouse": warehouse},
            ["actual_qty", "reserved_qty"],
            as_dict=True
        )

        if not bin_doc:
            return {
                "status": "fail",
                "message": f"Item {item_code} is not stocked in warehouse {warehouse}. Please create stock for this item before proceeding."
            }, 404

        available_qty = (bin_doc.actual_qty or 0) - (bin_doc.reserved_qty or 0)

        if available_qty < required_qty:
            return {
                "status": "fail",
                "message": (
                    f"Not enough stock. "
                    f"{available_qty} available, {required_qty} required."
                ),
                "data": {
                    "item_code": item_code,
                    "warehouse": warehouse,
                    "available_qty": available_qty,
                    "required_qty": required_qty
                }
            }, 400

        return {
            "status": "success",
            "message": "Sufficient stock available",
            "data": {
                "item_code": item_code,
                "warehouse": warehouse,
                "available_qty": available_qty,
                "required_qty": required_qty
            }
        }, 200

        
    def canItemStockBeUpdate(self, item_code):
        if not item_code:
            return False

        items = frappe.get_all(
            "Item",
            filters={"item_code": item_code},
            fields=["custom_itemtycd"],
            limit_page_length=1
        )

        print("Checking item :", items)
        if not items:
            return False

        item_type = items[0].get("custom_itemtycd")

        try:
            item_type = int(item_type)  
        except (ValueError, TypeError):
            return False

        return item_type in (1, 2)

    
    def get_customer_details(self, customer_id):
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
            frappe.log_error(frappe.get_traceback(), "Get Customer Details API Error")
            return send_response(
                status="fail",
                message=f"Error retrieving customer: {str(e)}",
                status_code=500,
                http_status=500
            )

    def get_item_details(self, item_code):
        if not item_code:
            return send_response(
                status="fail",
                message="Item code is required.",
                status_code=400,
                http_status=400
            )
        
        try:
            item = frappe.get_doc("Item", item_code)
        except frappe.DoesNotExistError:
            return send_response(
                status="fail",
                message="Item not found",
                status_code=404,
                http_status=404
            )
        except Exception as e:
            return send_response(
                status="fail",
                message=f"Cannot proceed: {str(e)}",
                status_code=400,
                http_status=400
            )
        
        itemName = item.item_name
        itemClassCd = getattr(item, "custom_itemclscd", None)
        itemPackingUnitCd = getattr(item, "custom_pkgunitcd", None)
        itemUnitCd = getattr(item, "stock_uom", None)
        itemVatCd = getattr(item, "custom_vatcd", None)
        itemIplCd = getattr(item, "custom_iplcd", None)
        itemTlCd = getattr(item, "custom_tlcd", None)

        return {
            "itemName": itemName,
            "itemClassCd": itemClassCd,
            "itemPackingUnitCd": itemPackingUnitCd,
            "itemUnitCd": itemUnitCd,
            "itemVatCd": itemVatCd,
            "itemIplCd": itemIplCd,
            "itemTlCd": itemTlCd
        }
        
    def get_sales_item_codes(sales_invoice_no=None, item_code=None):
        if not sales_invoice_no:
            return send_response(
                status="fail",
                message="Sales Invoice number is required.",
                status_code=400,
                http_status=400
            )

        if not item_code:
            return send_response(
                status="fail",
                message="Item code is required.",
                status_code=400,
                http_status=400
            )

        try:
            invoice = frappe.get_doc("Sales Invoice", sales_invoice_no)
            for item in invoice.items:
                if item.item_code == item_code:
                    data = {
                        "vatCd": item.custom_vatcd or "",
                        "iplCd": item.custom_iplcd or "",
                        "tlCd": item.custom_tlcd or ""
                    }
                    print("**** item codes", data)

                    return data

            return send_response(
                status="fail",
                message=f"Item '{item_code}' not found in Sales Invoice '{sales_invoice_no}'.",
                status_code=404,
                http_status=404
            )

        except frappe.DoesNotExistError:
            return send_response(
                status="fail",
                message=f"Sales Invoice '{sales_invoice_no}' does not exist.",
                status_code=404,
                http_status=404
            )

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "get_sales_item_codes Error")

            return send_response(
                status="fail",
                message=f"Unexpected error: {str(e)}",
                status_code=500,
                http_status=500
            )
    def getTaxCategory(self):
        VALID_TAX_CATEGORY =  ["Non-Export", "Export", "LPO"]
        return VALID_TAX_CATEGORY
    
    
    def AllowedInvoiceStatuses(self):
        ALLOWED_STATUSES = ["Draft", "Sent", "Paid", "Overdue"]
        return ALLOWED_STATUSES
    
    
    def GetTopLevelCostCenter(self, company):
        parent = frappe.db.get_value("Cost Center", {"company": company, "is_group": 1})
        if parent:
            return parent
        doc = frappe.get_doc({
            "doctype": "Cost Center",
            "cost_center_name": f"{company} Cost Center Group",
            "company": company,
            "is_group": 1
        })
        try:
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            parent = frappe.db.get_value("Cost Center", {"company": company, "is_group": 1})
            return parent
        return doc.name


    def getCurrentCompany(self):
        COMPANY = "Izyane"
        return COMPANY


    def GetOrCreateCostCenter(self, doctype, name):
        print("CALLS: ", doctype, name)
        if not name:
            return None
        existing = frappe.db.exists(doctype, name)
        if existing:
            print("exists", existing)
            return existing

        company = self.getCurrentCompany()
        parent = self.GetTopLevelCostCenter(company)

        doc = frappe.get_doc({
            "doctype": "Cost Center",
            "cost_center_name": name,
            "company": company,
            "parent_cost_center": parent,
            "is_group": 0
        })
        try:
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            existing = frappe.db.exists(doctype, name)
            return existing
        return doc.name
    
    
    def GetOrCreateLink(self, doctype, name):
        if not name:
            return None
        existing = frappe.db.exists(doctype, name)
        if existing:
            return existing
        doc = frappe.get_doc({"doctype": doctype, "name": name})
        try:
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            existing = frappe.db.exists(doctype, name)
            return existing
        return doc.nam
    

    def GetOrCreateProject(self, project_name):
        if not project_name:
            return None

        existing = frappe.db.get_value("Project", {"project_name": project_name}, "name")
        if existing:
            return existing

        doc = frappe.get_doc({
            "doctype": "Project",
            "project_name": project_name,
            "company": self.getCurrentCompany()
        })
        try:
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            existing = frappe.db.get_value("Project", {"project_name": project_name}, "name")
            return existing
        except frappe.UniqueValidationError:
            existing = frappe.db.get_value("Project", {"project_name": project_name}, "name")
            return existing

        return doc.name
    
    
    
    def GetOrCreateParentExpenseAccount(self):
        """Ensure a top-level 'Expenses' account exists, create if missing"""
        company = self.getCurrentCompany()
        parent = frappe.db.get_value("Account", {"company": company, "account_name": "Expenses", "is_group": 1})
        if parent:
            return parent

        # Create top-level Expenses account
        doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": "Expenses",
            "account_type": "Expense Account",
            "company": company,
            "is_group": 1
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc.name

    def GetOrCreateExpenseAccount(self):
        """Return or create default Shipping Expense Account"""
        company = self.getCurrentCompany()
        account = frappe.db.get_value("Account", {"company": company, "account_name": "Shipping Expense"}, "name")
        if account:
            return account

        parent = self.GetOrCreateParentExpenseAccount()

        doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": "Shipping Expense",
            "account_type": "Expense Account",  # Correct type
            "company": company,
            "parent_account": parent,
            "is_group": 0
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc.name

    def GetOrCreateShippingRule(self, shipping_rule_name, cost_center_name, account=None):
        print(shipping_rule_name, cost_center_name)
        if not shipping_rule_name:
            return None

        # Ensure we have a valid cost center
        if not cost_center_name:
            frappe.throw("Cost Center is required for Shipping Rule")

        if not account:
            account = self.GetOrCreateExpenseAccount()

        # Check if already exists
        existing = frappe.db.get_value("Shipping Rule", {"label": shipping_rule_name}, "name")
        if existing:
            return existing

        doc = frappe.get_doc({
            "doctype": "Shipping Rule",
            "label": shipping_rule_name,
            "cost_center": cost_center_name,  # must be db 'name'
            "account": account,
            "company": self.getCurrentCompany()
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc.name



    
    

        
        
