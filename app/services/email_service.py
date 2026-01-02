import os
import resend
from dotenv import load_dotenv

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

def send_email(to: str, subject: str, html: str):
    try:
        params = {
            "from": "Buzzy’s Inflatables <no-reply@buzzys.org>",
            "to": [to],
            "subject": subject,
            "html": html,
        }

        response = resend.Emails.send(params)
        return {"status": "success", "response": response}

    except Exception as e:
        return {"status": "error", "message": str(e)}