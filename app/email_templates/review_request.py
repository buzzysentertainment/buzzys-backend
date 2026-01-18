from app.email_templates._header import buzzy_header

def review_request_template(customer_name, review_link):
    return f"""
    {buzzy_header()}
    <div style="font-family:Arial, sans-serif; font-size:16px; color:#222;">
        <p>Hi {customer_name},</p>

        <p>We hope your event was a wonderful experience. It was our pleasure to help make your day special.</p>

        <p>If you have a moment, we’d truly appreciate your feedback. Your review helps other families feel confident choosing Buzzy’s for their celebrations.</p>

        <p>
            <a href="{review_link}" 
               style="display:inline-block; padding:10px 18px; background:#0066cc; color:#fff; 
                      text-decoration:none; border-radius:6px; margin-top:10px;">
                Leave a Google Review
            </a>
        </p>

        <p>Thank you again for choosing Buzzy’s Inflatables. We hope to celebrate with you again soon.</p>

        <p>Warm regards,<br>Buzzy’s Team</p>
    </div>
    """
