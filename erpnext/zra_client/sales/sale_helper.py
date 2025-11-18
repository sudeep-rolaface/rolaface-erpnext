import random
from erpnext.zra_client.generic_api import send_response
from erpnext.zra_client.receipt.build import BuildPdf
from erpnext.zra_client.main import ZRAClient
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import requests
import uuid
import frappe
import json
import os


class NormaSale(ZRAClient):
    def __init__(self):
        self.taxbl_totals = {key: 0.0 for key in self.TAX_RATES}
        self.tax_amt_totals = {key: 0.0 for key in self.TAX_RATES}
        super().__init__()
        
    def reset_totals(self):
        for key in self.TAX_RATES:
            self.taxbl_totals[key] = 0.0
            self.tax_amt_totals[key] = 0.0
        print("[INFO] Tax totals and amounts have been reset to zero.")


    def create_normal_sale_helper(self, payload):
        return self.create_sale_zra_client(payload)

    TAX_RATES = {
        "A": 16, "B": 16, "C1": 0, "C2": 0, "C3": 0,
        "D": 0, "E": 0, "F": 10,
        "Ipl1": 5, "Ipl2": 0,
        "Tl": 1.5,
        "ECM": 5,
        "EXEEG": 3,
        "RVAT": 16
    }


    @staticmethod
    def format_tax_amount(value):
        return float(Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))

    def generate_cis_invc_no(self):
        no = f"CIS{random.randint(1, 999):03d}-{random.randint(1000, 9999)}"
        print(f"[INFO] Generated invoice no: {no}")
        return no

    def calculate_tax_for_item(self, item):
        qty = float(item.get("qty", 0))
        price_tax_inclusive = float(item.get("prc", 0))
        discount_rate = 0.0

        vat_cat = item.get("VatCd")
        ipl_cat = item.get("IplCd")
        tl_cat = item.get("TlCd")
        excise_cat = item.get("ExciseCd")


        print(f"\n[CALCULATE TAX] {item['itemNm']} (qty={qty}, price={price_tax_inclusive}, "
              f"vatCatCd={vat_cat}, iplCatCd={ipl_cat}, tlCatCd={tl_cat}, exciseTxCatCd={excise_cat})")

        supply_amount = round(qty * price_tax_inclusive, 2)
        discount_amount = round(supply_amount * (discount_rate / 100), 2)

        vat_rate = self.TAX_RATES.get(vat_cat, 0) / 100 if vat_cat else 0
        ipl_rate = self.TAX_RATES["Ipl1"] / 100 if ipl_cat == "IPL1" else self.TAX_RATES["Ipl2"] / 100 if ipl_cat == "IPL2" else 0
        tl_rate = self.TAX_RATES["Tl"] / 100 if tl_cat == "TL" else 0
        ecm_rate = self.TAX_RATES["ECM"] / 100 if excise_cat == "ECM" else 0

        combined_rate_excl_ecm = vat_rate + ipl_rate + tl_rate
        base_amount = round(supply_amount / (1 + combined_rate_excl_ecm), 2) if combined_rate_excl_ecm > 0 else supply_amount

        vat_tax = round(base_amount * vat_rate, 2)
        ipl_tax = round(base_amount * ipl_rate, 2)
        tl_tax = round(base_amount * tl_rate, 2)

        ecm_taxable_amount = 0.0
        ecm_tax = 0.0

        ipl_taxable_amt = base_amount if ipl_rate > 0 else (supply_amount if ipl_cat == "IPL2" else 0.0)

        return {
            "splyAmt": supply_amount,
            "dcRt": discount_rate,
            "dcAmt": discount_amount,
            "vatTaxblAmt": base_amount if vat_cat else 0.0,
            "vatAmt": vat_tax,
            "iplTaxblAmt": ipl_taxable_amt,
            "iplAmt": ipl_tax,
            "tlTaxblAmt": base_amount if tl_rate > 0 else 0.0,
            "tlAmt": tl_tax,
            "ecmTaxblAmt": ecm_taxable_amount,
            "ecmAmt": ecm_tax,
            "totAmt": supply_amount
        }

    def build_payload(self, items, base_data):
        print("\n[BUILD PAYLOAD] Processing items...")
        processed_items = []

        for idx, item in enumerate(items):
            tax_result = self.calculate_tax_for_item(item)

            vat_cat = item.get("VatCd")
            ipl_cat = item.get("IplCd")
            tl_cat = item.get("TlCd")
            excise_cat = item.get("ExciseCd")

            if vat_cat in self.TAX_RATES:
                self.taxbl_totals[vat_cat] += tax_result["vatTaxblAmt"]
                self.tax_amt_totals[vat_cat] += tax_result["vatAmt"]

            if ipl_cat == "IPL1":
                self.taxbl_totals["Ipl1"] += tax_result["iplTaxblAmt"]
                self.tax_amt_totals["Ipl1"] += tax_result["iplAmt"]
            elif ipl_cat == "IPL2":
                self.taxbl_totals["Ipl2"] += tax_result["iplTaxblAmt"]

            if tl_cat == "TL":
                self.taxbl_totals["Tl"] += tax_result["tlTaxblAmt"]
                self.tax_amt_totals["Tl"] += tax_result["tlAmt"]

            if excise_cat == "ECM":
                ecm_taxbl_amt = 150.0
                ecm_tax_amt = round(ecm_taxbl_amt * (self.TAX_RATES["ECM"] / 100), 2)
                self.taxbl_totals["ECM"] += ecm_taxbl_amt
                self.tax_amt_totals["ECM"] += ecm_tax_amt
            else:
                ecm_taxbl_amt = 0.0
                ecm_tax_amt = 0.0

            processed_item = {
                "itemSeq": idx + 1,
                "itemCd": item["itemCd"],
                "itemClsCd": item["itemClsCd"],
                "itemNm": item["itemNm"],
                "qty": float(item.get("qty", 0)),
                "prc": float(item.get("prc", 0)),
                "rrp": round(float(item.get("prc", 0)), 2),
                **tax_result,
                "vatCatCd": vat_cat or "",
                "iplCatCd": ipl_cat or "",
                "tlCatCd": tl_cat or "",
                "pkgUnitCd": item.get("pkgUnitCd", "BA"),
                "pkg": float(item.get("pkg", 1.0)),
                "qtyUnitCd": item.get("qtyUnitCd", "BE"),
                "bcd": item.get("bcd", ""),
                "isrccCd": item.get("isrccCd", ""),
                "isrccNm": item.get("isrccNm", ""),
                "isrcRt": float(item.get("isrcRt", 0.0)),
                "isrcAmt": float(item.get("isrcAmt", 0.0)),
                "ecmTaxblAmt": ecm_taxbl_amt,
                "ecmAmt": ecm_tax_amt,
                "totAmt": round(tax_result["splyAmt"] + ecm_tax_amt, 2)
            }

            processed_items.append(processed_item)

        total_taxable_amount = round(sum(
            item.get("vatTaxblAmt", 0.0)
            + item.get("iplTaxblAmt", 0.0)
            + item.get("tlTaxblAmt", 0.0)
            + item.get("ecmTaxblAmt", 0.0)
            for item in processed_items
        ), 2)

        total_tax_amount = round(sum(
            item["vatAmt"] + item["iplAmt"] + item["tlAmt"] + item["ecmAmt"]
            for item in processed_items
        ), 2)
        total_amount = round(sum(item["totAmt"] for item in processed_items), 2)        
        lpoNumber = base_data.get("lpoNumber")
        get_principal_id = base_data.get("principalId")
        exchangeRt = base_data.get("exchangeRt")
        currencyCd = base_data.get("currencyCd")
        destnCountryCd = base_data.get("destnCountryCd")
        invoiceName = base_data.get("name")

        logged_in_user = "Admin"
        username = "Admin"

        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.get_branch_code(),
            "orgInvcNo": 0,
            "cisInvcNo":  str(uuid.uuid4()),
            "custTpin": base_data["cust_tpin"],
            "custNm": base_data["cust_name"],
            "salesTyCd": "N",
            "rcptTyCd": "S",
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": datetime.now().strftime("%Y%m%d%H%M%S"),
            "salesDt": datetime.now().strftime("%Y%m%d"),
            "totItemCnt": len(items),
            **self.generate_tax_fields(),
            "totTaxblAmt": total_taxable_amount,
            "totTaxAmt": self.format_tax_amount(total_tax_amount),
            "cashDcRt": 0,
            "cashDcAmt": 0.0,
            "totAmt": total_amount,
            "prchrAcptcYn": "N",
            "remark": "",
            "regrId": username,
            "regrNm": username,
            "modrId": username,
            "modrNm": username,
            "saleCtyCd": "1",
            "dbtRsnCd": "",
            "invcAdjustReason": "",
            "itemList": processed_items
        }
        if destnCountryCd:
            payload["destnCountryCd"] = destnCountryCd

        if lpoNumber:
            payload["lpoNumber"] = lpoNumber

        if get_principal_id:
            payload["principalId"] = get_principal_id
            
        if exchangeRt:
            payload["exchangeRt"] = exchangeRt
            
        if currencyCd:
            payload["currencyTyCd"] = currencyCd
            
        if destnCountryCd:
            payload["destnCountryCd"] = destnCountryCd
            
        

        self.to_use_data = payload

        print(json.dumps(payload, indent=4))
        return payload

    def generate_tax_fields(self):
        def fix_key(k):
            if k.upper() == "RVAT":
                return "Rvat"
            return k.capitalize()

        taxblAmt = {f"taxblAmt{fix_key(k)}": round(self.taxbl_totals.get(k, 0.0), 2) for k in self.TAX_RATES}
        taxRt = {f"taxRt{fix_key(k)}": self.TAX_RATES.get(k, 0) for k in self.TAX_RATES}
        taxAmt = {f"taxAmt{fix_key(k)}": round(self.tax_amt_totals.get(k, 0.0), 2) for k in self.TAX_RATES}

        return {**taxblAmt, **taxRt, **taxAmt}

    def send_sale_data(self, sell_data):
        customer_name = sell_data.get("customerName")
        name = sell_data.get("name")
        customer_doc = frappe.get_doc("Customer", customer_name)
        customer_tpin = customer_doc.get("customer_tpin")
        destnCountryCd = sell_data.get("destnCountryCd")
        exchangeRt = sell_data.get("exchangeRt")
        is_stock_updated = 1
        created_by = sell_data.get("modified_by")
        currencyCd = sell_data.get("currencyCd")
        lpoNumber = sell_data.get("lpoNumber")
    
        sell_data_item = sell_data.get("items")
        items = []
        for item in sell_data_item:

            
            itemCd = item.get("itemCode")
            packageUnitCode = item.get("packageUnitCode")
            unitOfMeasure = item.get("unitOfMeasure")
            itemClassCd = item.get("itemClassCode")
            getIplCd = item.get("IplCd")
            getTlCd = item.get("TlCd")
            getExciseCd = item.get("ExciseCd")
            getVatCd = item.get("VatCd")
            itemName = item.get("itemName")
            qty = item.get("qty")
            actual_stock = item.get('actual_qty', 0)
            price = item.get("price")
            remaining_stock = 0
            items.append({
                "itemCd": itemCd,
                "packageUnitCode": packageUnitCode,
                "unitOfMeasure": unitOfMeasure,
                "itemClsCd": itemClassCd,
                "IplCd": getIplCd,
                "TlCd": getTlCd,
                "ExciseCd": getExciseCd,
                "VatCd": getVatCd,
                "itemNm": itemName,
                "prc": price,
                "qty": qty
                
            })

            print(items)


        base_data = {
            "cust_name": customer_name,
            "cust_tpin": customer_tpin,
            "name": name,
            "currencyCd": "ZMW",
            "exchangeRt": exchangeRt,
            "created_by": created_by,
            "currencyCd": currencyCd,
            "lpoNumber": lpoNumber,
            "destnCountryCd": destnCountryCd

            
        }


        print("\n[START] Sending sale data...")
        self.reset_totals()
        payload = self.build_payload(items, base_data)
        response = self.create_normal_sale_helper(payload)
        response = response.json()
        apiCallerResponse = response
        print(response)
        print(f"Response from ZRA: {response}")
        
        if response.get("resultCd") == "000":
            rcpt_no = response.get("data", {}).get("rcptNo")
            self.update_sales_rcptno_by_inv_no(name, rcpt_no, 1)

            additionInfoToBeSaved = []
            additionInfoToBeSaved.extend([
                payload["currencyTyCd"],
                payload["exchangeRt"],
                payload["totTaxAmt"]
            ])
            additionInfoToBeSavedItem = []
            for item in payload["itemList"]:
                additionInfoToBeSavedItem.append({
                    "itemCd": item["itemCd"],
                    "vatTaxblAmt": item["vatTaxblAmt"],
                })

            
            company_info = []
            company_info.append((
                self.get_company_name(),
                self.get_company_phone_no(),
                self.get_company_email(),
                self.get_tpin(),
            ))

        
            customer_info = []
            customer_info.append((
                "2484778086",
                payload["custNm"]
            ))

            get_qrcode_url = response.get("data", {}).get("qrCodeUrl") 
            invoice = []
            invoice.append((
                base_data["name"],
                self.todays_date(),
                "TAX INVOICE",
                get_qrcode_url
                
            ))
            sdc_data = []
            sdc_data.append((
                self.todays_date(),
                self.get_origin_sdc_id(),
            ))

            pdf_items = payload["itemList"]
            print(customer_info, company_info, invoice, pdf_items)
            created_by = sell_data.get("owner")
            ocrnDt = datetime.now().strftime("%Y%m%d")
            pdf_items = payload["itemList"]
            print(customer_info, company_info, invoice, pdf_items)
            pdf_generator = BuildPdf()
            pdf_generator.build_invoice(company_info, customer_info, invoice, pdf_items, sdc_data, payload)
            if is_stock_updated == 1:
                print("Updating stock items...")

                update_stock_items = []
                update_stock_master_items = []                    
                    
                for item in self.to_use_data.get("itemList", []):
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
                        "pkg": item.get("pkg", 1),
                        "totDcAmt": item.get("dcAmt", 0),
                    })

        
                    update_stock_master_items.append({
                        "itemCd": item.get("itemCd"),
                        "rsdQty": remaining_stock 
                    })


                update_stock_payload = {
                    "tpin": self.tpin,
                    "bhfId": self.branch_code,
                    "sarNo": 1,
                    "orgSarNo": 0,
                    "regTyCd": "M",
                    "sarTyCd": "11",
                    "ocrnDt": ocrnDt,
                    "totItemCnt": self.to_use_data['totItemCnt'],
                    "totTaxblAmt": self.to_use_data['totTaxblAmt'],
                    "totTaxAmt": self.to_use_data['totTaxAmt'],
                    "totAmt": self.to_use_data['totAmt'],
                    "regrId": self.to_use_data["regrId"],
                    "regrNm": self.to_use_data["regrId"],
                    "modrNm": self.to_use_data["regrId"],
                    "modrId": self.to_use_data["regrId"],
                    "itemList": update_stock_items
                }

                update_stock_master_payload = {
                    "tpin": self.tpin,
                    "bhfId": self.get_branch_code(),
                    "regrId": self.to_use_data["regrId"],
                    "regrNm": self.to_use_data["regrId"],
                    "modrNm": self.to_use_data["regrId"],
                    "modrId": self.to_use_data["regrId"],
                    "stockItemList": update_stock_master_items 
                    }

                print(update_stock_payload, update_stock_master_items)
                self.run_stock_update_in_background(update_stock_payload, update_stock_master_payload, created_by)

                response_status = response.get("resultCd")
                if  response_status == "000":
                    response_message = response.get("resultMsg")
                    print("Response returned 1")
                    return {
                        "resultCd": response_status,
                        "resultMsg": response_message,
                        "additionalInfo": additionInfoToBeSaved,
                        "additionInfoToBeSavedItem": additionInfoToBeSavedItem 
                    }
                    
                else:
                    return {
                        "resultCd": response_status,
                        "resultMsg": response_message,
                    }
                    

            else:
                send_response(
                    status="fail",
                    message=f"ZRA API Error: {response.get('resultMsg', 'Unknown error')}",
                    status_code=400,
                    http_status=400
                )
                return
        print("Response returned 2")
        return response

            


