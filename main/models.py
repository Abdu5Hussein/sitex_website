from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.text import slugify
from decimal import Decimal

# Custom User
class User(AbstractUser):
    is_admin = models.BooleanField(default=False)
    is_guest = models.BooleanField(default=True)

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