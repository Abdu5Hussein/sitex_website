from django.shortcuts import render, redirect , get_object_or_404
from django.contrib.auth import authenticate, login, logout
from .models import Product, Branch, Inquiry,Invoice, ContactMessage,Banner, Category, City, Project , brand, MessagePackage
from django.http import JsonResponse
from django.views.decorators.http import require_GET

def home(request):
    return render(request, 'main/home.html')

def about(request):
    return render(request, 'main/about.html')

def shop(request):
    return render(request, 'main/shop.html')

def view_cart(request):
    return render(request, 'main/cart.html')


def products(request):
    products = Product.objects.all()
    return render(request, 'main/products.html', {'products': products})

def sitex_invoice(request):
    return render(request, 'main/sitex-invoice.html')

def website_calculator(request):
    return render(request, 'main/website-calculator.html')

def categories(request):
    categories = Category.objects.all()

    # wa_packages = [
    #     {"name": "Basic WA Pack", "messages": 250, "price": 50, "plan_code": "basic"},
    #     {"name": "Standard WA Pack", "messages": 650, "price": 100, "plan_code": "standard"},
    #     {"name": "Premium WA Pack", "messages": 1000, "price": 150, "plan_code": "premium"},
    # ]
    wa_packages = [
        {"name": pack.name, "messages": pack.message_count, "price": pack.price, "plan_code": pack.plan_code}
        for pack in MessagePackage.objects.filter(is_active=True)
    ]

    return render(request, 'main/categories.html', {
        'categories': categories,
        'wa_packages': wa_packages
    })


def contact(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        message = request.POST.get('message')
        ContactMessage.objects.create(
            user=request.user if request.user.is_authenticated else None,
            email=email,
            message=message
        )
        return redirect('contact')

    # Get all branches to display on the map
    branches = Branch.objects.all()

    return render(request, 'main/contact.html', {
        'branches': branches
    })

def clients(request):
    projects = Project.objects.filter(is_public=True).order_by("sort_order", "-created_at")[:12]
    return render(request, "main/clients.html", {"projects": projects})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_active:
            login(request, user)

            # Redirect based on user type
            if user.is_admin:
                return redirect('admin:index')  # default Django admin
            elif user.is_client:
                return redirect('WA_provider:dashboard')  # client dashboard
            elif user.is_wa_provider_user:
                return redirect('WA_provider:employee_dashboard')  # WA provider employee dashboard
            elif user.is_company_user:
                return redirect('company:dashboard')  # company dashboard
            else:
                messages.info(request, "Logged in, but no dashboard assigned.")
                return redirect('/')

        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'main/login.html')

def logout_view(request):
    logout(request)
    return redirect('home')

from .models import Invoice  # make sure you have this import at the top

def dashboard(request):
    if not request.user.is_authenticated or not request.user.is_admin:
        return redirect('login')

    products = Product.objects.all()
    inquiries = Inquiry.objects.all()
    messages = ContactMessage.objects.all()
    branches = Branch.objects.all()
    categories = Category.objects.all()
    banners = Banner.objects.all()
    cities = City.objects.all()
    brands = brand.objects.all()  # <-- new line

    invoices = Invoice.objects.prefetch_related('items').all()

    return render(
        request,
        'main/dashboard.html',
        {
            'products': products,
            'inquiries': inquiries,
            'messages': messages,
            'branches': branches,
            'categories': categories,
            'invoices': invoices,  # use lowercase variable
            'banners': banners,
            'cities': cities,
            'brands': brands,  # <-- pass to template


        }
    )


@require_GET
def get_products_api(request):
    products = Product.objects.all().values(
        'id', 'name', 'description', 'quantity_available',
        'price', 'image', 'show_quantity', 'show_price', 'place_orders'
    )

    # Convert to list and handle image URLs
    products_list = list(products)
    for product in products_list:
        if product['image']:
            product['image'] = request.build_absolute_uri(product['image'])

    return JsonResponse(products_list, safe=False)


from django.templatetags.static import static  # make sure this is imported

def product_detail_view(request, product_id):
    """Render product detail page in new window"""

    product = get_object_or_404(
        Product.objects.select_related('category'),
        id=product_id
    )

    category = product.category

    # Similar products
    if category:
        similar_products = Product.objects.filter(
            category=category
        ).exclude(id=product_id).order_by('?')[:4]

        category_products = Product.objects.filter(
            category=category
        ).exclude(id=product_id).order_by('-id')[:8]
    else:
        similar_products = []
        category_products = []

    categories = Category.objects.all()

    # 👉 get extra images
    extra_images = product.additional_images.all()

    # Build media items (for gallery if you want to use it)
    media_items = []

    # Main image first (if exists)
    if product.image:
        media_items.append({
            "type": "image",
            "url": product.image.url,
            "is_main": True,
        })

    # Additional images
    for img in extra_images:
        if img.image:
            media_items.append({
                "type": "image",
                "url": img.image.url,
                "is_main": False,
            })

    # Video
    if product.video:
        media_items.append({
            "type": "video",
            "url": product.video.url,
            "thumbnail": product.image.url if product.image else static("main/img/video-thumb.jpg"),
        })

    # Fallback if absolutely nothing
    if not media_items:
        media_items.append({
            "type": "image",
            "url": static("main/img/product-default.jpg"),
            "is_main": True,
        })

    context = {
        "product": product,
        "similar_products": similar_products,
        "category_products": category_products,
        "categories": categories,
        "media_items": media_items,
        "extra_images": extra_images,  # 👉 add this

        "has_video": bool(product.video),
        "in_stock": product.quantity_available > 0,
        "can_order": product.place_orders and product.quantity_available > 0,
        "show_price": product.show_price and product.price is not None,
        "show_quantity": product.show_quantity,
    }

    return render(request, "main/product_detail.html", context)


def get_product_api(request, product_id):
    product = get_object_or_404(Product.objects.select_related('category'), id=product_id)

    data = {
        "success": True,                "url": "/static/main/img/product-default.jpg",

        "product": {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "quantity_available": product.quantity_available if product.show_quantity else None,
            "price": str(product.price) if product.show_price and product.price else None,
            "image_url": product.image.url if product.image else None,
            "video_url": product.video.url if product.video else None,
            "place_orders": product.place_orders,
            "category": {
                "id": product.category.id if product.category else None,
                "name": product.category.name if product.category else None,
            },
        }
    }
    return JsonResponse(data)



def t404_view(request, exception=None):
    return render(request, 'main/404.html', status=404)