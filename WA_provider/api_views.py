# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from main.models import MerchantPackage, MerchantSubscription

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe_package(request):
    merchant = request.user.owned_merchants.first()
    if not merchant:
        return Response({"success": False, "message": "No merchant found."}, status=400)

    package_id = request.data.get("package_id")
    if not package_id:
        return Response({"success": False, "message": "Package ID is required."}, status=400)

    try:
        package = MerchantPackage.objects.get(id=package_id, is_active=True)
    except MerchantPackage.DoesNotExist:
        return Response({"success": False, "message": "Package not found."}, status=404)

    # Deactivate existing subscription
    try:
        subscription = merchant.subscription
        subscription.is_active = False
        subscription.save()
    except MerchantSubscription.DoesNotExist:
        subscription = None

    # Create new subscription
    subscription = MerchantSubscription.objects.create(
        merchant=merchant,
        package=package,
        started_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=30),
        is_active=True
    )

    return Response({"success": True, "message": f"Subscribed to {package.name}"})
