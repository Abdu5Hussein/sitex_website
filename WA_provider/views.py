from django.shortcuts import render, redirect,get_object_or_404
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login,get_user_model
from django.contrib import messages
from django.utils import timezone
import uuid
import random
import secrets
from django.db import IntegrityError
from django.utils.timezone import now, timedelta
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from decimal import Decimal
from functools import wraps
from .forms import (
    MerchantBasicInfoForm,
    MerchantVerificationForm,
    MerchantBankDetailsForm,
    SubscriptionSelectionForm
)
from main.models import (
    ApiClient,
    MessagePackage,
    ClientMessageBalance,
    MessagePurchase,
    WhatsAppMessage,
    WhatsAppLog,
    ApiUsage,
    Merchant,
    MerchantPackage,
    MerchantSubscription,
    MerchantInvoice,
    PaymentLink,
    Transaction,
    MerchantInvoiceItem,
    Payout,
)
from django.db.models import Q, F,Sum, Count, Avg, Q, ExpressionWrapper, FloatField,Max,Case, When, Value, CharField
from django.db import transaction
import json

# -----------------------
# Home / Health Check
# -----------------------
def index(request):
    return HttpResponse("WA Provider is working ✅")

# -----------------------
# User Registration
# -----------------------
User = get_user_model()

def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        email = request.POST.get("email")
        full_name = request.POST.get("full_name")
        company = request.POST.get("company", "")

        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("WA_provider:register_user")

        # 1️⃣ Create User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=full_name
        )
        user.is_guest = False
        user.is_client = True
        user.save()

        # 2️⃣ Create ApiClient linked to user (solid relation)
        api_key = secrets.token_hex(32)
        client = ApiClient.objects.create(
            user=user,        # link directly to user
            company=company,
            api_key=api_key
        )

        # 3️⃣ Log the user in
        login(request, user)
        messages.success(request, "Registration successful. API Client created!")

        return redirect("WA_provider:dashboard")  # go to API dashboard

    # GET request
    return render(
        request,
        "login_register.html",
        {"reg_messages": messages.get_messages(request)}
    )

# -----------------------
# Choose Message Package
# -----------------------
@login_required(login_url='/login/')
def choose_package(request):
    # Get all active packages
    packages = MessagePackage.objects.filter(is_active=True).order_by('price')

    if request.method == "POST":
        package_id = request.POST.get("package_id")
        if not package_id:
            messages.error(request, "No package selected.")
            return redirect('WA_provider:choose_package')

        # Save selected package in session
        request.session['selected_package'] = package_id
        return redirect('WA_provider:checkout')

    return render(request, 'choose_package.html', {"packages": packages})


# -----------------------
# Checkout / Payment Simulation
# -----------------------
@login_required(login_url='/login/')
def checkout(request):
    raw = request.session.get('selected_package')
    if raw is None:
        return redirect('WA_provider:choose_package')

    raw_str = str(raw).strip()
    if not raw_str:
        return redirect('WA_provider:choose_package')

    # Build lookup safely
    q = Q()
    if raw_str.isdigit():
        q = Q(id=int(raw_str))
    else:
        q = Q(plan_code=raw_str)

    package = MessagePackage.objects.filter(q, is_active=True).first()
    if not package:
        messages.error(request, f"{ raw_str } Package not found.")
        return redirect('WA_provider:choose_package')

    if request.method == "POST":
        with transaction.atomic():
            client, _ = ApiClient.objects.get_or_create(user=request.user)

            balance, _ = ClientMessageBalance.objects.get_or_create(client=client)
            ClientMessageBalance.objects.filter(pk=balance.pk).update(
                total_messages=F('total_messages') + package.message_count
            )
            balance.refresh_from_db()

            MessagePurchase.objects.create(
                client=client,
                package=package,
                messages_added=package.message_count,
                price_paid=package.price
            )

        messages.success(request, f"Purchase successful! You have {balance.remaining_messages} messages now.")
        return redirect('WA_provider:dashboard')

    return render(request, 'checkout.html', {"package": package})


