from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.text import slugify
from decimal import Decimal
from django.utils.timezone import now
from django.utils import timezone
import random
import string

def generate_unique_slug(model_class, name):
    base_slug = slugify(name)
    slug = base_slug
    while model_class.objects.filter(slug=slug).exists():
        # Add random 4-digit suffix
        suffix = ''.join(random.choices(string.digits, k=4))
        slug = f"{base_slug}-{suffix}"
    return slug

# Custom User
class User(AbstractUser):
    is_admin = models.BooleanField(default=False)
    is_guest = models.BooleanField(default=True)
    is_company_user = models.BooleanField(default=False)
    is_wa_provider_user = models.BooleanField(default=False)
    is_client = models.BooleanField(default=False)
    is_marchent = models.BooleanField(default=False)
    # Fix reverse accessor clashes
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_groups',  # <-- Add this
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions',  # <-- Add this
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )

class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)  # allow blank initially
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:  # only generate if empty
            self.slug = self.name  # directly assign name for Arabic slug
            # Or if you want slugify (works with Arabic too):
            # self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class brand(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='brands/', blank=True, null=True)

    def __str__(self):
        return self.name
# Product
class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    quantity_available = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # optional
    image = models.ImageField(upload_to='products/', null=True, blank=True)  # New field
    video = models.FileField(upload_to='products/videos/', null=True, blank=True)  # New field
    show_quantity = models.BooleanField(default=True)  # New field to control quantity visibility
    show_price = models.BooleanField(default=True)  # New field to control price visibility
    place_orders = models.BooleanField(default=True)  # New field to control if orders can be placed
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,default=0.00)  # New field
    brand = models.ForeignKey(brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    @property
    def discounted_price(self):
        """
        Returns price after applying discount_percentage.
        If no valid discount, returns the original price.
        """
        if self.price and self.discount_percentage and 0 < self.discount_percentage < 100:
            return self.price * (Decimal('1') - Decimal(self.discount_percentage) / Decimal('100'))
        return self.price

    def __str__(self):
        return self.name


# Branch
class Branch(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    Email_Adress = models.EmailField(null=True, blank=True)
    opening_hours = models.CharField(max_length=100, null=True, blank=True)
    closing_hours = models.CharField(max_length=100, null=True, blank=True)
    day_from = models.CharField(max_length=50, null=True, blank=True)
    day_to = models.CharField(max_length=50, null=True, blank=True)
    address = models.CharField(max_length=500, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    facbook_link = models.URLField(null=True, blank=True)
    instagram_link = models.URLField(null=True, blank=True)
    twitter_link = models.URLField(null=True, blank=True)
    linkdin_link = models.URLField(null=True, blank=True)
    primery_branch = models.BooleanField(default=False)

    def __str__(self):
        return self.name

# Inquiry (orders from guests)
class Inquiry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    guest_id = models.CharField(max_length=100, null=True, blank=True)  # for guest users

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=250, default='قيد المعالجة')  # e.g., Pending, Processed, Shipped
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=100)

    latitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)
    longitude = models.DecimalField(max_digits=18, decimal_places=15, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Inquiry for {self.product.name}"


# Contact Message
class ContactMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class Invoice(models.Model):
    name = models.CharField(max_length=150, blank=True, null=True)  # Guest or user name
    city = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True, null=True)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, blank=True, null=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True)

    def __str__(self):
        return f"Invoice {self.id} - {self.name or 'Guest'}"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items', blank=True, null=True)
    product_id = models.IntegerField(blank=True, null=True)  # or ForeignKey to Product
    name = models.CharField(max_length=200, blank=True, null=True)
    quantity = models.PositiveIntegerField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True,default=0.00)
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price per unit before discount"
    )

    def __str__(self):
        return f"Item {self.id} for Invoice {self.invoice.id if self.invoice else 'Unknown'}"
    @property
    def subtotal(self):
        """Return quantity * price (discounted), safely handling None values."""
        q = self.quantity or 0
        p = self.price if self.price is not None else Decimal("0")
        return p * q

class Banner(models.Model):
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=200, blank=True, null=True)
    image = models.ImageField(upload_to='banners/')
    button_text = models.CharField(max_length=50, blank=True, null=True)
    button_link = models.URLField(blank=True, null=True)  # New URL field
    text_color = models.CharField(max_length=20, default='white')  # e.g., 'white' or 'dark'
    order = models.PositiveIntegerField(default=0)  # for ordering banners
    is_active = models.BooleanField(default=True)  # only show active banners

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title

class City(models.Model):
    name = models.CharField(max_length=100)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name


class images(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='additional_images')
    image = models.ImageField(upload_to='products/additional/')

    def __str__(self):
        return f"Image for {self.product.name}"


class Project(models.Model):
    # Optional: link to a Client model if you have one later
    # client = models.ForeignKey("Client", on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)  # allow blank for auto
    description = models.TextField(blank=True, null=True)

    # Used in your "Selected Projects" cards
    image = models.ImageField(upload_to="projects/", blank=True, null=True)

    # Public link to project (optional)
    url = models.URLField(blank=True, null=True)

    # Badges shown in the UI
    project_type = models.CharField(max_length=120, blank=True, null=True)  # e.g. Website, Dashboard, Integration
    stack = models.CharField(max_length=255, blank=True, null=True)         # e.g. Django, DRF, React, PostgreSQL
    industry = models.CharField(max_length=120, blank=True, null=True)      # e.g. Banking, Retail, Logistics
    year = models.PositiveIntegerField(blank=True, null=True)

    # Nice ordering + filtering
    is_featured = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        # Keep Arabic slugs allowed (like your Category model)
        if not self.slug:
            self.slug = self.title
        super().save(*args, **kwargs)

