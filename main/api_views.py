from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Product, Branch, Category ,Invoice ,InvoiceItem,Banner,City
from .serializers import ProductSerializer,ProductSerializer1, BranchSerializer ,InquirySerializer,CategorySerializer
from rest_framework.permissions import AllowAny
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt  # optional if you handle CSRF in JS
from django.http import JsonResponse
from django.db.models import Count, Min, Max, Q,F
from django.core.paginator import Paginator
import json
from django.contrib.postgres.search import TrigramSimilarity
from django.utils.text import slugify
from decimal import Decimal, InvalidOperation
from django.templatetags.static import static
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from .models import Product, Category, images  # note: `images` model
from .serializers import ProductSerializer
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def create_product(request):
    if not request.user.is_admin:
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )

    # --- Make a plain dict from request.data ---
    data = {k: v for k, v in request.data.items()}

    # --- Category handling ---
    category_id = data.get('category')
    if category_id:
        try:
            category_instance = Category.objects.get(id=int(category_id))
            data['category'] = category_instance.id
        except Category.DoesNotExist:
            return Response({'error': 'Invalid category'}, status=status.HTTP_400_BAD_REQUEST)

    # --- Images handling ---
    uploaded_images = request.FILES.getlist('images')
    main_image_file = uploaded_images[0] if uploaded_images else None
    extra_image_files = uploaded_images[1:] if uploaded_images else []

    # --- Video handling (optional) ---
    video_file = request.FILES.get('video')  # will be None if not provided

    data.pop('images', None)
    data.pop('video', None)  # remove if serializer doesn't expect it

    serializer = ProductSerializer(data=data)

    with transaction.atomic():
        if serializer.is_valid():
            product_kwargs = {}
            if main_image_file:
                product_kwargs['image'] = main_image_file
            if video_file:
                product_kwargs['video'] = video_file  # only pass if present

            product = serializer.save(**product_kwargs)

            # Extra images
            for img_file in extra_image_files:
                images.objects.create(product=product, image=img_file)

            return Response({'success': True, 'id': product.id}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_branch(request):
    if not request.user.is_admin:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    serializer = BranchSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
@permission_classes([AllowAny])  # allow both authenticated + guest
def create_inquiry(request):

    data = request.data.copy()

    # If logged in → use real user
    if request.user.is_authenticated:
        data['user'] = request.user.id
        data['guest_id'] = None
    else:
        # Guest → assign random guest id
        import uuid
        data['guest_id'] = str(uuid.uuid4())
        data['user'] = None

    serializer = InquirySerializer(data=data)

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)

    return Response(serializer.errors, status=400)


@api_view(['GET'])
def branch_list_api(request):
    branches = Branch.objects.all()
    print("Branches count:", branches.count())
    serializer = BranchSerializer(branches, many=True)
    return Response(serializer.data)



@api_view(['GET'])
def product_list_api(request):
    products = Product.objects.all()[:4]  # only fetch 4 products
    serializer = ProductSerializer1(products, many=True, context={'request': request})
    return Response(serializer.data)
