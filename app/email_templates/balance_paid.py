from app.email_templates._header import buzzy_header

def balance_paid_template(customer_name, event_date):
    return f"""
    {buzzy_header()}
    <div style="font-family:Arial, sans-serif; font-size:16px; color:#222;">
        <p>Hi {customer_name},</p>

        <p>Great news — your remaining balance for your event on <strong>{event_date}</strong> has been successfully paid.</p>

        <p>Your booking is now fully settled. We’ll handle everything from here and ensure your setup is smooth and on time.</p>

        <p>If you need to update any event details, feel free to reply to this email.</p>

        <p>Thank you for choosing Buzzy’s,<br>Buzzy’s Team</p>
    </div>
    """
