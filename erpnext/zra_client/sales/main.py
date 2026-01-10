import time
import json
import random
import asyncio
import frappe
import requests
import threading
from frappe.utils import flt
from datetime import datetime
from erpnext.zra_client.main import ZRAClient

now = datetime.now()

class zraSales(ZRAClient):
    def __init__(self):
        super().__init__()

    def get_tpin(self):
        return self.tpin

    def get_branch(self):
        return self.branch_code


    def get_org_sdc_id(self):
        return self.org_sdc_id
    
    def call_create_normal_sale_client(self, payload):
        return self.normal_sale(payload)
    
    def call_create_credit_note_sale_client(self, payload):
        return self.sale_credit_note(payload)

    def update_stock_after_purchase(self, payload):
        return self.update_stock_after_purchase_view(payload)

    def update_stock_master_after_purchase(self, payload):
        return self.save_stock_master(payload)
    

    def update_rcptNo_delayed(self, docname, rcpt_no, delay=10):
        def worker():
            try:
                print(f"⏳ Received rcptNo: {rcpt_no}. Waiting {delay} seconds before updating...")
                time.sleep(delay)

                url = "http://0.0.0.0:7000/api/update_rcpt/" 
                payload = {
                    "docname": docname,
                    "rcpt_no": rcpt_no
                }
                headers = {'Content-Type': 'application/json'}
                response = requests.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    print(f"rcptNo '{rcpt_no}' updated for {docname} via API")
                else:
                    print(f"Failed to update rcptNo via API: {response.text}")

            except Exception as e:
                print(f" Error calling API to update rcptNo: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def create_sale_normal(self, sell_order):
        print("Creating sale for order:", sell_order)
        customer_name = sell_order.get("customer") or sell_order.get("customer_name") or ""
        customer_doc = frappe.get_doc("Customer", customer_name)
        customer_tpin = customer_doc.get("custom_customer_tpin")
        cisInvcNo = f'CIS{sell_order.get("name", "001")}-{random.randint(1000, 9999)}'
        created_by = sell_order.get("owner") or "system"
        currency = sell_order.get("currency") or "ZMW"
        totals = {'taxable': 0.0, 'vat': 0.0, 'discount': 0.0, 'gross': 0.0, 'net': 0.0}
        item_list = []

        for i, item in enumerate(sell_order.get("items", []), 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)
            qty = flt(item.get("qty", 1))
            price = flt(item_doc.get("custom_default_unit_price", 0))
            gross = flt(qty * price, 4)
            bins = frappe.db.get_all("Bin", filters={"item_code": item_code}, fields=["actual_qty"])
            available_qty = sum(flt(b.get("actual_qty", 0)) for b in bins)

            # if qty > available_qty:
            #     frappe.throw(
            #         f"Insufficient stock for item <b>{item_code}</b>: Ordered: {qty}, Available: {available_qty}"
            #     )

            discount_pct = flt(item.get("discount_percentage", 0))
            discount_amt = flt(gross * discount_pct / 100, 4)
            net = flt(gross - discount_amt, 4)
            taxable = flt(net / 1.16, 4)
            vat = flt(taxable * 0.16, 4)

            totals['gross'] += gross
            totals['discount'] += discount_amt
            totals['net'] += net
            totals['taxable'] += taxable
            totals['vat'] += vat

            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": "50102518",
                "itemNm": item.get("item_name"),
                "bcd": item_doc.get("custom_origin_place_code", ""),
                "pkgUnitCd": "WRAP",
                "pkg": 1,
                "qtyUnitCd": "EA",
                "qty": qty,
                "prc": flt(price, 4),
                "splyAmt": gross,
                "dcRt": discount_pct,
                "dcAmt": discount_amt,
                "vatCatCd": "A",
                "vatTaxblAmt": taxable,
                "vatAmt": vat,
                "totAmt": flt(taxable + vat, 4),
                "exciseTxCatCd": "",
                "tlCatCd": "",
                "iplCatCd": "",
                "exciseTaxblAmt": 0.0,
                "tlTaxblAmt": 0.0,
                "iplTaxblAmt": 0.0,
                "iplAmt": 0.0,
                "tlAmt": 0.0,
                "exciseTxAmt": 0.0
            })

        cash_discount_rate = flt(25.0, 4)
        cash_discount_amt = flt(totals['net'] * cash_discount_rate / 100, 4)
        final_amount = flt(totals['net'] - cash_discount_amt, 4)

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "orgSdcId": "SDC0010002709",
            "cisInvcNo": cisInvcNo,
            "orgInvcNo": 0,
            "Customer":  customer_name,
            "custTpin":  customer_tpin ,
            "salesTyCd": "N",
            "rcptTyCd": "S",
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": now.strftime("%Y%m%d%H%M%S"),
            "salesDt": now.strftime("%Y%m%d"),
            "totItemCnt": len(item_list),
            "taxblAmtA": totals['taxable'],
            "taxblAmtB": 0.0,
            "taxblAmtC1": 0.0,
            "taxblAmtC2": 0.0,
            "taxblAmtC3": 0.0,
            "taxblAmtD": 0.0,
            "taxblAmtRvat": 0.0,
            "taxblAmtE": 0.0,
            "taxblAmtF": 0.0,
            "taxblAmtIpl1": 0.0,
            "taxblAmtIpl2": 0.0,
            "taxblAmtTl": 0.0,
            "taxblAmtEcm": 0.0,
            "taxblAmtExeeg": 0.0,
            "taxblAmtTot": 0.0,
            "taxRtA": 16,
            "taxRtB": 16,
            "taxRtC1": 0,
            "taxRtC2": 0,
            "taxRtC3": 0,
            "taxRtD": 0,
            "tlAmt": 0.0,
            "taxRtRvat": 16,
            "taxRtE": 0,
            "taxRtF": 10,
            "taxRtIpl1": 5,
            "taxRtIpl2": 0,
            "taxRtTl": 1.5,
            "taxRtEcm": 5,
            "taxRtExeeg": 3,
            "taxRtTot": 0,
            "taxAmtA": totals['vat'],
            "taxAmtB": 0.0,
            "taxAmtC1": 0.0,
            "taxAmtC2": 0.0,
            "taxAmtC3": 0.0,
            "taxAmtD": 0.0,
            "taxAmtRvat": 0.0,
            "taxAmtE": 0.0,
            "taxAmtF": 0.0,
            "taxAmtIpl1": 0.0,
            "taxAmtIpl2": 0.0,
            "taxAmtTl": 0.0,
            "taxAmtEcm": 0.0,
            "taxAmtExeeg": 0.0,
            "taxAmtTot": 0.0,
            "totTaxblAmt": totals['taxable'],
            "totTaxAmt": totals['vat'],
            "totAmt": final_amount,
            "cashDcRt": cash_discount_rate,
            "cashDcAmt": cash_discount_amt,
            "prchrAcptcYn": "N",
            "remark": "",
            "regrId": created_by,
            "regrNm": created_by,
            "modrId": created_by,
            "modrNm": created_by,
            "saleCtyCd": "1",
            "currencyTyCd": currency,
            "exchangeRt": "1",
            "destnCountryCd": "",
            "dbtRsnCd": "",
            "invcAdjustReason": "",
            "itemList": item_list
        }
        toUseData = payload
        print("Preparing sale data:", payload)
        response = self.call_create_normal_sale_client(payload)

        if response.get("resultCd") == "000":
            get_rcpt_no = response.get("data", {}).get("rcptNo")
            print(" Stock master updated successfully after sale.")
            doc_name = sell_order.get("name")
            self.update_rcptNo_delayed(docname=doc_name, rcpt_no=get_rcpt_no)

            print("This prints immediately, before delayed print")
            ocrnDt = datetime.now().strftime("%Y%m%d")
            itemsListInToUseData = toUseData.get("itemList", [])

            update_stock_items = []
            update_stock_master_items = []

            for item in itemsListInToUseData:
                update_stock_items.append({
                    "itemSeq": item.get("itemSeq"),
                    "itemCd": item.get("itemCd"),
                    "itemClsCd": item.get("itemClsCd"),
                    "itemNm": item.get("itemNm"),
                    "pkgUnitCd": item.get("pkgUnitCd"),
                    "qtyUnitCd": item.get("qtyUnitCd"),
                    "qty": item.get("qty"),
                    "prc": item.get("prc"),
                    "splyAmt": item.get("splyAmt"),
                    "taxblAmt": item.get("vatTaxblAmt"),  
                    "vatCatCd": item.get("vatCatCd"),
                    "taxAmt": item.get("vatAmt"),         
                    "totAmt": item.get("totAmt"),
                    "pkg": 1,
                    "totDcAmt": 0,
                })
                update_stock_master_items.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": 12 
                })

            update_stock_payload = {
                "tpin": self.tpin,
                "bhfId": self.branch_code,
                "sarNo": 1,
                "orgSarNo": 0,
                "regTyCd": "M",
                "sarTyCd": "02",
                "ocrnDt": ocrnDt,
                "totItemCnt": toUseData['totItemCnt'],
                "totTaxblAmt": toUseData['totTaxblAmt'],
                "totTaxAmt": toUseData['totTaxAmt'],
                "totAmt": toUseData['totAmt'],
                "regrId": created_by,
                "regrNm": created_by,
                "modrNm": created_by,
                "modrId": created_by,
                "itemList": update_stock_items
            }

            print(" Preparing stock update data:", update_stock_payload)

            response = call_update_stock_after_purchase = self.update_stock_after_purchase(update_stock_payload)
            if response.get("resultCd") == "000":
                print(" Stock updated successfully after sale.")

                create_update_stock_master_payload = {
                                "tpin": self.tpin,
                                "bhfId": self.branch_code,
                                "regrId": created_by,
                                "regrNm": created_by,
                                "modrNm": created_by,
                                "modrId": created_by,
                                "stockItemList":update_stock_master_items 

                                }

                print(" Preparing stock master update data:", create_update_stock_master_payload)
                response = call_update_stock_master_after_purchase = self.update_stock_master_after_purchase(create_update_stock_master_payload)
         
            frappe.msgprint(f"Sale made successfully: {response.get('resultMsg')}")
        else:
            frappe.throw(f"Purchase save failed: {response.get('resultMsg')}")



    def create_credit_note_sale(self, cancel_data):
        print("Sale cancelled", cancel_data)
        rcpt_no = cancel_data.get("name")
        cisInvcNo = f'CIS{rcpt_no}-{random.randint(1000, 9999)}'
        customer_name = cancel_data.get("customer") or cancel_data.get("customer_name") or ""
        customer_doc = frappe.get_doc("Customer", customer_name)
        customer_tpin = customer_doc.get("custom_customer_tpin") or ""

        created_by = cancel_data.get("owner") or "system"
        currency = cancel_data.get("currency") or "ZMW"
        cfmDt = datetime.now().strftime("%Y%m%d%H%M%S")
        salesDt = datetime.now().strftime('%Y%m%d')

        get_name = cancel_data.get("name")

        if not get_name:
            frappe.throw("Sale cancellation failed: 'name' field is required in cancel_data.")

        try:

            response = requests.get("http://0.0.0.0:7000/api/get-rcpt-no/", params={"docname": get_name})

            response.raise_for_status() 

            data = response.json()
            orgInvcNo = data.get("rcpNo")

            if not orgInvcNo:
                frappe.throw("Sale cancellation failed: 'orgInvcNo' not found in response.")

        except Exception as e: 
            frappe.throw(f"Sale cancellation failed: {str(e)}")
        item_list = []
        totals = {"net": 0.0, "vat": 0.0, "taxable": 0.0}

        # Process each item in cancel_data items
        for idx, item in enumerate(cancel_data.get("items", []), start=1):
            price = flt(item.get("rate") or 0)
            quantity = flt(item.get("qty") or 1)
            net_amount = flt(price * quantity, 4)
            taxable_amount = net_amount
            vat_amount = flt(taxable_amount * 0.16, 4)

            totals["net"] += net_amount
            totals["taxable"] += taxable_amount
            totals["vat"] += vat_amount

            item_list.append({
                "itemSeq": idx,
                "itemCd": item.get("item_code") or "",
                "itemClsCd": "A",
                "itemNm": item.get("item_name") or "",
                "bcd": "",
                "pkgUnitCd": "EA",
                "pkg": 1,
                "qtyUnitCd": "EA",
                "qty": quantity,
                "prc": price,
                "splyAmt": taxable_amount,
                "dcRt": 0,
                "dcAmt": 0,
                "taxblAmt": taxable_amount,
                "taxTyCd": "A",
                "taxAmt": vat_amount,
                "totAmt": flt(taxable_amount + vat_amount, 4),
                "remark": ""
            })

        # Calculate cash discount only if applicable
        raw_total = flt(totals["taxable"] + totals["vat"], 4)
        if raw_total > 0:
            cash_discount_rate = 25.0
            cash_discount_amt = flt(raw_total * cash_discount_rate / 100, 4)
        else:
            cash_discount_rate = 0.0
            cash_discount_amt = 0.0

        final_amount = flt(raw_total - cash_discount_amt, 4)

        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.get_branch(),
            "orgSdcId": self.get_org_sdc_id(),
            "orgInvcNo": orgInvcNo,
            "cisInvcNo": cisInvcNo,
            "Customer": customer_name,
            "custTpin": customer_tpin,
            "salesTyCd": "N",
            "rcptTyCd": "R",
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": cfmDt,
            "salesDt": salesDt,
            "rfdRsnCd": "01",
            "totItemCnt": len(item_list),
            "taxblAmtA": flt(totals["taxable"], 4),
            "taxRtA": 16,
            "taxAmtA": flt(totals["vat"], 4),
            "totTaxblAmt": flt(totals["taxable"], 4),
            "totTaxAmt": flt(totals["vat"], 4),
            "cashDcRt": cash_discount_rate,
            "cashDcAmt": cash_discount_amt,
            "totAmt": final_amount,
            "prchrAcptcYn": "N",
            "remark": "",
            "regrId": created_by,
            "regrNm": created_by,
            "modrId": created_by,
            "modrNm": created_by,
            "saleCtyCd": "1",
            "currencyTyCd": currency,
            "exchangeRt": "1",
            "destnCountryCd": "",
            "dbtRsnCd": "",
            "invcAdjustReason": "",
            "itemList": item_list
        }

        print(" SENDING PAYLOAD:", payload)
        response = self.call_create_credit_note_sale_client(payload)
        return response





		