class CreditNote(ZRAClient):

        def __init__(self):
            self.taxbl_totals = {key: 0.0 for key in self.TAX_RATES}
            self.tax_amt_totals = {key: 0.0 for key in self.TAX_RATES}
            super().__init__()

        def create_normal_sale_helper(self, payload):
            return self.create_sale_zra_client(payload)

        TAX_RATES = {
            "A": 16, "B": 16, "C1": 0, "C2": 0, "C3": 0,
            "D": 0, "E": 0, "F": 10,
            "Ipl1": 5, "Ipl2": 0,
            "Tl": 1.5,
            "ECM": 5,
            "EXEEG": 3,
            "RVAT": 16
        }


        @staticmethod
        def format_tax_amount(value):
            return float(Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))

        def generate_cis_invc_no(self):
            no = f"CIS{random.randint(1, 999):03d}-{random.randint(1000, 9999)}"
            print(f"[INFO] Generated invoice no: {no}")
            return no

        def calculate_tax_for_item(self, item):
            qty = float(item.get("qty", 0))
            price_tax_inclusive = float(item.get("prc", 0))
            discount_rate = 0.0

            vat_cat = item.get("vatCatCd")
            ipl_cat = item.get("iplCatCd")
            tl_cat = item.get("tlCatCd")
            excise_cat = item.get("exciseTxCatCd")

            print(f"\n[CALCULATE TAX] {item['itemNm']} (qty={qty}, price={price_tax_inclusive}, "
                f"vatCatCd={vat_cat}, iplCatCd={ipl_cat}, tlCatCd={tl_cat}, exciseTxCatCd={excise_cat})")

            supply_amount = round(qty * price_tax_inclusive, 2)
            discount_amount = round(supply_amount * (discount_rate / 100), 2)

            vat_rate = self.TAX_RATES.get(vat_cat, 0) / 100 if vat_cat else 0
            ipl_rate = self.TAX_RATES["Ipl1"] / 100 if ipl_cat == "IPL1" else self.TAX_RATES["Ipl2"] / 100 if ipl_cat == "IPL2" else 0
            tl_rate = self.TAX_RATES["Tl"] / 100 if tl_cat == "TL" else 0
            ecm_rate = self.TAX_RATES["ECM"] / 100 if excise_cat == "ECM" else 0

            combined_rate_excl_ecm = vat_rate + ipl_rate + tl_rate
            base_amount = round(supply_amount / (1 + combined_rate_excl_ecm), 2) if combined_rate_excl_ecm > 0 else supply_amount

            vat_tax = round(base_amount * vat_rate, 2)
            ipl_tax = round(base_amount * ipl_rate, 2)
            tl_tax = round(base_amount * tl_rate, 2)

            ecm_taxable_amount = 0.0
            ecm_tax = 0.0

            ipl_taxable_amt = base_amount if ipl_rate > 0 else (supply_amount if ipl_cat == "IPL2" else 0.0)

            return {
                "splyAmt": supply_amount,
                "dcRt": discount_rate,
                "dcAmt": discount_amount,
                "vatTaxblAmt": base_amount if vat_cat else 0.0,
                "vatAmt": vat_tax,
                "iplTaxblAmt": ipl_taxable_amt,
                "iplAmt": ipl_tax,
                "tlTaxblAmt": base_amount if tl_rate > 0 else 0.0,
                "tlAmt": tl_tax,
                "ecmTaxblAmt": ecm_taxable_amount,
                "ecmAmt": ecm_tax,
                "totAmt": supply_amount
            }

        def build_payload(self, items, base_data):
            print("\n[BUILD PAYLOAD] Processing items...")
            processed_items = []

            for idx, item in enumerate(items):
                tax_result = self.calculate_tax_for_item(item)

                vat_cat = item.get("vatCatCd")
                ipl_cat = item.get("iplCatCd")
                tl_cat = item.get("tlCatCd")
                excise_cat = item.get("exciseTxCatCd")

                if vat_cat in self.TAX_RATES:
                    self.taxbl_totals[vat_cat] += tax_result["vatTaxblAmt"]
                    self.tax_amt_totals[vat_cat] += tax_result["vatAmt"]

                if ipl_cat == "IPL1":
                    self.taxbl_totals["Ipl1"] += tax_result["iplTaxblAmt"]
                    self.tax_amt_totals["Ipl1"] += tax_result["iplAmt"]
                elif ipl_cat == "IPL2":
                    self.taxbl_totals["Ipl2"] += tax_result["iplTaxblAmt"]

                if tl_cat == "TL":
                    self.taxbl_totals["Tl"] += tax_result["tlTaxblAmt"]
                    self.tax_amt_totals["Tl"] += tax_result["tlAmt"]

                if excise_cat == "ECM":
                    ecm_taxbl_amt = 150.0
                    ecm_tax_amt = round(ecm_taxbl_amt * (self.TAX_RATES["ECM"] / 100), 2)
                    self.taxbl_totals["ECM"] += ecm_taxbl_amt
                    self.tax_amt_totals["ECM"] += ecm_tax_amt
                else:
                    ecm_taxbl_amt = 0.0
                    ecm_tax_amt = 0.0

                processed_item = {
                    "itemSeq": idx + 1,
                    "itemCd": item["itemCd"],
                    "itemClsCd": item["itemClsCd"],
                    "itemNm": item["itemNm"],
                    "qty": float(item.get("qty", 0)),
                    "prc": float(item.get("prc", 0)),
                    "rrp": round(float(item.get("prc", 0)), 2),
                    **tax_result,
                    "vatCatCd": vat_cat or "",
                    "iplCatCd": ipl_cat or "",
                    "tlCatCd": tl_cat or "",
                    "pkgUnitCd": item.get("pkgUnitCd", "BA"),
                    "pkg": float(item.get("pkg", 1.0)),
                    "qtyUnitCd": item.get("qtyUnitCd", "BE"),
                    "bcd": item.get("bcd", ""),
                    "isrccCd": item.get("isrccCd", ""),
                    "isrccNm": item.get("isrccNm", ""),
                    "isrcRt": float(item.get("isrcRt", 0.0)),
                    "isrcAmt": float(item.get("isrcAmt", 0.0)),
                    "ecmTaxblAmt": ecm_taxbl_amt,
                    "ecmAmt": ecm_tax_amt,
                    "totAmt": round(tax_result["splyAmt"] + ecm_tax_amt, 2)
                }

                processed_items.append(processed_item)

            total_taxable_amount = sum(self.taxbl_totals.values())
            total_tax_amount = sum(self.tax_amt_totals.values())
            total_amount = round(total_taxable_amount + total_tax_amount, 2)
            original_invoice_no = base_data["original_sell"]

            orgInvcNo = self.fetch_original_invoice(original_invoice_no)

            export_destination_country_code = base_data.get("export_destination_code")
            if export_destination_country_code is not None:
                destnCountryCd = export_destination_country_code
            else:
                destnCountryCd = None
            
            get_lpoNumber = base_data.get("lpoNumber")
            logged_in_user = "Admin"
            username = "Admin"


            payload = {
                "tpin": self.get_tpin(),
                "bhfId": self.get_branch_code(),
                "orgInvcNo":  orgInvcNo,
                "orgSdcId": "SDC0010002709",
                "cisInvcNo": base_data["name"],
                "custTpin": base_data["cust_tpin"],
                "custNm": base_data["cust_name"],
                "salesTyCd": "N",
                "rcptTyCd": "R",
                "pmtTyCd": "01",
                "salesSttsCd": "02",
                "cfmDt": datetime.now().strftime("%Y%m%d%H%M%S"),
                "salesDt": datetime.now().strftime("%Y%m%d"),
                "totItemCnt": len(items),
                **self.generate_tax_fields(),
                "totTaxblAmt": total_taxable_amount,
                "totTaxAmt": self.format_tax_amount(total_tax_amount),
                "cashDcRt": 0,
                "cashDcAmt": 0.0,
                "totAmt": total_amount,
                "prchrAcptcYn": "N",
                "remark": "",
                "regrId": username,
                "regrNm": username,
                "modrId": username,
                "modrNm": username,
                "saleCtyCd": "1",
                "lpoNumber": None,
                "currencyTyCd": base_data["currencyCd"],
                "exchangeRt": base_data["exchangeRt"],
                "dbtRsnCd": "",
                "rfdRsnCd": "01",
                "invcAdjustReason": "",
                "itemList": processed_items
            }
            if destnCountryCd:
                payload["destnCountryCd"] = destnCountryCd

            print("Checkin for LOP: ", get_lpoNumber)
            if get_lpoNumber:
                payload["lpoNumber"] = get_lpoNumber
            self.to_use_data = payload

            print(json.dumps(payload, indent=4))
            return payload

        def generate_tax_fields(self):
            return {
                f"taxblAmt{k}": round(self.taxbl_totals.get(k, 0.0), 2)
                for k in self.TAX_RATES
            } | {
                f"taxRt{k}": self.TAX_RATES.get(k, 0)
                for k in self.TAX_RATES
            } | {
                f"taxAmt{k}": round(self.tax_amt_totals.get(k, 0.0), 2)
                for k in self.TAX_RATES
            }
        
        def send_credit_sale_data(self, sell_data):
            print(sell_data)
            name = sell_data.get("name")
            customer_name = sell_data.get("customer") or sell_data.get("customer_name") or ""
            customer_doc = frappe.get_doc("Customer", customer_name)
            customer_tpin = customer_doc.get("custom_tpin") or ""
            original_sell = sell_data.get("return_against")
            export_destination_country = sell_data.get("custom_destination_country")
            lpo_number = sell_data.get("custom_lpo_number")
            is_lpo_transactions = sell_data.get("custom__lpo_transaction")
            is_export = sell_data.get("custom_export")
            currency = sell_data.get("custom_sale_currency_")
            exchangeRt = sell_data.get("custom_rate")
            created_by = sell_data.get("modified_by")
            is_stock_update = sell_data.get("update_stock")


            

            if export_destination_country == "ASCENSION ISLAND":
                export_destination_country = " "


            currencies = [
                {"code": "ZMW", "name": "Zambian kwacha"},
                {"code": "USD", "name": "United States Dollar"},
                {"code": "ZAR", "name": "South African Rand"},
                {"code": "GBP", "name": "Pound Sterling"},
                {"code": "CNY", "name": "Chinese Yuan"},
                {"code": "EUR", "name": "Euro"},
            ]

            currency_dict = {currency["name"]: currency["code"] for currency in currencies}
    
            currencyCd = None
            if currency in currency_dict:
                currencyCd = currency_dict[currency]
            else:
                frappe.throw(f"Currency name '{currency}' not found.")

            if exchangeRt is None:
                frappe.throw(f"Exchange rate for Currency name '{currency}' not found.")


            sell_data_item = sell_data.get("items")
            items = []
            for item in sell_data_item:

                itemCd = item.get("item_code")
                item_doc = frappe.get_doc("Item", itemCd)
                formatted_items = item_doc.as_dict()
                item_price = sell_data['items'][0]['rate']
                package_unit_code = formatted_items.get("custom_packaging_unit_code")
                unit_of_measure = formatted_items.get("custom_units_of_measure")
                item_class_name = formatted_items.get("custom_item_class_code")
                get_ipl_name = item.get("custom_ipl")
                get_tl_name = item.get("custom_tl")
                get_excise_name = item.get("custom_excise")
                get_turn_over_tax = item.get("custom_tot")
                get_vat_name = "A"
                item_price = sell_data['items'][0]['rate']
                itemName = item.get("item_name")
                warehouses = item.get("warehouse") 

                tlCat = {
                "TL":"Tourism Levy",
                "F": "Service Charge 10%"
                }

                
                iplCat = {

                    "IPL1":"Insurance Premium Levy",
                    "IPL2": "Re-Insurance"
                }

                vat_tax_types = {
                    "A": "Standard Rated 16%",
                    "B": "Minimum Taxable Value (MTV)",
                    "C1": "Exports 0%",               
                    "RVAT": "RVAT Reverse VAT",           
                    "C2": "Local Purchases Order",
                    "C3": "Zero-rated by nature",
                    "D": "Exempt No tax charge",
                    "E": "Disbursement",
                }
                vatCd = next((key for key, value in vat_tax_types.items() if value == get_vat_name), None)
                iplCd = next((key for key, value in iplCat.items() if value == get_ipl_name), None)
                tlCd = next((key for key, value in tlCat.items() if value == get_tl_name), None)

                present_codes = [code for code in [vatCd, iplCd, tlCd] if code is not None]
                if len(present_codes) != 1:
                    frappe.throw("Exactly one of vatCd, iplCd, or tlCd must be present. Found: {}".format(len(present_codes)))

                
                qty = abs((item.get("qty", 0)))
                current_qty = self.get_current_item_stock_qty(itemCd, warehouses)
                now_available_qty =  current_qty + qty

                print(f"available Qty for {itemCd} in {warehouses}: {current_qty }, Now available Qty: {now_available_qty}")

                items.append({
                    "itemCd": itemCd,
                    "itemClsCd": self.get_classification_code(item_class_name),         
                    "itemNm": itemName,
                    "qty": qty,
                    "prc": item_price,
                    "pkgUnitCd": self.get_packaging_unit(package_unit_code),
                    "qtyUnitCd": self.get_units_of_measure(unit_of_measure),                
                    "vatCatCd": vatCd,                
                    "iplCatCd": iplCd ,
                    "tlCatCd": tlCd,
                    "exciseTxCatCd": None
                })

            base_data = {
                "name": name,
                "cust_name": customer_name,
                "cust_tpin": customer_tpin,
                "original_sell": original_sell,
                "currencyCd": currencyCd,
                "exchangeRt": exchangeRt,
                "created_by": created_by
            }
            if is_export == 1 or vatCd == "C1":
                self.validate_export(vatCd, export_destination_country, is_export)

                if export_destination_country == "N / A":
                    frappe.throw("Destination country is required. Please select a valid country.")

                destination_country_code = self.get_country_code_by_name(export_destination_country)
                base_data["export_destination_code"] = destination_country_code 


            if iplCd is not None and (vatCd is not None or tlCd is not None):
                frappe.throw(
                    f"[ZRA Error] IPL transactions (iplCd) must not be combined with VAT or TL. Found: vatCd={vatCd}, tlCd={tlCd}"
                )
            
            if is_lpo_transactions == 1:
                if vatCd != "C2":
                    frappe.throw("Only VAT Code 'C2' is allowed for LPO transactions.")
                if not lpo_number:
                    frappe.throw("LPO Number is required when VAT Code is 'C2' for LPO transactions.")
                if len(lpo_number) < 9 or len(lpo_number) > 20:
                    frappe.throw("LPO Number length must be between 9 and 20 characters.")
                base_data["lpoNumber"] = lpo_number

            if vatCd == "C2" and not is_lpo_transactions:
                frappe.throw("For VAT Code 'C2', LPO transaction must be checked.")

            print("\n[START] Sending sale data...")
            payload = self.build_payload(items, base_data)
            response = self.create_normal_sale_helper(payload)
            response = response.json()

            if response.get("resultCd") == "000":

                company_info = []
                company_info.append((
                    self.get_company_name(),
                    self.get_company_phone_no(),
                    self.get_company_email(),
                    self.get_tpin()
                ))

            
                customer_info = []
                customer_info.append((
                    payload["custTpin"],
                    payload["custNm"]
                ))

                get_qrcode_url = response.get("data", {}).get("qrCodeUrl") 
                invoice = []
                invoice.append((
                    payload["cisInvcNo"],
                    self.todays_date(),
                    "CREDIT NOTE",
                    get_qrcode_url
                    
                ))
                sdc_data = []
                sdc_data.append((
                    self.todays_date(),
                    self.get_origin_sdc_id(),
                                    

                ))

                pdf_items = payload["itemList"]
                print(customer_info, company_info, invoice, pdf_items)
                # BuildPdf().build_invoice(company_info, customer_info, invoice, pdf_items,  sdc_data, payload)
                # get_rcpt_no = response.get("data", {}).get("rcptNo")
                # get_qrcode_url = response.get("data", {}).get("qrCodeUrl") 
                # print("Stock master updated successfully after sale.")
                # doc_name = sell_data.get("name")
                # self.update_rcptNo_delayed(docname=doc_name, rcpt_no=get_rcpt_no)
                # created_by = sell_data.get("owner")

                print("This prints immediately, before delayed print")
                ocrnDt = datetime.now().strftime("%Y%m%d")
                print(self.to_use_data)

                if is_stock_update == 1:
                    print("Updating stock items...")
                    update_stock_items = []
                    update_stock_master_items = []

                        
                        
                    for item in self.to_use_data.get("itemList", []):
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
                            "pkg": item.get("pkg", 1),
                            "totDcAmt": item.get("dcAmt", 0),
                        })

                        update_stock_master_items.append({
                            "itemCd": item.get("itemCd"),
                            "rsdQty": now_available_qty
                        })


                    update_stock_payload = {
                        "tpin": self.tpin,
                        "bhfId": self.branch_code,
                        "sarNo": 1,
                        "orgSarNo": 0,
                        "regTyCd": "M",
                        "sarTyCd": "03",
                        "ocrnDt": ocrnDt,
                        "totItemCnt": self.to_use_data['totItemCnt'],
                        "totTaxblAmt": self.to_use_data['totTaxblAmt'],
                        "totTaxAmt": self.to_use_data['totTaxAmt'],
                        "totAmt": self.to_use_data['totAmt'],
                        "regrId": self.to_use_data["regrId"],
                        "regrNm": self.to_use_data["regrId"],
                        "modrNm": self.to_use_data["regrId"],
                        "modrId": self.to_use_data["regrId"],
                        "itemList": update_stock_items
                    }

                    update_stock_master_payload = {
                        "tpin": self.tpin,
                        "bhfId": self.get_branch_code(),
                        "regrId": self.to_use_data["regrId"],
                        "regrNm": self.to_use_data["regrId"],
                        "modrNm": self.to_use_data["regrId"],
                        "modrId": self.to_use_data["regrId"],
                        "stockItemList": update_stock_master_items 
                        }
                    


            #         print(update_stock_payload, update_stock_master_items)
            #         self.run_stock_update_in_background(update_stock_payload, update_stock_master_payload, created_by)
            # else:
            #     result_cd = response.get("resultCd")
            #     RequestException(result_cd or "SALE_ERROR").throw()



