import requests
import json
from urllib.parse import urljoin

BASE_URL = "http://localhost:8080/sandboxvsdc1.0.8.0/"

class ZARCustomerClient:
    def __init__(self, cust_no=None, tpin=None, cust_name="Unknown", cust_tpin="2000000000", bhf_id="000"):
        self.endpoint = "branches/saveBrancheCustomers"
        self.url = urljoin(BASE_URL, self.endpoint)
        self.headers = {"Content-Type": "application/json"}
        self.cust_no = cust_no
        self.tpin = tpin
        self.cust_name = cust_name
        self.cust_tpin = cust_tpin
        self.bhf_id = bhf_id

    def create_customer(self):
        if not self.cust_no or not self.tpin:
            raise ValueError("cust_no and tpin are required")

        payload = {
            "tpin": self.tpin,
            "bhfId": self.bhf_id,
            "custNo": self.cust_no,
            "custTpin": self.cust_tpin,
            "custNm": self.cust_name,
            "adrs": None,
            "email": None,
            "faxNo": None,
            "useYn": "Y",
            "remark": None,
            "regrNm": "Admin",
            "regrId": "Admin",
            "modrNm": "Admin",
            "modrId": "Admin"
        }

        try:
            response = requests.post(self.url, headers=self.headers, json=payload)
            print("Status Code:", response.status_code)
            print("Response:", response.text)
        except requests.exceptions.RequestException as e:
            print("Error:", e)



