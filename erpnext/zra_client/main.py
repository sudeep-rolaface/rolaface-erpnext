import threading
import time
from urllib.parse import quote
from frappe import throw, _
from datetime import datetime
from datetime import date
import requests
import frappe
import json




ZRA_LOCAL_BASE_URL = "http://41.60.191.7:4000/sandboxvsdc1.0.8.0/"
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

    def get_tpin(self):
        return self.tpin

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


    
    
