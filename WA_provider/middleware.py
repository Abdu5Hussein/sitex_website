# middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from main.models import Merchant
from django.http import HttpResponseForbidden

class OnboardingMiddleware:
    """
    Middleware to ensure that merchants complete onboarding before accessing certain pages.
    """
    def __init__(self, get_response):
        self.get_response = get_response

        # Merchant URLs that require completed onboarding
        self.merchant_urls = [
            '/merchant/payment-links/',
            '/merchant/payment-links/edit/',
            '/merchant/payment-links/delete/',
            '/merchant/transactions/',
            '/merchant/invoices/',
            '/merchant/invoices/create/',
            '/merchant/invoices/edit/',
            '/invoices/delete/',
            '/merchant/payouts/',
            '/merchant/subscription/',
            '/merchant/settings/',
            '/api/subscribe/',
            '/merchant/dashboard/',

        ]

    def __call__(self, request):
        # Skip for anonymous users
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip admin users
        if getattr(request.user, 'is_admin', False):
            return self.get_response(request)

        # Skip onboarding page itself to avoid redirect loop
        if request.path.startswith('/merchant/onboarding/'):
            return self.get_response(request)

        # Only check merchant URLs
        path_requires_onboarding = any(request.path.startswith(url) for url in self.merchant_urls)
        if not path_requires_onboarding:
            return self.get_response(request)

        # Check if user is a merchant
        if getattr(request.user, 'is_marchent', False):
            try:
                merchant = Merchant.objects.get(owner=request.user)
            except Merchant.DoesNotExist:
                return redirect(reverse('WA_provider:merchant_onboarding'))

            # Redirect if onboarding not completed
            if merchant.onboarding_step != 'completed':
                return redirect(f"{reverse('WA_provider:merchant_onboarding')}?step={merchant.onboarding_step}")

            # Completed merchants proceed
            return self.get_response(request)

        # Public payment links allowed
        if request.path.startswith('/pay/'):
            return self.get_response(request)

        # Non-merchant users blocked
        return HttpResponseForbidden("Access denied. Merchant account required.")