# -----------------------
# Dashboard
# -----------------------
@login_required(login_url='/login/')
def WA_dashboard(request):
    user = request.user

    # Only allow client users
    if not user.is_client:
        return redirect('/')  # or some "not allowed" page

    try:
        client = ApiClient.objects.get(user=user)
    except ApiClient.DoesNotExist:
        # No API client record, force subscription or creation
        return redirect('/choose-package/')

    # Get or create message balance
    balance, created = ClientMessageBalance.objects.get_or_create(client=client)

    # If client has no subscription/messages, redirect to choose package
    if balance.total_messages == 0:
        return redirect('/choose-package/')

    # Ensure API key exists
    if not client.api_key:
        client.api_key = str(uuid.uuid4())
        client.save()

    # Get last 10 messages
    last_messages = WhatsAppMessage.objects.filter(client=client).order_by('-created_at')[:10]

    return render(request, 'dashboard.html', {
        "client": client,
        "api_key": client.api_key,
        "balance": balance,
        "last_messages": last_messages,
    })
@login_required(login_url='/login/')
def dashboard(request):
    user = request.user

    # Check roles
    can_merchant = getattr(user, "is_marchent", False)  # fixed typo
    can_client = getattr(user, "is_client", False)

    context = {
        "can_merchant": can_merchant,
        "can_client": can_client,
        # If user is not a merchant, provide register link
        "merchant_register_url": None
    }

    if not can_merchant:
        from django.urls import reverse
        context["merchant_register_url"] = reverse("WA_provider:merchant_register")

    # If user has neither role, redirect home
    if not can_merchant and not can_client:
        return redirect("/")

    return render(request, "homedashboard.html", context)


# -----------------------
# Send OTP / Message
# -----------------------
@login_required(login_url='/login/')
@require_POST
def send_otp(request):
    client = ApiClient.objects.get(email=request.user.email)
    balance, _ = ClientMessageBalance.objects.get_or_create(client=client)

    phone = request.POST.get("phone")
    message_type = request.POST.get("message_type", "otp")  # otp / text
    content = request.POST.get("message", "")

    if not phone:
        return JsonResponse({"error": "Phone number is required."}, status=400)

    if balance.remaining_messages <= 0:
        return JsonResponse({"error": "Insufficient message balance."}, status=400)

    # Generate OTP if type=otp
    if message_type == "otp":
        otp_code = str(random.randint(100000, 999999))
        content = f"Your OTP is {otp_code}"

    # Deduct message
    balance.used_messages += 1
    balance.save()

    # Log message
    msg = WhatsAppMessage.objects.create(
        client=client,
        phone=phone,
        message_type=message_type,
        content=content,
        status="queued",  # later update after sending via provider
    )

    # Optional: log raw WhatsApp API call
    WhatsAppLog.objects.create(
        client=client,
        phone=phone,
        message=content,
        status="queued",
        provider_id=None
    )

    # Track usage per day
    today = timezone.now().date()
    usage, _ = ApiUsage.objects.get_or_create(client=client, date=today)
    usage.total_messages_sent += 1
    usage.save()

    return JsonResponse({
        "success": True,
        "message_id": msg.id,
        "remaining_messages": balance.remaining_messages,
        "content": content
    })
###############################################################
#marchent_mvp 
################################################################

def merchant_owner_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # get the merchant owned by the logged-in user
        merchant = getattr(request.user, 'owned_merchants', None)
        merchant = merchant.first() if merchant else None

        if not merchant:
            return redirect("merchant_register")

        # attach to request
        request.merchant = merchant
        return view_func(request, *args, **kwargs)
    return wrapper

