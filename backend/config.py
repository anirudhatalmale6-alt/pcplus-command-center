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

CRASHPLAN_BASE_URL = os.getenv("CRASHPLAN_BASE_URL", "https://console.us2.crashplan.com")
CRASHPLAN_CLIENT_ID = os.getenv("CRASHPLAN_CLIENT_ID", "key-1128386f-5633-47d8-845e-fcb80c388abf")
CRASHPLAN_CLIENT_SECRET = os.getenv("CRASHPLAN_CLIENT_SECRET", "")

WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "EAAbkxMWVc4kBRtBPdwEQVTpAZAC4nuF3dBS8t0LbjulOgg19CKeS805n907LVCVdlYRRxaEPF0vOIoB7zReTC5HCHOTcdqnUw0cFjbmTcXemGkp9O2sqK2lYdh5yRBl2Um0YepOfYcwIJFsFn8WOpGEz83z9kbkUmwBc29mOEVJu05ZBQIuD5EDpuW3FvCbQZDZD")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "1104681162719288")
ESCALATION_PHONE = os.getenv("ESCALATION_PHONE", "16047601662")
ESCALATION_EMAIL = os.getenv("ESCALATION_EMAIL", "pcpluscomputing@gmail.com")
ESCALATION_MINUTES = int(os.getenv("ESCALATION_MINUTES", "5"))

REFRESH_INTERVAL = 30
AI_ENABLED = False
