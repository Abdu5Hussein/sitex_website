# forms.py
from django import forms
from django.core.validators import FileExtensionValidator
from main.models import Merchant, MerchantSubscription, MerchantPackage

class MerchantBasicInfoForm(forms.ModelForm):
    class Meta:
        model = Merchant
        fields = ['name', 'phone', 'email', 'city', 'address']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }

class MerchantVerificationForm(forms.ModelForm):
    id_document = forms.FileField(
        required=True,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])]
    )
    business_license = forms.FileField(
        required=False,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])]
    )
    
    class Meta:
        model = Merchant
        fields = ['id_document', 'business_license']

class MerchantBankDetailsForm(forms.ModelForm):
    class Meta:
        model = Merchant
        fields = ['lypay_number', 'bank_iban']

class SubscriptionSelectionForm(forms.Form):
    package = forms.ModelChoiceField(
        queryset=MerchantPackage.objects.filter(is_active=True),
        widget=forms.RadioSelect
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['package'].empty_label = None
        self.fields['package'].label_from_instance = lambda obj: f"{obj.name} - ${obj.monthly_price}/month"