class ApiClient(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="api_client",
        null=True,       # temporary
        blank=True       # optional
    )
    name = models.CharField(max_length=150)
    company = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    api_key = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class WhatsAppLog(models.Model):
    client = models.ForeignKey(ApiClient, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)
    message = models.TextField()
    status = models.CharField(max_length=20)
    provider_id = models.CharField(max_length=100, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class MessagePackage(models.Model):
    name = models.CharField(max_length=100, verbose_name="Package Name")
    message_count = models.PositiveIntegerField(verbose_name="Number of Messages")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Price (USD)")
    description = models.TextField(blank=True, null=True, verbose_name="Description")  # optional
    duration_days = models.PositiveIntegerField(default=30, verbose_name="Validity (Days)")
    is_active = models.BooleanField(default=True, verbose_name="Active Package")
    plan_code = models.CharField(max_length=50, null=True, blank=True, verbose_name="Plan Code")

    # Safe for existing rows
    created_at = models.DateTimeField(verbose_name="Created At", default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Message Package"
        verbose_name_plural = "Message Packages"

    def __str__(self):
        return f"{self.name} ({self.message_count} msgs) - ${self.price}"

class ClientMessageBalance(models.Model):
    client = models.OneToOneField(ApiClient, on_delete=models.CASCADE)

    total_messages = models.PositiveIntegerField(default=0)
    used_messages = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    @property
    def remaining_messages(self):
        return self.total_messages - self.used_messages

    def __str__(self):
        return f"{self.client.name} Balance"

class MessagePurchase(models.Model):
    client = models.ForeignKey(ApiClient, on_delete=models.CASCADE)
    package = models.ForeignKey(MessagePackage, on_delete=models.PROTECT)

    messages_added = models.PositiveIntegerField()
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)

    purchased_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client} bought {self.messages_added}"


class WhatsAppMessage(models.Model):
    STATUS_CHOICES = (
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("delivered", "Delivered"),
    )

    MESSAGE_TYPE = (
        ("otp", "OTP"),
        ("text", "Text"),
        ("template", "Template"),
    )

    client = models.ForeignKey(ApiClient, on_delete=models.CASCADE)

    phone = models.CharField(max_length=20)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE)
    content = models.TextField()

    provider_message_id = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")

    cost = models.DecimalField(max_digits=6, decimal_places=4, default=0)

    created_at = models.DateTimeField(auto_now_add=True)


class ApiUsage(models.Model):
    client = models.ForeignKey(ApiClient, on_delete=models.CASCADE)
    date = models.DateField()

    total_messages_sent = models.PositiveIntegerField(default=0)

class Merchant(models.Model):
    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("pending", "Pending Review"),
        ("active", "Active"),
        ("suspended", "Suspended"),
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_merchants"
    )
    onboarding_step = models.CharField(
        max_length=50,
        default='basic_info',
        choices=(
            ('basic_info', 'Basic Information'),
            ('verification', 'Verification'),
            ('bank_details', 'Bank Details'),
            ('subscription', 'Subscription Plan'),
            ('completed', 'Completed')
        )
    )
        # Document verification fields
    id_document = models.FileField(
        upload_to='merchant/documents/id/',
        null=True,
        blank=True
    )
    business_license = models.FileField(
        upload_to='merchant/documents/license/',
        null=True,
        blank=True
    )
    id_verified = models.BooleanField(default=False)
    business_verified = models.BooleanField(default=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)

    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)

    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)

    # Settlement info
    lypay_number = models.CharField(max_length=20, blank=True, null=True)
    bank_iban = models.CharField(max_length=50, blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    balance_available = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    balance_on_hold = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
            if not self.slug:
                self.slug = generate_unique_slug(Merchant, self.name)
            super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class PaymentLink(models.Model):
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="payment_links"
    )

    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    invoice = models.ForeignKey(
            "MerchantInvoice",
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name="payment_links"
        )
    reference = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    expires_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.amount}"

class Transaction(models.Model):
    STATUS_CHOICES = (
        ("initiated", "Initiated"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    )

    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    payment_link = models.ForeignKey(
        PaymentLink,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    plutu_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    platform_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    net_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="initiated"
    )

    gateway_reference = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

class MerchantInvoice(models.Model):
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="invoices"
    )

    invoice_number = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.invoice_number


class MerchantInvoiceItem(models.Model):
    invoice = models.ForeignKey(
        MerchantInvoice,
        on_delete=models.CASCADE,
        related_name="items"
    )

    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return self.quantity * self.unit_price


class Payout(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="payouts"
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    method = models.CharField(
        max_length=20,
        choices=(("lypay", "LyPay"), ("bank", "Bank"))
    )

    reference = models.CharField(max_length=150, blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    processed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

class MerchantPackage(models.Model):
    name = models.CharField(max_length=100)
    monthly_price = models.DecimalField(max_digits=8, decimal_places=2)

    transaction_fee_percent = models.DecimalField(
        max_digits=4, decimal_places=2,
        help_text="Platform fee percentage"
    )

    max_payment_links = models.PositiveIntegerField(default=10)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class MerchantSubscription(models.Model):
    merchant = models.OneToOneField(
        Merchant,
        on_delete=models.CASCADE,
        related_name="subscription"
    )

    package = models.ForeignKey(
        MerchantPackage,
        on_delete=models.PROTECT
    )

    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    is_active = models.BooleanField(default=True)