@login_required
def merchant_register(request):
    packages = MerchantPackage.objects.filter(is_active=True)

    if request.method == "POST":
        package_id = request.POST.get("package")
        if not package_id:
            return render(request, "merchant_register.html", {"packages": packages, "error": "Please select a package."})

        package = MerchantPackage.objects.get(id=package_id)

        merchant = Merchant.objects.create(
            owner=request.user,
            name=request.POST.get("name"),
            phone=request.POST.get("phone"),
            email=request.POST.get("email"),
            city=request.POST.get("city"),
            address=request.POST.get("address"),
            lypay_number=request.POST.get("lypay"),
            status='draft',
            onboarding_step='basic_info'
        )

        # Set user as merchant
        request.user.is_merchant = True
        request.user.save()

        # Optionally create subscription record for selected package
        MerchantSubscription.objects.create(
            merchant=merchant,
            package=package,
            expires_at=timezone.now() + timedelta(days=30),
            is_active=True
        )

        return redirect("WA_provider:merchant_onboarding")
    
    return render(request, "merchant_register.html", {"packages": packages})

@login_required
@merchant_owner_required
def merchant_dashboard(request):
    merchant = request.merchant  # guaranteed to be the logged-in user's merchant
    return render(request, "merchant_dashboard.html", {
        "merchant": merchant
    })





@login_required
@merchant_owner_required
def payment_links(request):
    merchant = request.merchant  # safe: always the logged-in user's merchant

    if request.method == "POST":
        title = request.POST.get("title")
        amount = request.POST.get("amount")
        invoice_id = request.POST.get("invoice")
        expires_at = request.POST.get("expires_at")

        invoice = None
        if invoice_id:
            invoice = MerchantInvoice.objects.filter(id=invoice_id, merchant=merchant).first()
            if invoice:
                amount = invoice.total_amount

        link = PaymentLink.objects.create(
            merchant=merchant,
            title=title,
            amount=amount,
            reference=str(uuid.uuid4()).replace("-", "")[:12],
            expires_at=expires_at if expires_at else None,
            is_active=True,
            invoice=invoice
        )

        return redirect("WA_provider:payment_links")

    links = merchant.payment_links.all()
    invoices = merchant.invoices.all()

    for link in links:
        link.full_url = request.build_absolute_uri(
            reverse("WA_provider:customer_payment_link", args=[link.reference])
        )

    return render(request, "merchant_payment_links.html", {
        "merchant": merchant,
        "links": links,
        "invoices": invoices
    })

@merchant_owner_required
@login_required
def edit_payment_link(request, link_id):
    merchant = request.merchant  # safe: always the logged-in user's merchant
    link = PaymentLink.objects.get(id=link_id, merchant=merchant)
    invoices = merchant.invoices.all()

    if request.method == "POST":
        link.title = request.POST.get("title")
        link.amount = request.POST.get("amount")
        invoice_id = request.POST.get("invoice")
        link.invoice = MerchantInvoice.objects.filter(id=invoice_id, merchant=merchant).first() if invoice_id else None
        expires_at = request.POST.get("expires_at")
        link.expires_at = expires_at if expires_at else None
        link.save()
        return redirect("/merchant/payment-links/")

    return render(request, "merchant_edit_payment_link.html", {"link": link, "invoices": invoices})


@merchant_owner_required
@login_required
def delete_payment_link(request, link_id):
    merchant = request.merchant  # safe: always the logged-in user's merchant
    link = PaymentLink.objects.get(id=link_id, merchant=merchant)
    if request.method == "POST":
        link.delete()
        return redirect("/merchant/payment-links/")
    return render(request, "merchant_delete_payment_link.html", {"link": link})





def customer_payment_link(request, reference):
    link = get_object_or_404(PaymentLink, reference=reference)

    # Check if already paid via transaction first
    existing_txn = Transaction.objects.filter(payment_link=link, status="paid").first()
    if existing_txn:
        return redirect("WA_provider:payment_success", transaction_id=existing_txn.id)

    # Check if link is inactive or expired
    if not link.is_active or (link.expires_at and link.expires_at < timezone.now()):
        return render(request, "customer_payment_link.html", {
            "link": link,
            "message": "This payment link is no longer valid."
        })

    # POST: process payment
    if request.method == "POST":
        amount = link.amount

        # Create transaction
        transaction = Transaction.objects.create(
            merchant=link.merchant,
            payment_link=link,
            amount=amount,
            plutu_fee=0,
            platform_fee=0,
            net_amount=amount,
            status="paid",
            gateway_reference=str(uuid.uuid4()).replace("-", "")[:12],
            created_at=timezone.now()
        )

        # Update merchant balance
        link.merchant.balance_available += amount
        link.merchant.save()

        # Mark link inactive
        link.is_active = False
        link.save()

        return redirect("WA_provider:payment_success", transaction_id=transaction.id)

    return render(request, "customer_payment_link.html", {
        "link": link
    })

