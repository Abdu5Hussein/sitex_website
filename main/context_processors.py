from django.conf import settings

def website_context(request):
    return {
        "WEBSITE_NAME": getattr(settings, "WEBSITE_NAME", "Website"),
        "WEBSITE_NAME_AR": getattr(settings, "WEBSITE_NAME_AR", "موقع الويب"),
        "WEBSITE_DESCRIPTION": getattr(settings, "WEBSITE_DESCRIPTION", "A description of the website."),
        "WEBSITE_DESCRIPTION_AR": getattr(settings, "WEBSITE_DESCRIPTION_AR", "وصف الموقع."),
    }
