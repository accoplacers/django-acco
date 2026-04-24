from django.conf import settings

def site_config(request):
    """
    Makes site-wide configuration variables available in all templates.
    """
    return {
        'WHATSAPP_NUMBER': settings.WHATSAPP_CONTACT_NUMBER,
    }
