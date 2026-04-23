import os
import resend

def send_invitation(to_email, to_name, invite_url):
    resend.api_key = os.environ.get("RESEND_API_KEY", "")
    resend.Emails.send({
        "from": os.environ.get("RESEND_FROM", "adboard@teteapapineau.com"),
        "to": to_email,
        "subject": "Invitation — AdBoard Tête à Papineau",
        "html": f"""
        <p>Bonjour {to_name},</p>
        <p>Tu as été invité(e) à rejoindre AdBoard.</p>
        <p><a href="{invite_url}" style="background:#E95526;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;display:inline-block">Créer mon compte</a></p>
        <p style="color:#9C7A6A;font-size:12px">Ce lien expire dans 48 heures.</p>
        """,
    })
