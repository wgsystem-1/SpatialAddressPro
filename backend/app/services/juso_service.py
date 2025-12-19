import requests
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

class JusoService:
    """
    Service to interact with Korea Road Address API (juso.go.kr)
    """
    def __init__(self):
        self.api_key = os.getenv("JUSO_API_KEY")
        # Search API URL (검색 API)
        self.base_url = "https://business.juso.go.kr/addrlink/addrLinkApi.do"

    def search_address(self, keyword: str, page: int = 1, count_per_page: int = 10) -> Dict[str, Any]:
        """
        Search for an address using the keyword.
        """
        if not self.api_key or self.api_key == "your_api_key_here":
            print("Warning: Juso API Key is missing.")
            return {"accepted": False, "error": "API Key missing"}

        params = {
            "confmKey": self.api_key,
            "currentPage": page,
            "countPerPage": count_per_page,
            "keyword": keyword,
            "resultType": "json"
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=5)
            # Debug: Print the actual URL and response for troubleshooting
            print(f"DEBUG: Request URL: {response.url}")
            print(f"DEBUG: Response Status: {response.status_code}")
            print(f"DEBUG: Response Body: {response.text}")
            
            response.raise_for_status()
            data = response.json()
            
            # Check for API errors
            common = data.get("results", {}).get("common", {})
            if common.get("errorCode") != "0":
                return {
                    "accepted": False, 
                    "error": common.get("errorMessage"), 
                    "code": common.get("errorCode")
                }
            
            return {"accepted": True, "data": data.get("results", {}).get("juso", [])}
            
        except requests.RequestException as e:
            return {"accepted": False, "error": str(e)}

juso_service = JusoService()
