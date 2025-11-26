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
            send_response(
                status="fail",
                message="Required quantity must be a valid number",
                status_code=400,
                http_status=400
            )
            return

        if not item_code:
            send_response(
                status="fail",
                message="Item code is required",
                status_code=400,
                http_status=400
            )
            return

        if required_qty <= 0:
            send_response(
                status="fail",
                message="Required quantity must be greater than 0",
                status_code=400,
                http_status=400
            )
            return

        bin_doc = frappe.get_value(
            "Bin",
            {"item_code": item_code, "warehouse": warehouse},
            ["actual_qty", "reserved_qty"],
            as_dict=True
        )

        if not bin_doc:
            send_response(
                status="fail",
                message=f"Item {item_code} not found in warehouse {warehouse}",
                status_code=404,
                http_status=404
            )
            return

        available_qty = bin_doc["actual_qty"] - bin_doc["reserved_qty"]
        print(f"Available stock for {item_code}: {available_qty}, Required: {required_qty}")

        if available_qty >= required_qty:
            return {"status": "success", "available_qty": available_qty}, 200
        else:
            needed_qty = required_qty - available_qty
            send_response(
                status="fail",
                message =f"Not enough stock: {available_qty} available, {required_qty} required. You need {needed_qty} more.",
                status_code=400,
                http_status=400
            )
            return
        
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



    
    