def payment_success(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    return render(request, "payment_success.html", {
        "transaction": transaction
    })

@merchant_owner_required
@login_required
def transaction_list(request):
    merchant = request.merchant  # safe: always the logged-in user's merchant
    transactions = merchant.transactions.all() if merchant else []
    return render(request, "merchant_transactions.html", {
        "merchant": merchant,
        "transactions": transactions
    })

@merchant_owner_required
@login_required
def invoice_list(request):
    merchant = request.merchant  # safe: always the logged-in user's merchant
    invoices = merchant.invoices.all() if merchant else []
    return render(request, "merchant_invoices.html", {
        "merchant": merchant,
        "invoices": invoices
    })

@merchant_owner_required    
@login_required
def create_invoice(request):
    merchant = request.merchant  # safe: always the logged-in user's merchant
    if request.method == "POST":
        invoice_number = request.POST.get("invoice_number")
        description = request.POST.get("description", "")

        invoice = MerchantInvoice.objects.create(
            merchant=merchant,
            invoice_number=invoice_number,
            description=description,
            total_amount=0  # will calculate below
        )

        total = 0
        items_desc = request.POST.getlist("item_description[]")
        items_qty = request.POST.getlist("item_quantity[]")
        items_price = request.POST.getlist("item_unit_price[]")

        for desc, qty, price in zip(items_desc, items_qty, items_price):
            qty = int(qty)
            price = float(price)
            MerchantInvoiceItem.objects.create(
                invoice=invoice,
                description=desc,
                quantity=qty,
                unit_price=price
            )
            total += qty * price

        invoice.total_amount = total
        invoice.save()

        return redirect("WA_provider:invoice_list")

    return render(request, "merchant_create_invoice.html", {"merchant": merchant})
@merchant_owner_required    
@login_required
def edit_invoice(request, invoice_id):
    merchant = request.merchant  # safe: always the logged-in user's merchant

    invoice = get_object_or_404(
        MerchantInvoice,
        id=invoice_id,
        merchant=merchant
    )

    if request.method == "POST":
        invoice.invoice_number = request.POST.get("invoice_number")
        invoice.description = request.POST.get("description", "")

        # Remove old items
        invoice.items.all().delete()

        total = 0
        items_desc = request.POST.getlist("item_description[]")
        items_qty = request.POST.getlist("item_quantity[]")
        items_price = request.POST.getlist("item_unit_price[]")

        for desc, qty, price in zip(items_desc, items_qty, items_price):
            qty = int(qty)
            price = float(price)

            MerchantInvoiceItem.objects.create(
                invoice=invoice,
                description=desc,
                quantity=qty,
                unit_price=price
            )
            total += qty * price

        invoice.total_amount = total
        invoice.save()

        return redirect("WA_provider:invoice_list")

    return render(request, "merchant_edit_invoice.html", {
        "merchant": merchant,
        "invoice": invoice
    })

@merchant_owner_required    
@login_required
def delete_invoice(request, invoice_id):
    merchant = request.merchant
    if not merchant:
        return redirect("WA_provider:merchant_dashboard")

    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        merchant=merchant
    )

    if request.method == "POST":
        invoice.delete()
        return redirect("merchant_invoices")  # change to your invoice list url name

    return render(request, "confirm_delete.html", {
        "object": invoice,
        "type": "Invoice"
    })

