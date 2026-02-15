import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from django.conf import settings

def send_brevo_email(to_email, subject, html_content):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = settings.BREVO_API_KEY

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email}],
        subject=subject,
        html_content=html_content,
        sender={"email": settings.DEFAULT_FROM_EMAIL.split("<")[1].replace(">", "")}
    )

    try:
        api_instance.send_transac_email(email)
    except ApiException as e:
        raise Exception(f"Brevo email failed: {e}")

