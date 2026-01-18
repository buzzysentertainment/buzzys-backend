from app.email_templates._header import buzzy_header

def refund_issued_template(customer_name, amount):
    return f"""
    {buzzy_header()}
    <div style="font-family:Arial, sans-serif; font-size:16px; color:#222;">
        <p>Hi {customer_name},</p>

        <p>Your refund of <strong>${amount:.2f}</strong> has been processed successfully.</p>

        <p>The funds should appear in your account within 3–5 business days, depending on your bank.</p>

        <p>If you have any questions, feel free to reply to this email.</p>

        <p>Thank you,<br>Buzzy’s Team</p>
    </div>
    """