class DebitNote(ZRAClient):
            def __init__(self):
                self.taxbl_totals = {key: 0.0 for key in self.TAX_RATES}
                self.tax_amt_totals = {key: 0.0 for key in self.TAX_RATES}
                super().__init__()

            def create_normal_sale_helper(self, payload):
                return self.create_sale_zra_client(payload)

            TAX_RATES = {
                "A": 16, "B": 16, "C1": 0, "C2": 0, "C3": 0,
                "D": 0, "E": 0, "F": 10,
                "Ipl1": 5, "Ipl2": 0,
                "Tl": 1.5,
                "ECM": 5,
                "EXEEG": 3,
                "RVAT": 16
            }


            @staticmethod
            def format_tax_amount(value):
                return float(Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))

            def generate_cis_invc_no(self):
                no = f"CIS{random.randint(1, 999):03d}-{random.randint(1000, 9999)}"
                print(f"[INFO] Generated invoice no: {no}")
                return no

            def calculate_tax_for_item(self, item):
                qty = float(item.get("qty", 0))
                price_tax_inclusive = float(item.get("prc", 0))
                discount_rate = 0.0

                vat_cat = item.get("vatCatCd")
                ipl_cat = item.get("iplCatCd")
                tl_cat = item.get("tlCatCd")
                excise_cat = item.get("exciseTxCatCd")

                print(f"\n[CALCULATE TAX] {item['itemNm']} (qty={qty}, price={price_tax_inclusive}, "
                    f"vatCatCd={vat_cat}, iplCatCd={ipl_cat}, tlCatCd={tl_cat}, exciseTxCatCd={excise_cat})")

                supply_amount = round(qty * price_tax_inclusive, 2)
                discount_amount = round(supply_amount * (discount_rate / 100), 2)

                vat_rate = self.TAX_RATES.get(vat_cat, 0) / 100 if vat_cat else 0
                ipl_rate = self.TAX_RATES["Ipl1"] / 100 if ipl_cat == "IPL1" else self.TAX_RATES["Ipl2"] / 100 if ipl_cat == "IPL2" else 0
                tl_rate = self.TAX_RATES["Tl"] / 100 if tl_cat == "TL" else 0
                ecm_rate = self.TAX_RATES["ECM"] / 100 if excise_cat == "ECM" else 0

                combined_rate_excl_ecm = vat_rate + ipl_rate + tl_rate
                base_amount = round(supply_amount / (1 + combined_rate_excl_ecm), 2) if combined_rate_excl_ecm > 0 else supply_amount

                vat_tax = round(base_amount * vat_rate, 2)
                ipl_tax = round(base_amount * ipl_rate, 2)
                tl_tax = round(base_amount * tl_rate, 2)

                ecm_taxable_amount = 0.0
                ecm_tax = 0.0

                ipl_taxable_amt = base_amount if ipl_rate > 0 else (supply_amount if ipl_cat == "IPL2" else 0.0)

                return {
                    "splyAmt": supply_amount,
                    "dcRt": discount_rate,
                    "dcAmt": discount_amount,
                    "vatTaxblAmt": base_amount if vat_cat else 0.0,
                    "vatAmt": vat_tax,
                    "iplTaxblAmt": ipl_taxable_amt,
                    "iplAmt": ipl_tax,
                    "tlTaxblAmt": base_amount if tl_rate > 0 else 0.0,
                    "tlAmt": tl_tax,
                    "ecmTaxblAmt": ecm_taxable_amount,
                    "ecmAmt": ecm_tax,
                    "totAmt": supply_amount
                }

            def build_payload(self, items, base_data):
                print("\n[BUILD PAYLOAD] Processing items...")
                processed_items = []

                for idx, item in enumerate(items):
                    tax_result = self.calculate_tax_for_item(item)

                    vat_cat = item.get("vatCatCd")
                    ipl_cat = item.get("iplCatCd")
                    tl_cat = item.get("tlCatCd")
                    excise_cat = item.get("exciseTxCatCd")

                    if vat_cat in self.TAX_RATES:
                        self.taxbl_totals[vat_cat] += tax_result["vatTaxblAmt"]
                        self.tax_amt_totals[vat_cat] += tax_result["vatAmt"]

                    if ipl_cat == "IPL1":
                        self.taxbl_totals["Ipl1"] += tax_result["iplTaxblAmt"]
                        self.tax_amt_totals["Ipl1"] += tax_result["iplAmt"]
                    elif ipl_cat == "IPL2":
                        self.taxbl_totals["Ipl2"] += tax_result["iplTaxblAmt"]

                    if tl_cat == "TL":
                        self.taxbl_totals["Tl"] += tax_result["tlTaxblAmt"]
                        self.tax_amt_totals["Tl"] += tax_result["tlAmt"]

                    if excise_cat == "ECM":
                        ecm_taxbl_amt = 150.0
                        ecm_tax_amt = round(ecm_taxbl_amt * (self.TAX_RATES["ECM"] / 100), 2)
                        self.taxbl_totals["ECM"] += ecm_taxbl_amt
                        self.tax_amt_totals["ECM"] += ecm_tax_amt
                    else:
                        ecm_taxbl_amt = 0.0
                        ecm_tax_amt = 0.0

                    processed_item = {
                        "itemSeq": idx + 1,
                        "itemCd": item["itemCd"],
                        "itemClsCd": item["itemClsCd"],
                        "itemNm": item["itemNm"],
                        "qty": float(item.get("qty", 0)),
                        "prc": float(item.get("prc", 0)),
                        "rrp": round(float(item.get("prc", 0)), 2),
                        **tax_result,
                        "vatCatCd": vat_cat or "",
                        "iplCatCd": ipl_cat or "",
                        "tlCatCd": tl_cat or "",
                        "pkgUnitCd": item.get("pkgUnitCd", "BA"),
                        "pkg": float(item.get("pkg", 1.0)),
                        "qtyUnitCd": item.get("qtyUnitCd", "BE"),
                        "bcd": item.get("bcd", ""),
                        "isrccCd": item.get("isrccCd", ""),
                        "isrccNm": item.get("isrccNm", ""),
                        "isrcRt": float(item.get("isrcRt", 0.0)),
                        "isrcAmt": float(item.get("isrcAmt", 0.0)),
                        "ecmTaxblAmt": ecm_taxbl_amt,
                        "ecmAmt": ecm_tax_amt,
                        "totAmt": round(tax_result["splyAmt"] + ecm_tax_amt, 2)
                    }

                    processed_items.append(processed_item)

                total_taxable_amount = round(sum(
                    item.get("vatTaxblAmt", 0.0)
                    + item.get("iplTaxblAmt", 0.0)
                    + item.get("tlTaxblAmt", 0.0)
                    + item.get("ecmTaxblAmt", 0.0)
                    for item in processed_items
                ), 2)
                total_tax_amount = sum(self.tax_amt_totals.values())
                total_amount = round(total_taxable_amount + total_tax_amount, 2)
                original_invoice_no = base_data["original_sell"]
                try:
                    original_invoice = frappe.get_doc("Sales Invoice", original_invoice_no)
                    orgInvcNo = original_invoice.custom_rcpt_no if hasattr(original_invoice, 'custom_rcpt_no') else None
                    if not orgInvcNo:
                        frappe.throw("Original invoice receipt number not found")
                except Exception as e:
                    frappe.throw(f"Failed to get original invoice: {str(e)}")

                export_destination_country_code = base_data.get("export_destination_code")
                if export_destination_country_code is not None:
                    destnCountryCd = export_destination_country_code
                else:
                    destnCountryCd = None
                
                get_lpoNumber = base_data.get("lpoNumber")
                logged_in_user = self.get_logged_in_details(base_data["created_by"])
                username = logged_in_user['username']

                payload = {
                    "tpin": self.get_tpin(),
                    "bhfId": self.get_branch_code(),
                    "orgInvcNo":  orgInvcNo,
                    "orgSdcId": "SDC0010002709",
                    "cisInvcNo": base_data["name"],
                    "custTpin": base_data["cust_tpin"],
                    "custNm": base_data["cust_name"],
                    "salesTyCd": "N",
                    "rcptTyCd": "D",
                    "pmtTyCd": "01",
                    "salesSttsCd": "02",
                    "cfmDt": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "salesDt": datetime.now().strftime("%Y%m%d"),
                    "totItemCnt": len(items),
                    **self.generate_tax_fields(),
                    "totTaxblAmt": total_taxable_amount,
                    "totTaxAmt": self.format_tax_amount(total_tax_amount),
                    "cashDcRt": 0,
                    "cashDcAmt": 0.0,
                    "totAmt": total_amount,
                    "prchrAcptcYn": "N",
                    "remark": "",
                    "regrId": username,
                    "regrNm": username,
                    "modrId": username,
                    "modrNm": username,
                    "saleCtyCd": "1",
                    "lpoNumber": None,
                    "currencyTyCd": base_data["currencyCd"],
                    "exchangeRt": base_data["exchangeRt"],
                    "dbtRsnCd": "03",
                    "invcAdjustReason": "",
                    "itemList": processed_items
                }
                if destnCountryCd:
                    payload["destnCountryCd"] = destnCountryCd

                print("Checkin for LOP: ", get_lpoNumber)
                if get_lpoNumber:
                    payload["lpoNumber"] = get_lpoNumber
                self.to_use_data = payload

                print(json.dumps(payload, indent=4))
                return payload

            def generate_tax_fields(self):
                return {
                    f"taxblAmt{k}": round(self.taxbl_totals.get(k, 0.0), 2)
                    for k in self.TAX_RATES
                } | {
                    f"taxRt{k}": self.TAX_RATES.get(k, 0)
                    for k in self.TAX_RATES
                } | {
                    f"taxAmt{k}": round(self.tax_amt_totals.get(k, 0.0), 2)
                    for k in self.TAX_RATES
                }
            
            def send_debit_sale_data(self, sell_data):
                name = sell_data.get("name")
                customer_name = sell_data.get("customer") or sell_data.get("customer_name") or ""
                customer_doc = frappe.get_doc("Customer", customer_name)
                customer_tpin = customer_doc.get("custom_tpin") or ""
                original_sell = sell_data.get("return_against")
                export_destination_country = sell_data.get("custom_destination_country")
                lpo_number = sell_data.get("custom_lpo_number")
                is_lpo_transactions = sell_data.get("custom__lpo_transaction")
                is_export = sell_data.get("custom_export")
                currency = sell_data.get("custom_sale_currency_")
                exchangeRt = sell_data.get("custom_rate")
                is_stock_updated = 1
                created_by = sell_data.get("modified_by")
                if export_destination_country == "ASCENSION ISLAND":
                    export_destination_country = " "


                currencies = [
                {"code": "ZMW", "name": "Zambian kwacha"},
                {"code": "USD", "name": "United States Dollar"},
                {"code": "ZAR", "name": "South African Rand"},
                {"code": "GBP", "name": "Pound Sterling"},
                {"code": "CNY", "name": "Chinese Yuan"},
                {"code": "EUR", "name": "Euro"},
                ]

                currency_dict = {currency["name"]: currency["code"] for currency in currencies}
        
                currencyCd = None
                if currency in currency_dict:
                    currencyCd = currency_dict[currency]
                else:
                    frappe.throw(f"Currency name '{currency}' not found.")

                if exchangeRt is None:
                    frappe.throw(f"Exchange rate for Currency name '{currency}' not found.")


                sell_data_item = sell_data.get("items")
                items = []
                for item in sell_data_item:

                    itemCd = item.get("item_code")
                    item_doc = frappe.get_doc("Item", itemCd)
                    formatted_items = item_doc.as_dict()
                    package_unit_code = formatted_items.get("custom_packaging_unit_code")
                    unit_of_measure = formatted_items.get("custom_units_of_measure")
                    item_class_name = formatted_items.get("custom_item_class_code")
                    product_type = formatted_items.get("custom_product_type"),
                    get_ipl_name = item.get("custom_ipl")
                    get_tl_name = item.get("custom_tl")
                    get_excise_name = item.get("custom_excise")
                    get_turn_over_tax = item.get("custom_tot")
                    get_vat_name = item.get("custom_test")
                    item_price = sell_data['items'][0]['rate']



                    if isinstance(product_type, tuple):
                        product_type = product_type[0]
                    if product_type in ["Raw Material", "Finished Product"]:
                        if is_stock_updated != 1:
                            frappe.throw(f"Update Stock must be checked for item {itemName} ({product_type})")

                    elif product_type == "Service":
                        if is_stock_updated == 1:
                            frappe.throw(f"Update Stock must NOT be checked for item {itemName} ({product_type})")
                            
            
                    tlCat = {
                    "TL":"Tourism Levy",
                    "F": "Service Charge 10%"
                    }

                    
                    iplCat = {

                        "IPL1":"Insurance Premium Levy",
                        "IPL2": "Re-Insurance"
                    }

                    
            
                    vat_tax_types = {
                        "A": "Standard Rated 16%",
                        "B": "Minimum Taxable Value (MTV)",
                        "C1": "Exports 0%",               
                        "RVAT": "RVAT Reverse VAT",           
                        "C2": "Local Purchases Order",
                        "C3": "Zero-rated by nature",
                        "D": "Exempt No tax charge",
                        "E": "Disbursement",
                    }
                    vatCd = next((key for key, value in vat_tax_types.items() if value == get_vat_name), None)
                    iplCd = next((key for key, value in iplCat.items() if value == get_ipl_name), None)
                    tlCd = next((key for key, value in tlCat.items() if value == get_tl_name), None)

                    present_codes = [code for code in [vatCd, iplCd, tlCd] if code is not None]
                    if len(present_codes) != 1:
                        frappe.throw("Exactly one of vatCd, iplCd, or tlCd must be present. Found: {}".format(len(present_codes)))

                    print(package_unit_code, unit_of_measure, get_vat_name, vatCd)
                    itemName = item.get("item_name")
                    
                    
                
                    qty = abs((item.get("qty", 0)))
                    actual_stock = item.get('actual_qty', 0)
                    remaining_stock = actual_stock - qty


                    items.append({
                        "itemCd": itemCd,
                        "itemClsCd": self.get_classification_code(item_class_name),         
                        "itemNm": itemName,
                        "qty": qty,
                        "prc": item_price,
                        "pkgUnitCd": self.get_packaging_unit(package_unit_code),
                        "qtyUnitCd": self.get_units_of_measure(unit_of_measure),                
                        "vatCatCd": vatCd,                
                        "iplCatCd": iplCd,
                        "tlCatCd": tlCd,
                        "exciseTxCatCd": None
                    })

                base_data = {
                    "name":name,
                    "cust_name": customer_name,
                    "cust_tpin": customer_tpin,
                    "original_sell": original_sell,
                    "currencyCd": currencyCd,
                    "exchangeRt": exchangeRt,
                    "created_by": created_by
                }

                if is_export == 1 or vatCd == "C1":
                    self.validate_export(vatCd, export_destination_country, is_export)

                    if export_destination_country == "N / A":
                        frappe.throw("Destination country is required. Please select a valid country.")

                    destination_country_code = self.get_country_code_by_name(export_destination_country)
                    base_data["export_destination_code"] = destination_country_code 


                if iplCd is not None and (vatCd is not None or tlCd is not None):
                    frappe.throw(
                        f"[ZRA Error] IPL transactions (iplCd) must not be combined with VAT or TL. Found: vatCd={vatCd}, tlCd={tlCd}"
                    )
                
                if is_lpo_transactions == 1:
                    if vatCd != "C2":
                        frappe.throw("Only VAT Code 'C2' is allowed for LPO transactions.")
                    if not lpo_number:
                        frappe.throw("LPO Number is required when VAT Code is 'C2' for LPO transactions.")
                    if len(lpo_number) < 9 or len(lpo_number) > 20:
                        frappe.throw("LPO Number length must be between 9 and 20 characters.")
                    base_data["lpoNumber"] = lpo_number

                if vatCd == "C2" and not is_lpo_transactions:
                    frappe.throw("For VAT Code 'C2', LPO transaction must be checked.")

                print("\n[START] Sending sale data...")
                payload = self.build_payload(items, base_data)
                response = self.create_normal_sale_helper(payload)
                response = response.json()
                
                if response.get("resultCd") == "000":

                    company_info = []
                    company_info.append((
                        self.get_company_name(),
                        self.get_company_phone_no(),
                        self.get_company_email(),
                        self.get_tpin(),
                    ))

                
                    customer_info = []
                    customer_info.append((
                        payload["custTpin"],
                        payload["custNm"]
                    ))

                    get_qrcode_url = response.get("data", {}).get("qrCodeUrl") 
                    invoice = []
                    invoice.append((
                        payload["cisInvcNo"],
                        self.todays_date(),
                        "DEBIT NOTE",
                        get_qrcode_url
                        
                    ))
                    sdc_data = []
                    sdc_data.append((
                        self.todays_date(),
                        self.get_origin_sdc_id(),
                                        

                    ))

                    pdf_items = payload["itemList"]
                    print(customer_info, company_info, invoice, pdf_items)
                    # BuildPdf().build_invoice(company_info, customer_info, invoice, pdf_items,  sdc_data, payload)
                    # get_rcpt_no = response.get("data", {}).get("rcptNo")
                    # get_qrcode_url = response.get("data", {}).get("qrCodeUrl") 
                    # print("Stock master updated successfully after sale.")
                    # doc_name = sell_data.get("name")
                    # self.update_rcptNo_delayed(docname=doc_name, rcpt_no=get_rcpt_no)
                    # created_by = sell_data.get("owner")

                    print("This prints immediately, before delayed print")
                    ocrnDt = datetime.now().strftime("%Y%m%d")
                    print(self.to_use_data)

                    update_stock_items = []
                    update_stock_master_items = []

                        
                        
                    for item in self.to_use_data.get("itemList", []):
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
                            "pkg": item.get("pkg", 1),
                            "totDcAmt": item.get("dcAmt", 0),
                        })

                
                        update_stock_master_items.append({
                            "itemCd": item.get("itemCd"),
                            "rsdQty": remaining_stock 
                        })


                    update_stock_payload = {
                        "tpin": self.tpin,
                        "bhfId": self.branch_code,
                        "sarNo": 1,
                        "orgSarNo": 0,
                        "regTyCd": "M",
                        "sarTyCd": "06",
                        "ocrnDt": ocrnDt,
                        "totItemCnt": self.to_use_data['totItemCnt'],
                        "totTaxblAmt": self.to_use_data['totTaxblAmt'],
                        "totTaxAmt": self.to_use_data['totTaxAmt'],
                        "totAmt": self.to_use_data['totAmt'],
                        "regrId": self.to_use_data["regrId"],
                        "regrNm": self.to_use_data["regrId"],
                        "modrNm": self.to_use_data["regrId"],
                        "modrId": self.to_use_data["regrId"],
                        "itemList": update_stock_items
                    }
                    update_stock_master_payload = {
                        "tpin": self.tpin,
                        "bhfId": self.get_branch_code(),
                        "regrId": self.to_use_data["regrId"],
                        "regrNm": self.to_use_data["regrId"],
                        "modrNm": self.to_use_data["regrId"],
                        "modrId": self.to_use_data["regrId"],
                        "stockItemList": update_stock_master_items 
                        }

                    print(update_stock_payload, update_stock_master_items)
                    self.run_stock_update_in_background(update_stock_payload,  update_stock_master_payload, created_by)
                else:
                    result_cd = response.get("resultCd")
                    RequestException(result_cd or "SALE_ERROR").throw()
   