@merchant_owner_required    
@login_required
def payout_list(request):
    merchant = request.merchant
    if not merchant:
        return redirect("merchant_register")

    # Handle payout request
    if request.method == "POST":
        amount = Decimal(request.POST.get("amount", "0"))  # convert to Decimal
        method = request.POST.get("method", "lypay")  # default LyPay
        reference = request.POST.get("reference", "")

        # Validate requested amount
        if amount > 0 and amount <= merchant.balance_available:
            Payout.objects.create(
                merchant=merchant,
                amount=amount,
                method=method,
                reference=reference,
                status="pending",
            )
            # Deduct from available balance immediately (Decimal - Decimal)
            merchant.balance_available -= amount
            merchant.save()
            return redirect("WA_provider:payout_list")
        else:
            error = "Invalid amount. Must be positive and <= available balance."
            payouts = merchant.payouts.all()
            return render(request, "merchant_payouts.html", {
                "merchant": merchant,
                "payouts": payouts,
                "error": error
            })
    # GET → show list + form
    payouts = merchant.payouts.all()
    return render(request, "merchant_payouts.html", {
        "merchant": merchant,
        "payouts": payouts
    })

@merchant_owner_required    
@login_required
def merchant_subscription(request):
    merchant = request.merchant
    
    # Safely get subscription
    try:
        subscription = merchant.subscription
    except MerchantSubscription.DoesNotExist:
        subscription = None

    # Show all active packages (for display purposes)
    packages = MerchantPackage.objects.filter(is_active=True)

    return render(request, "merchant_subscription.html", {
        "merchant": merchant,
        "subscription": subscription,
        "packages": packages
    })


@merchant_owner_required    
@login_required
def merchant_settings(request):
    merchant = request.merchant
    if request.method == "POST":
        # update merchant info
        merchant.name = request.POST.get("name")
        merchant.phone = request.POST.get("phone")
        merchant.email = request.POST.get("email")
        merchant.city = request.POST.get("city")
        merchant.address = request.POST.get("address")
        merchant.save()
        return redirect("merchant_settings")
    return render(request, "merchant_settings.html", {"merchant": merchant})



@login_required
def merchant_onboarding(request):
    # Get or create merchant
    merchant, created = Merchant.objects.get_or_create(
        owner=request.user,
        defaults={'status': 'draft', 'onboarding_step': 'basic_info'}
    )

    # If onboarding already completed
    if merchant.status != 'draft' and merchant.onboarding_step == 'completed':
        messages.info(request, "Onboarding already completed!")
        return redirect('WA_provider:merchant_dashboard')

    # Define onboarding steps
    steps = [
        ('basic_info', 'Basic Info'),
        ('verification', 'Verification'),
        ('bank_details', 'Bank Details'),
        ('subscription', 'Subscription'),
        ('completed', 'Completed')
    ]

    # Current step from query string or DB
    current_step = request.GET.get('step')
    if not current_step:  # empty or None
        current_step = merchant.onboarding_step

    # Handle POST submissions
    if request.method == 'POST':
        if current_step == 'basic_info':
            form = MerchantBasicInfoForm(request.POST, instance=merchant)
            if form.is_valid():
                merchant = form.save(commit=False)
                merchant.onboarding_step = 'verification'  # always update step
                merchant.status = 'draft'
                merchant.save()

                # Set user as merchant
                request.user.is_marchent = True
                request.user.save()

                messages.success(request, "Basic information saved successfully!")
                return redirect(f"{request.path}?step=verification")

        elif current_step == 'verification':
            form = MerchantVerificationForm(request.POST, request.FILES, instance=merchant)
            if form.is_valid():
                merchant = form.save(commit=False)
                merchant.onboarding_step = 'bank_details'
                merchant.save()
                messages.success(request, "Documents uploaded successfully!")
                return redirect(f"{request.path}?step=bank_details")

        elif current_step == 'bank_details':
            form = MerchantBankDetailsForm(request.POST, instance=merchant)
            if form.is_valid():
                merchant = form.save(commit=False)
                merchant.onboarding_step = 'subscription'
                merchant.save()
                messages.success(request, "Bank details saved successfully!")
                return redirect(f"{request.path}?step=subscription")


        elif current_step == 'subscription':
            form = SubscriptionSelectionForm(request.POST)
            if form.is_valid():
                package = form.cleaned_data['package']

                # Try to get existing subscription
                subscription, created = MerchantSubscription.objects.get_or_create(
                    merchant=merchant,
                    defaults={
                        'package': package,
                        'expires_at': timezone.now() + timedelta(days=30),
                        'is_active': True
                    }
                )
                if not created:
                    # Update existing subscription if it already exists
                    subscription.package = package
                    subscription.expires_at = timezone.now() + timedelta(days=30)
                    subscription.is_active = True
                    subscription.save()

                # Mark onboarding complete
                merchant.onboarding_step = 'completed'
                merchant.status = 'pending'
                merchant.save()

                messages.success(request, "Subscription activated! Account pending review.")
                return redirect(f"{request.path}?step=completed")


    # GET requests - show forms
    else:
        if current_step == 'basic_info':
            form = MerchantBasicInfoForm(instance=merchant)
        elif current_step == 'verification':
            form = MerchantVerificationForm(instance=merchant)
        elif current_step == 'bank_details':
            form = MerchantBankDetailsForm(instance=merchant)
        elif current_step == 'subscription':
            form = SubscriptionSelectionForm()
        elif current_step == 'completed':
            return render(request, "merchant_onboarding_completed.html", {
                "merchant": merchant,
                "steps": steps,
                "current_step": current_step
            })
        else:
            messages.error(request, "Invalid step!")
            return redirect(f"{request.path}?step=basic_info")

    return render(request, "merchant_onboarding.html", {
        "form": form,
        "merchant": merchant,
        "steps": steps,
        "current_step": current_step
    })