@require_http_methods(["GET", "POST"])
def product_detail_api(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "GET":
        categories = Category.objects.all()
        categories_data = [
            {"id": c.id, "name": c.name, "slug": c.slug} for c in categories
        ]

        # Extra gallery images (from separate images model)
        extra_images_qs = images.objects.filter(product=product)
        gallery_images = [
            {
                "id": img.id,
                "image_url": img.image.url,
            }
            for img in extra_images_qs
            if img.image
        ]

        return JsonResponse({
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "quantity_available": product.quantity_available,
            "price": str(product.price) if product.price is not None else "",
            "image_url": product.image.url if product.image else "",
            "video_url": product.video.url if product.video else "",
            "show_quantity": product.show_quantity,
            "show_price": product.show_price,
            "place_orders": product.place_orders,
            "category": {
                "id": product.category.id if product.category else None,
                "name": product.category.name if product.category else None,
                "slug": product.category.slug if product.category else None,
            },
            "all_categories": categories_data,
            "gallery_images": gallery_images,  # <-- NEW
        })

    # POST = update
    data = request.POST
    files = request.FILES

    # Text fields
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()

    # Numeric fields
    try:
        quantity_available = int(data.get("quantity_available", 0))
    except Exception:
        quantity_available = 0

    try:
        price = float(data.get("price")) if data.get("price") else None
    except Exception:
        price = None

    # Booleans (checkbox-style)
    show_quantity = data.get("show_quantity") in ("true", "1", "on", "yes")
    show_price = data.get("show_price") in ("true", "1", "on", "yes")
    place_orders = data.get("place_orders") in ("true", "1", "on", "yes")

    # Category
    category_id = data.get("category")
    category = None
    if category_id:
        try:
            category = Category.objects.get(id=int(category_id))
        except Category.DoesNotExist:
            category = None

    # Assign basic fields
    product.name = name
    product.description = description
    product.quantity_available = quantity_available
    product.price = price
    product.show_quantity = show_quantity
    product.show_price = show_price
    product.place_orders = place_orders
    product.category = category

    # --- File handling ---

    # Multiple images (same field name you used in the modals: `images`)
    images_list = files.getlist("images")

    if images_list:
        # First image is the new main product image
        product.image = images_list[0]

        # Replace gallery images with the rest
        images.objects.filter(product=product).delete()
        for img_file in images_list[1:]:
            images.objects.create(product=product, image=img_file)
    else:
        # Fallback: support old single field "image" if present
        if "image" in files:
            product.image = files["image"]

    # Single video (still one file)
    if "video" in files:
        product.video = files["video"]

    product.save()

    return JsonResponse({"success": True, "id": product.id})


@require_http_methods(["POST"])
def product_delete_api(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    return JsonResponse({"success": True})

@require_http_methods(["GET", "POST"])
def branch_detail_api(request, pk):
    branch = get_object_or_404(Branch, pk=pk)

    if request.method == "GET":
        return JsonResponse({
            "id": branch.id,
            "name": branch.name or "",
            "phone_number": branch.phone_number or "",
            "Email_Adress": branch.Email_Adress or "",
            "address": branch.address or "",
            "latitude": float(branch.latitude) if branch.latitude is not None else None,
            "longitude": float(branch.longitude) if branch.longitude is not None else None,
            "opening_hours": branch.opening_hours or "",
            "closing_hours": branch.closing_hours or "",
            "day_from": branch.day_from or "",
            "day_to": branch.day_to or "",
            "facbook_link": branch.facbook_link or "",
            "instagram_link": branch.instagram_link or "",
            "twitter_link": branch.twitter_link or "",
            "linkdin_link": branch.linkdin_link or "",
            "primery_branch": bool(branch.primery_branch),
        })

    # POST = update
    data = request.POST

    branch.name = data.get("name", "").strip()
    branch.phone_number = data.get("phone_number", "").strip()
    branch.Email_Adress = data.get("Email_Adress", "").strip()
    branch.address = data.get("address", "").strip()

    # latitude
    lat = data.get("latitude")
    if lat not in (None, ""):
        try:
            branch.latitude = float(lat)
        except ValueError:
            # keep old value or set to None depending on your preference
            pass
    else:
        branch.latitude = None

    # longitude
    lng = data.get("longitude")
    if lng not in (None, ""):
        try:
            branch.longitude = float(lng)
        except ValueError:
            pass
    else:
        branch.longitude = None

    branch.opening_hours = data.get("opening_hours", "").strip()
    branch.closing_hours = data.get("closing_hours", "").strip()
    branch.day_from = data.get("day_from", "").strip()
    branch.day_to = data.get("day_to", "").strip()

    branch.facbook_link = data.get("facbook_link", "").strip()
    branch.instagram_link = data.get("instagram_link", "").strip()
    branch.twitter_link = data.get("twitter_link", "").strip()
    branch.linkdin_link = data.get("linkdin_link", "").strip()

    # primery_branch comes as "true"/"false" (from FormData.set) or "on" (from checkbox)
    primery = data.get("primery_branch")
    if primery is not None:
        branch.primery_branch = str(primery).lower() in ("true", "1", "on", "yes")
        # if setting this branch as primary, unset others
        if branch.primery_branch:
            Branch.objects.exclude(pk=branch.pk).update(primery_branch=False)

    branch.save()

    return JsonResponse({"success": True})


@require_http_methods(["POST"])
def branch_delete_api(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    branch.delete()
    return JsonResponse({"success": True})

@require_http_methods(["GET"])
def get_primary_branch(request):
    branch = Branch.objects.filter(primery_branch=True).first()
    if not branch:
        return JsonResponse({"error": "No primary branch found"}, status=404)

    return JsonResponse({
        "id": branch.id,
        "name": branch.name or "Not Set",
        "phone_number": branch.phone_number or "Not Set",
        "Email_Adress": branch.Email_Adress or "Not Set",
        "address": branch.address or "Not Set",
        "latitude": float(branch.latitude) if branch.latitude is not None else None,
        "longitude": float(branch.longitude) if branch.longitude is not None else None,
        "opening_hours": branch.opening_hours or "Not Set",
        "closing_hours": branch.closing_hours or "Not Set",
        "day_from": branch.day_from or "Not Set",
        "day_to": branch.day_to or "Not Set",
        "facbook_link": branch.facbook_link or "#",
        "instagram_link": branch.instagram_link or "#",
        "twitter_link": branch.twitter_link or "#",
        "linkdin_link": branch.linkdin_link or "#",
        "primery_branch": bool(branch.primery_branch),
    })

# -----------------------------
# Create Category
# -----------------------------
@csrf_exempt
def category_add(request):
    if request.method == "POST":
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        description = request.POST.get('description')
        image = request.FILES.get('image')

        if Category.objects.filter(name=name).exists():
            return JsonResponse({'success': False, 'error': 'Category already exists'})

        category = Category.objects.create(
            name=name,
            slug=slug,
            description=description,
            image=image
        )
        return JsonResponse({'success': True, 'id': category.id})


@require_http_methods(["POST"])
def category_update(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    image = request.FILES.get('image')

    if not name:
        return JsonResponse(
            {'success': False, 'error': 'Name is required'},
            status=400
        )

    category.name = name
    category.slug = slugify(name)  # auto-generate slug
    category.description = description

    if image:
        category.image = image

    category.save()
    return JsonResponse({'success': True})

# -----------------------------
# Delete Category
# -----------------------------
@csrf_exempt
def category_delete(request, category_id):
    if request.method == "POST":
        try:
            category = Category.objects.get(id=category_id)
            category.delete()
            return JsonResponse({'success': True})
        except Category.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Category not found'})

# -----------------------------
# Category Detail (unchanged)
# -----------------------------
def category_detail(request, category_id):
    try:
        category = Category.objects.get(id=category_id)
        data = {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "slug": category.slug,
            "image_url": category.image.url if category.image else None,
        }
        return JsonResponse(data)
    except Category.DoesNotExist:
        return JsonResponse({"error": "Category not found"}, status=404)



# Fetch all categories
@api_view(['POST'])
@permission_classes([AllowAny])
def api_categories(request):
    categories = Category.objects.all()
    serializer = CategorySerializer(categories, many=True, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)

# Fetch products by category slug
@api_view(['POST'])
@permission_classes([AllowAny])
def api_products_by_category(request):
    slug = request.data.get('slug')
    if not slug:
        return Response({"error": "slug is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        category = Category.objects.get(slug=slug)
    except Category.DoesNotExist:
        return Response({"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)

    products = Product.objects.filter(category=category)
    serializer = ProductSerializer1(products, many=True, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def home_data(request):
    """Get all data needed for homepage"""
    try:
        # Featured products (products with images)
        featured_products = Product.objects.filter(
            image__isnull=False
        ).select_related('category')[:12]

        # Popular categories (categories with most products)
        popular_categories = Category.objects.annotate(
            product_count=Count('products')
        ).filter(product_count__gt=0).order_by('-product_count')[:8]

        # New arrivals (latest products)
        new_arrivals = Product.objects.order_by('-id')[:8]

        # All categories for filter
        all_categories = Category.objects.all()

        # Banners from database
        banners_qs = Banner.objects.filter(is_active=True).order_by('order')
        banners = []
        for b in banners_qs:
            banners.append({
                'id': b.id,
                'title': b.title,
                'subtitle': b.subtitle,
                'image': b.image.url if b.image else None,
                'button_text': b.button_text,
                'button_link': b.button_link,
                'text_color': b.text_color,
            })

        # 🔹 FEATURED PRODUCTS
        featured_data = [
            {
                'id': product.id,
                'name': product.name,
                'description': (
                    product.description[:100] + '...'
                    if product.description and len(product.description) > 100
                    else product.description
                ),
                'price': float(product.price) if product.price and product.show_price else None,
                'discount_percentage': float(product.discount_percentage or 0),  # 👈 NEW
                'image': product.image.url if product.image else None,
                'category': product.category.name if product.category else None,
                'category_slug': product.category.slug if product.category else None,
                'in_stock': product.place_orders and product.quantity_available > 0,
                'stock_quantity': product.quantity_available if product.show_quantity else None,
                'can_order': product.place_orders,
                'show_price': product.show_price,
                'show_quantity': product.show_quantity,
            }
            for product in featured_products
        ]

        # 🔹 ALL CATEGORIES
        categories_data = [
            {
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'description': category.description,
                'image': category.image.url if category.image else None,
                'product_count': category.products.count(),
            }
            for category in all_categories
        ]

        # 🔹 POPULAR CATEGORIES
        popular_categories_data = [
            {
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'product_count': category.product_count,
                'icon': get_category_icon(category.name),
            }
            for category in popular_categories
        ]

        # 🔹 NEW ARRIVALS
        new_arrivals_data = [
            {
                'id': product.id,
                'name': product.name,
                'description': (
                    product.description[:100] + '...'
                    if product.description and len(product.description) > 100
                    else product.description
                ),
                'price': float(product.price) if product.price and product.show_price else None,
                'discount_percentage': float(product.discount_percentage or 0),  # 👈 NEW
                'image': product.image.url if product.image else None,
                'category': product.category.name if product.category else None,
                'category_slug': product.category.slug if product.category else None,
                'in_stock': product.place_orders and product.quantity_available > 0,
                'stock_quantity': product.quantity_available if product.show_quantity else None,
                'can_order': product.place_orders,
                'show_price': product.show_price,
                'show_quantity': product.show_quantity,
            }
            for product in new_arrivals
        ]

        response_data = {
            'success': True,
            'featured_products': featured_data,
            'categories': categories_data,
            'popular_categories': popular_categories_data,
            'new_arrivals': new_arrivals_data,
            'banners': banners,
            'stats': {
                'total_products': Product.objects.count(),
                'total_categories': Category.objects.count(),
                'featured_count': len(featured_data),
            }
        }

        return Response(response_data)

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def search_products(request):
    """Search products with filters"""
    try:
        data = request.data
        query = data.get('query', '').strip()
        category_slug = data.get('category', '')
        min_price = data.get('min_price')
        max_price = data.get('max_price')
        in_stock = data.get('in_stock')
        sort_by = data.get('sort_by', 'newest')
        page = int(data.get('page', 1))
        page_size = int(data.get('page_size', 12))

        # Start with all products
        products = Product.objects.select_related('category').all()

        # Apply filters
        if query:
            products = products.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(category__name__icontains=query)
            )

        if category_slug and category_slug != 'all':
            products = products.filter(category__slug=category_slug)

        if min_price is not None:
            products = products.filter(price__gte=min_price)

        if max_price is not None:
            products = products.filter(price__lte=max_price)

        if in_stock:
            products = products.filter(quantity_available__gt=0)

        # Apply sorting
        if sort_by == 'price_low':
            products = products.order_by('price')
        elif sort_by == 'price_high':
            products = products.order_by('-price')
        elif sort_by == 'name':
            products = products.order_by('name')
        elif sort_by == 'popular':  # Can be extended with view counts
            products = products.order_by('-id')
        else:  # newest
            products = products.order_by('-id')

        # Pagination
        paginator = Paginator(products, page_size)
        total_pages = paginator.num_pages
        current_page = paginator.page(page)
        product_list = current_page.object_list

        # Serialize
        products_data = []
        for product in product_list:
            products_data.append({
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': float(product.price) if product.price and product.show_price else None,
                'image': product.image.url if product.image else None,
                'video': product.video.url if product.video else None,
                'category': {
                    'id': product.category.id if product.category else None,
                    'name': product.category.name if product.category else None,
                    'slug': product.category.slug if product.category else None,
                },
                'quantity_available': product.quantity_available,
                'show_price': product.show_price,
                'show_quantity': product.show_quantity,
                'place_orders': product.place_orders,
                'in_stock': product.quantity_available > 0,
                'can_order': product.place_orders and product.quantity_available > 0,
                'rating': 4.5,  # Can be extended
                'review_count': 24,  # Can be extended
            })

        return Response({
            'success': True,
            'products': products_data,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_items': paginator.count,
                'has_next': current_page.has_next(),
                'has_previous': current_page.has_previous(),
            },
            'filters': {
                'query': query,
                'category': category_slug,
                'min_price': min_price,
                'max_price': max_price,
                'in_stock': in_stock,
                'sort_by': sort_by,
            }
        })

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_categories(request):
    """Get all categories"""
    categories = Category.objects.annotate(
        product_count=Count('products')
    ).all()

    categories_data = []
    for i, category in enumerate(categories):
        categories_data.append({
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'description': category.description,
            'image': category.image.url if category.image else None,
            'product_count': category.product_count,
            'icon': get_category_icon(category.name),
            'color_class': f'cat-color-{(i % 6) + 1}',
        })

    return Response({
        'success': True,
        'categories': categories_data,
        'total': len(categories_data),
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def get_product_detail(request, product_id):
    """Get product details"""
    product = get_object_or_404(Product, id=product_id)

    # Get related products (same category)
    related_products = Product.objects.filter(
        category=product.category
    ).exclude(id=product_id)[:4]

    related_data = []
    for p in related_products:
        related_data.append({
            'id': p.id,
            'name': p.name,
            'price': float(p.price) if p.price and p.show_price else None,
            'image': p.image.url if p.image else None,
            'in_stock': p.quantity_available > 0,
        })

    return Response({
        'success': True,
        'product': {
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'full_description': product.description,  # Can have separate field
            'price': float(product.price) if product.price and product.show_price else None,
            'original_price': None,  # Can be extended for discounts
            'image': product.image.url if product.image else None,
            'video': product.video.url if product.video else None,
            'category': {
                'id': product.category.id if product.category else None,
                'name': product.category.name if product.category else None,
                'slug': product.category.slug if product.category else None,
            },
            'quantity_available': product.quantity_available,
            'show_price': product.show_price,
            'show_quantity': product.show_quantity,
            'place_orders': product.place_orders,
            'in_stock': product.quantity_available > 0,
            'can_order': product.place_orders and product.quantity_available > 0,
            'specifications': {},  # Can be extended
            'images': [product.image.url] if product.image else [],  # Can have multiple images
            'rating': 4.5,
            'review_count': 24,
            'sold_count': 125,
            'wishlist_count': 45,
        },
        'related_products': related_data,
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def quick_view(request):
    """Quick view for product"""
    product_id = request.data.get('product_id')
    product = get_object_or_404(Product, id=product_id)

    return Response({
        'success': True,
        'product': {
            'id': product.id,
            'name': product.name,
            'description': (
                product.description[:150] + '...'
                if product.description and len(product.description) > 150
                else product.description
            ),
            'price': float(product.price) if product.price and product.show_price else None,
            'discount_percentage': float(product.discount_percentage or 0),  # 👈 ADD THIS
            'image': product.image.url if product.image else None,
            'in_stock': product.quantity_available > 0,
            'stock': product.quantity_available if product.show_quantity else None,
            'can_order': product.place_orders and product.quantity_available > 0,
            'category': product.category.name if product.category else None,
            'show_price': product.show_price,
        }
    })


# Helper function
def get_category_icon(category_name):
    """Get FontAwesome icon for category"""
    icons = {
        'electronics': 'fas fa-laptop',
        'clothing': 'fas fa-tshirt',
        'shoes': 'fas fa-shoe-prints',
        'bags': 'fas fa-shopping-bag',
        'accessories': 'fas fa-glasses',
        'beauty': 'fas fa-spa',
        'home': 'fas fa-home',
        'kitchen': 'fas fa-utensils',
        'sports': 'fas fa-running',
        'books': 'fas fa-book',
        'toys': 'fas fa-gamepad',
        'jewelry': 'fas fa-gem',
        'watches': 'fas fa-clock',
        'phones': 'fas fa-mobile-alt',
        'computers': 'fas fa-desktop',
        'gaming': 'fas fa-gamepad',
        'furniture': 'fas fa-couch',
        'decor': 'fas fa-paint-roller',
    }

    name_lower = category_name.lower()
    for key, icon in icons.items():
        if key in name_lower:
            return icon

    return 'fas fa-shopping-bag'




@api_view(['GET'])
@permission_classes([AllowAny])
def shop_page_data(request):
    """Get data for shop page with pagination"""
    try:
        # Get query parameters safely
        category_slug = request.GET.get('category', '')
        search_query = request.GET.get('search', '')
        min_price_param = request.GET.get('min_price')
        max_price_param = request.GET.get('max_price')
        in_stock = request.GET.get('in_stock')
        sort_by = request.GET.get('sort_by', 'newest')

        # Safe conversion for page
        page_param = request.GET.get('page', '1')
        try:
            page = int(page_param)
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        # Safe conversion for min/max price
        try:
            min_price = float(min_price_param) if min_price_param is not None else None
        except (ValueError, TypeError):
            min_price = None

        try:
            max_price = float(max_price_param) if max_price_param is not None else None
        except (ValueError, TypeError):
            max_price = None

        # Start with all products
        products = Product.objects.select_related('category').all()

        # Apply filters
        if category_slug and category_slug != 'all':
            products = products.filter(category__slug=category_slug)

        if search_query:
            products = products.annotate(
                similarity_name=TrigramSimilarity('name', search_query),
                similarity_description=TrigramSimilarity('description', search_query),
                similarity_category=TrigramSimilarity('category__name', search_query),
            ).filter(
                Q(similarity_name__gt=0.2) |
                Q(similarity_description__gt=0.2) |
                Q(similarity_category__gt=0.2)
            ).order_by(
                '-similarity_name', '-similarity_description', '-similarity_category'
            )

        if min_price is not None:
            products = products.filter(price__gte=min_price)

        if max_price is not None:
            products = products.filter(price__lte=max_price)

        if in_stock == 'true':
            products = products.filter(quantity_available__gt=0)
        elif in_stock == 'false':
            products = products.filter(quantity_available=0)

        # Apply sorting
        if sort_by == 'price_low':
            products = products.order_by('price')
        elif sort_by == 'price_high':
            products = products.order_by('-price')
        elif sort_by == 'name':
            products = products.order_by('name')
        elif sort_by == 'popular':
            products = products.order_by('-id')  # Can extend with views/sales
        elif sort_by == 'rating':
            products = products.order_by('-id')  # Can extend with ratings
        else:  # newest
            products = products.order_by('-id')

        # Pagination
        paginator = Paginator(products, 20)  # 20 items per page
        total_pages = paginator.num_pages
        try:
            current_page = paginator.page(page)
        except:
            current_page = paginator.page(1)
            page = 1

        product_list = current_page.object_list

        # Get categories for filter sidebar
        all_categories = Category.objects.annotate(
            product_count=Count('products')
        ).all()

        # Get price range for slider
        price_range = Product.objects.aggregate(
            min_price=Min('price'),
            max_price=Max('price')
        )

        # Serialize products
        products_data = []
        for product in product_list:
            # Media items (images + video)
            media_items = []
            if product.image:
                media_items.append({
                    'type': 'image',
                    'url': product.image.url,
                    'thumbnail': product.image.url,
                    'full': product.image.url,
                })
            if product.video:
                media_items.append({
                    'type': 'video',
                    'url': product.video.url,
                    'thumbnail': product.image.url if product.image else '/static/main/img/video-thumb.jpg',
                    'full': product.video.url,
                })
            if not media_items:
                media_items.append({
                    'type': 'image',
                    'url': '/static/main/img/product-default.jpg',
                    'thumbnail': '/static/main/img/product-default.jpg',
                    'full': '/static/main/img/product-default.jpg',
                })

            products_data.append({
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': float(product.price) if product.price and product.show_price else None,
                'media_items': media_items,
                'category': {
                    'id': product.category.id if product.category else None,
                    'name': product.category.name if product.category else None,
                    'slug': product.category.slug if product.category else None,
                },
                'quantity_available': product.quantity_available,
                'show_price': product.show_price,
                'show_quantity': product.show_quantity,
                'place_orders': product.place_orders,
                'in_stock': product.quantity_available > 0,
                'can_order': product.place_orders and product.quantity_available > 0,
                'rating': 4.5,
                'review_count': 24,
                'sold_count': 125,
                'is_new': product.id > Product.objects.count() - 50,  # Last 50 products are new
                'discount': None,
                'discount_percentage': float(getattr(product, 'discount_percentage', 0) or 0),
            })

        # Serialize categories
        categories_data = []
        for category in all_categories:
            categories_data.append({
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'count': category.product_count,
                'selected': category.slug == category_slug,
            })

        # Response
        response_data = {
            'success': True,
            'products': products_data,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_items': paginator.count,
                'has_next': current_page.has_next(),
                'has_previous': current_page.has_previous(),
            },
            'filters': {
                'categories': categories_data,
                'price_range': {
                    'min': float(price_range['min_price'] or 0),
                    'max': float(price_range['max_price'] or 1000),
                },
                'current': {
                    'category': category_slug,
                    'search': search_query,
                    'min_price': min_price,
                    'max_price': max_price,
                    'in_stock': in_stock,
                    'sort_by': sort_by,
                }
            },
            'stats': {
                'total_products': paginator.count,
                'showing': len(products_data),
            }
        }

        return Response(response_data)

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_shop_filters(request):
    """Get filter options for shop"""
    categories = Category.objects.annotate(
        product_count=Count('products')
    ).all()

    price_range = Product.objects.aggregate(
        min_price=Min('price'),
        max_price=Max('price')
    )

    categories_data = []
    for category in categories:
        categories_data.append({
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'count': category.product_count,
        })

    return Response({
        'success': True,
        'categories': categories_data,
        'price_range': {
            'min': float(price_range['min_price'] or 0),
            'max': float(price_range['max_price'] or 1000),
        }
    })


from decimal import Decimal, InvalidOperation

@csrf_exempt
def create_invoice(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    name = (data.get("name") or "").strip()
    address = (data.get("address") or "").strip()
    phone = (data.get("phone") or "").strip()
    items = data.get("items") or []

    city_id = data.get("city_id") or data.get("city")

    if not (name and address and phone and city_id and items):
        return JsonResponse({"error": "Missing fields"}, status=400)

    # 1) City & delivery fee
    try:
        city_obj = City.objects.get(pk=city_id)
    except City.DoesNotExist:
        return JsonResponse({"error": "Invalid city"}, status=400)

    delivery_fee = city_obj.delivery_fee or Decimal("0.00")

    # 2) Build items + subtotal + discount
    subtotal = Decimal("0.00")              # total after discount
    total_discount_amount = Decimal("0.00") # total discount for the invoice
    invoice_items = []

    try:
        for item in items:
            product_id = item["product_id"]
            quantity = int(item["quantity"])
            # original unit price
            price = Decimal(str(item["price"]))
            item_name = (item.get("name") or "").strip()

            # discount percentage (optional)
            raw_discount = item.get("discount_percentage", 0)
            discount_pct = Decimal(str(raw_discount or 0))

            if quantity <= 0:
                return JsonResponse({"error": "Quantity must be positive"}, status=400)

            if discount_pct < 0 or discount_pct > 100:
                return JsonResponse(
                    {"error": "Discount percentage must be between 0 and 100"},
                    status=400,
                )

            # discounted unit price
            discount_multiplier = (Decimal("100") - discount_pct) / Decimal("100")
            discounted_price = (price * discount_multiplier).quantize(Decimal("0.01"))

            line_total = discounted_price * quantity
            subtotal += line_total

            # line discount amount = (original - discounted) * quantity
            line_discount_amount = (price - discounted_price) * quantity
            total_discount_amount += line_discount_amount

            invoice_items.append(
                InvoiceItem(
                    invoice=None,  # attach later
                    product_id=product_id,
                    name=item_name,
                    quantity=quantity,
                    original_price=price,            # store original unit price
                    price=discounted_price,          # store discounted unit price
                    discount_percentage=discount_pct # snapshot of discount used
                )
            )
    except (KeyError, ValueError, TypeError, InvalidOperation) as e:
        return JsonResponse({"error": f"Invalid item data: {e}"}, status=400)

    # 3) Total = subtotal(after discount) + delivery fee
    total = subtotal + delivery_fee

    # 4) Create Invoice
    invoice = Invoice.objects.create(
        name=name,
        city=city_obj.name,
        address=address,
        phone=phone,
        delivery_fee=delivery_fee,
        total=total,
        discount_amount=total_discount_amount,  # 👈 use the field on Invoice
    )

    # 5) Attach items
    for inv_item in invoice_items:
        inv_item.invoice = invoice
    InvoiceItem.objects.bulk_create(invoice_items)

    return JsonResponse({
        "success": True,
        "invoice_id": invoice.id,
        "subtotal": str(subtotal),                  # after discount
        "delivery_fee": str(delivery_fee),
        "discount_amount": str(total_discount_amount),
        "total": str(total),
    })



@require_http_methods(["GET", "POST"])
def banner_detail_api(request, pk):
    banner = get_object_or_404(Banner, pk=pk)

    if request.method == "GET":
        return JsonResponse({
            "id": banner.id,
            "title": banner.title,
            "subtitle": banner.subtitle,
            "image": banner.image.url if banner.image else None,
            "button_text": banner.button_text,
            "button_link": banner.button_link,
            "text_color": banner.text_color,
            "order": banner.order,
            "is_active": banner.is_active,
        })

    # ---- UPDATE ----
    banner.title = request.POST.get("title", banner.title)
    banner.subtitle = request.POST.get("subtitle", banner.subtitle)
    banner.button_text = request.POST.get("button_text", banner.button_text)
    banner.button_link = request.POST.get("button_link", banner.button_link)
    banner.text_color = request.POST.get("text_color", banner.text_color)
    banner.order = request.POST.get("order", banner.order)
    banner.is_active = request.POST.get("is_active") in ("true", "1", "on", "yes")

    if "image" in request.FILES:
        banner.image = request.FILES["image"]

    banner.save()

    return JsonResponse({"message": "Banner updated successfully"})

@require_http_methods(["POST"])
def banner_create_api(request):
    image = request.FILES.get("image")

    banner = Banner.objects.create(
        title=request.POST.get("title"),
        subtitle=request.POST.get("subtitle"),
        image=image,
        button_text=request.POST.get("button_text"),
        button_link=request.POST.get("button_link"),
        text_color=request.POST.get("text_color", "white"),
        order=request.POST.get("order", 0),
        is_active=request.POST.get("is_active") in ("true", "1", "on", "yes"),
    )

    return JsonResponse({"message": "Banner created", "id": banner.id})

@require_http_methods(["POST"])
def banner_delete_api(request, pk):
    banner = get_object_or_404(Banner, pk=pk)
    banner.delete()
    return JsonResponse({"message": "Banner deleted"})


# City detail + update
@require_http_methods(["GET", "POST"])
def city_detail_api(request, pk):
    city = get_object_or_404(City, pk=pk)

    if request.method == "GET":
        return JsonResponse({
            "id": city.id,
            "name": city.name,
            "delivery_fee": str(city.delivery_fee),
        })

    # POST = update
    # Support JSON or form-encoded body
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            data = {}
    else:
        data = request.POST

    name = (data.get("name") or "").strip()
    delivery_raw = data.get("delivery_fee", "").strip()

    if name:
        city.name = name

    if delivery_raw != "":
        try:
            city.delivery_fee = Decimal(delivery_raw)
        except (InvalidOperation, ValueError):
            return JsonResponse(
                {"success": False, "error": "Invalid delivery fee"},
                status=400,
            )

    city.save()

    return JsonResponse({"success": True, "id": city.id})

@require_http_methods(["POST"])
def city_delete_api(request, pk):
    city = get_object_or_404(City, pk=pk)
    city.delete()
    return JsonResponse({"success": True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_city(request):
    # Optional admin check (same idea as create_product)
    if not getattr(request.user, "is_admin", False):
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN,
        )

    name = (request.data.get('name') or "").strip()
    if not name:
        return Response(
            {'error': 'City name is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    delivery_raw = (request.data.get('delivery_fee') or "0").strip()
    try:
        delivery_fee = Decimal(delivery_raw)
    except (InvalidOperation, ValueError):
        return Response(
            {'error': 'Invalid delivery fee'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    city = City.objects.create(
        name=name,
        delivery_fee=delivery_fee,
    )

    return Response(
        {'success': True, 'id': city.id},
        status=status.HTTP_201_CREATED,
    )

@require_http_methods(["GET"])
def city_list_api(request):
    cities = City.objects.all().order_by("name")
    data = [
        {
            "id": c.id,
            "name": c.name,
            "delivery_fee": str(c.delivery_fee),
        }
        for c in cities
    ]
    return JsonResponse({"cities": data})