import os
import resend
from dotenv import load_dotenv

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

def send_email_template(to: str, template_id: str, data: dict):
    """
    Sends an email using a Resend hosted template.
    """
    try:
        response = resend.Emails.send({
            "from": "Buzzy’s Inflatables <no-reply@buzzys.org>",
            "to": [to],
            "template_id": template_id,
            "data": data
        })
        return {"status": "success", "response": response}

    except Exception as e:
        return {"status": "error", "message": str(e)}
