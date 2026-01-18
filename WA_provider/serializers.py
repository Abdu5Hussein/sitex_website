# serializers.py
from rest_framework import serializers
from main.models import MerchantPackage, MerchantSubscription

class MerchantPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MerchantPackage
        fields = ['id', 'name', 'monthly_price', 'transaction_fee_percent', 'max_payment_links']

class MerchantSubscriptionSerializer(serializers.ModelSerializer):
    package = MerchantPackageSerializer()

    class Meta:
        model = MerchantSubscription
        fields = ['id', 'package', 'started_at', 'expires_at', 'is_active']
