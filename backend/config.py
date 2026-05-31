import os

ZAMMAD_URL = "https://support.pcpluscomputing.com"
ZAMMAD_TOKEN = os.getenv("ZAMMAD_TOKEN", "VNUEETcjfo1lhGnf43lbA8Qwc_rQpNiiG3LZcaSbpQxjUKHPDvvGrejuTWlOTKfb")

RMM_URL = "https://api.pcpluscomputing.com"
RMM_API_KEY = os.getenv("RMM_API_KEY", "WDHX6IPCKJ9BISAFVOUJFFXVKKN5HMZV")

PCRT_DB_HOST = os.getenv("PCRT_DB_HOST", "65.7.31.124")
PCRT_DB_NAME = os.getenv("PCRT_DB_NAME", "pcrt")
PCRT_DB_USER = os.getenv("PCRT_DB_USER", "")
PCRT_DB_PASS = os.getenv("PCRT_DB_PASS", "")

CALCOM_URL = os.getenv("CALCOM_URL", "https://cal.pcpluscomputing.com")

REFRESH_INTERVAL = 30
AI_ENABLED = False