# views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, Q, F, ExpressionWrapper, FloatField
from django.utils import timezone
from datetime import timedelta, datetime
import json
from decimal import Decimal

@login_required
@merchant_owner_required
def merchant_analytics(request):
    merchant = request.merchant
    period = request.GET.get('period', '30d')
    
    # Calculate date range
    now = timezone.now()
    period_mapping = {
        '7d': (7, "Last 7 days"),
        '30d': (30, "Last 30 days"),
        '90d': (90, "Last 90 days"),
        'year': (365, "Last year"),
    }
    
    days, period_name = period_mapping.get(period, (30, "Last 30 days"))
    start_date = now - timedelta(days=days)
    
    # Get all transactions in period for various calculations
    all_transactions = merchant.transactions.filter(created_at__gte=start_date)
    paid_transactions = all_transactions.filter(status='paid')
    
    # Basic metrics with error handling
    revenue_agg = paid_transactions.aggregate(
        total_revenue=Sum('amount'),
        net_revenue=Sum('net_amount'),
        total_plutu_fee=Sum('plutu_fee'),
        total_platform_fee=Sum('platform_fee')
    )
    
    total_revenue = revenue_agg['total_revenue'] or Decimal('0')
    net_revenue = revenue_agg['net_revenue'] or Decimal('0')
    total_fees = (revenue_agg['total_plutu_fee'] or Decimal('0')) + \
                 (revenue_agg['total_platform_fee'] or Decimal('0'))
    
    transaction_count = paid_transactions.count()
    
    # Average transaction with safe division
    avg_transaction = paid_transactions.aggregate(avg=Avg('amount'))['avg'] or Decimal('0')
    
    # Daily revenue data for chart (optimized with list comprehension)
    daily_data = []
    date_range_days = min(days, 365)  # Cap at 1 year for performance
    
    for day_offset in range(date_range_days + 1):
        current_date = start_date + timedelta(days=day_offset)
        if current_date > now:
            break
            
        next_date = current_date + timedelta(days=1)
        day_transactions = paid_transactions.filter(
            created_at__gte=current_date,
            created_at__lt=next_date
        )
        
        day_revenue = day_transactions.aggregate(
            Sum('amount')
        )['amount__sum'] or Decimal('0')
        
        daily_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'day_label': current_date.strftime('%b %d'),
            'revenue': float(day_revenue),
            'count': day_transactions.count()
        })
    
    # Top performing payment links (with transaction count)
    top_links = merchant.payment_links.filter(
        transaction__status='paid',
        transaction__created_at__gte=start_date
    ).annotate(
        paid_count=Count('transaction', filter=Q(transaction__status='paid')),
        total_revenue=Sum('transaction__amount', filter=Q(transaction__status='paid')),
        last_transaction=Max('transaction__created_at', filter=Q(transaction__status='paid'))
    ).distinct().filter(paid_count__gt=0).order_by('-total_revenue')[:10]
    
    # Transaction status breakdown with percentage
    status_data = all_transactions.values('status').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    ).order_by('-count')
    
    total_all_transactions = all_transactions.count()
    
    status_breakdown = []
    for status in status_data:
        percentage = (status['count'] / total_all_transactions * 100) if total_all_transactions > 0 else 0
        status_breakdown.append({
            'status': status['status'],
            'count': status['count'],
            'total_amount': status['total_amount'] or Decimal('0'),
            'percentage': round(percentage, 1)
        })
    
    # Payment link performance with conversion rate
    payment_link_stats = merchant.payment_links.annotate(
        total_transactions=Count('transaction'),
        total_paid=Count('transaction', filter=Q(transaction__status='paid')),
        total_failed=Count('transaction', filter=Q(transaction__status='failed')),
        total_refunded=Count('transaction', filter=Q(transaction__status='refunded')),
    ).annotate(
        conversion_rate=ExpressionWrapper(
            Case(
                When(total_transactions=0, then=0.0),
                default=F('total_paid') * 100.0 / F('total_transactions'),
                output_field=FloatField()
            ),
            output_field=FloatField()
        )
    ).filter(total_paid__gt=0).order_by('-conversion_rate')[:5]
    
    # Calculate trends (comparing with previous period)
    previous_start_date = start_date - timedelta(days=days)
    previous_paid_transactions = merchant.transactions.filter(
        status='paid',
        created_at__gte=previous_start_date,
        created_at__lt=start_date
    )
    
    previous_revenue = previous_paid_transactions.aggregate(
        Sum('amount')
    )['amount__sum'] or Decimal('0')
    
    previous_count = previous_paid_transactions.count()
    
    # Calculate percentage changes
    revenue_change = 0
    if previous_revenue > 0:
        revenue_change = ((total_revenue - previous_revenue) / previous_revenue * 100)
    
    transaction_change = 0
    if previous_count > 0:
        transaction_change = ((transaction_count - previous_count) / previous_count * 100)
    
    # Overall conversion rate
    overall_conversion_rate = (transaction_count / total_all_transactions * 100) \
        if total_all_transactions > 0 else 0
    
    # Get today's performance
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_transactions = paid_transactions.filter(created_at__gte=today_start)
    today_revenue = today_transactions.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    today_count = today_transactions.count()
    
    # Get yesterday's performance for comparison
    yesterday_start = today_start - timedelta(days=1)
    yesterday_end = today_start
    yesterday_transactions = paid_transactions.filter(
        created_at__gte=yesterday_start,
        created_at__lt=yesterday_end
    )
    yesterday_revenue = yesterday_transactions.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    context = {
        "merchant": merchant,
        "period": period,
        "period_name": period_name,
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": now.strftime('%Y-%m-%d'),
        "today_date": now.strftime('%Y-%m-%d'),
        
        # Metrics
        "total_revenue": total_revenue,
        "net_revenue": net_revenue,
        "total_fees": total_fees,
        "transaction_count": transaction_count,
        "avg_transaction": avg_transaction,
        
        # Today's metrics
        "today_revenue": today_revenue,
        "today_count": today_count,
        "yesterday_revenue": yesterday_revenue,
        
        # Trends
        "revenue_change": round(revenue_change, 1),
        "transaction_change": round(transaction_change, 1),
        
        # Chart data
        "daily_data_json": json.dumps(daily_data),
        
        # Breakdowns
        "top_links": top_links,
        "status_breakdown": status_breakdown,
        "payment_link_stats": payment_link_stats,
        
        # Conversion rate
        "conversion_rate": round(overall_conversion_rate, 1),
        
        # For template calculations
        "total_all_transactions": total_all_transactions,
    }
    
    return render(request, "merchant_analytics.html", context)