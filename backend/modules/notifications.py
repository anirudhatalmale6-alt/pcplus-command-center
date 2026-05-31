import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import (
    WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_ID,
    ESCALATION_PHONE, ESCALATION_EMAIL
)

WA_API = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"


async def send_whatsapp_alert(ticket_number, ticket_title, minutes_waiting):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                WA_API,
                headers={
                    "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": ESCALATION_PHONE,
                    "type": "template",
                    "template": {
                        "name": "ticket_alert",
                        "language": {"code": "en_US"},
                        "components": [
                            {
                                "type": "body",
                                "parameters": [
                                    {"type": "text", "text": str(minutes_waiting)},
                                    {"type": "text", "text": str(ticket_number)},
                                    {"type": "text", "text": str(ticket_title)[:100]},
                                ],
                            }
                        ],
                    },
                },
            )
            return resp.status_code == 200
    except Exception:
        return False


def send_email_alert(ticket_number, ticket_title, minutes_waiting):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[ALERT] Ticket #{ticket_number} unacknowledged - {minutes_waiting}min"
        msg["From"] = "alerts@pcpluscomputing.com"
        msg["To"] = ESCALATION_EMAIL

        text = (
            f"A new support ticket has been waiting {minutes_waiting} minutes "
            f"with no acknowledgment.\n\n"
            f"Ticket: #{ticket_number}\n"
            f"Subject: {ticket_title}\n\n"
            f"Please check the Command Center or respond to the customer.\n\n"
            f"-- PC Plus Computing Command Center"
        )

        html = f"""<div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:20px">
<div style="background:#0a1628;color:#fff;padding:16px 20px;border-radius:8px 8px 0 0">
<strong style="color:#2596be">PC Plus Computing</strong> - Command Center Alert
</div>
<div style="background:#f8f9fa;padding:20px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px">
<p style="color:#e74c3c;font-weight:bold;font-size:16px">Unacknowledged Ticket - {minutes_waiting} minutes</p>
<table style="width:100%;margin:12px 0">
<tr><td style="color:#666;padding:4px 0">Ticket:</td><td style="font-weight:bold">#{ticket_number}</td></tr>
<tr><td style="color:#666;padding:4px 0">Subject:</td><td>{ticket_title}</td></tr>
</table>
<p style="color:#666;font-size:13px">Please check the Command Center or respond to the customer.</p>
</div></div>"""

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP("localhost", 25) as s:
            s.send_message(msg)
        return True
    except Exception:
        return False


async def escalate_ticket(ticket_number, ticket_title, minutes_waiting):
    wa_ok = await send_whatsapp_alert(ticket_number, ticket_title, minutes_waiting)
    email_ok = send_email_alert(ticket_number, ticket_title, minutes_waiting)
    return {"whatsapp": wa_ok, "email": email_ok}
