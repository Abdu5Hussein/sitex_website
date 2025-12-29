from django.urls import path, include
from . import views
from . import api_views
from .api_views import ProjectViewSet, create_product, product_list_api,create_branch ,create_inquiry ,branch_list_api
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")

urlpatterns = [
    path('', views.home, name='home'),
    path("api/", include(router.urls)),
    path('about/', views.about, name='about'),
    path('shop/', views.shop, name='shop'),
    path('cart/', views.view_cart, name='view_cart'),
    path('products/', views.products, name='products'),
    path('contact/', views.contact, name='contact'),
    path('clients/', views.clients, name='clients'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('our-services/', views.categories, name='categories'),
    path('api/branches/', branch_list_api, name='branch-list-api'),
    path('api/create-product/', create_product, name='create_product'),
    path('api/create-branch/', create_branch, name='create_branch'),
    path('api/create-inquiry/', create_inquiry, name='create_inquiry'),
    path('api/products/', product_list_api, name='api_products'),
    path("products/api/<int:pk>/", api_views.product_detail_api, name="product_detail_api"),
    path("products/api/<int:pk>/delete/", api_views.product_delete_api, name="product_delete_api"),
    path("branches/api/<int:pk>/", api_views.branch_detail_api, name="branch_detail_api"),
    path("branches/api/<int:pk>/delete/", api_views.branch_delete_api, name="branch_delete_api"),
    path("branches/api/get-primary/", api_views.get_primary_branch, name="get_primary_branch"),
    path('api/products/', views.get_products_api, name='products_api'),
    path('add/cat', api_views.category_add, name='category_add'),
    path('api/category/<int:category_id>/update/', api_views.category_update, name='category_update'),
    path('api/category/<int:category_id>/delete/', api_views.category_delete, name='category_delete'),
    path('api/category/<int:category_id>/', api_views.category_detail, name='category_detail'),
    path('api/categories/', api_views.api_categories, name='api-categories'),
    path('api/products/cat', api_views.api_products_by_category, name='api-products-by-category'),
    path('api/home-data/', api_views.home_data, name='api-home-data'),
    path('api/search/', api_views.search_products, name='api-search-products'),
    path('api/categories/', api_views.get_categories, name='api-get-categories'),
    path('api/product/<int:product_id>/', api_views.get_product_detail, name='api-product-detail'),
    path('api/quick-view/', api_views.quick_view, name='api-quick-view'),
    path('api/shop-page-data/', api_views.shop_page_data, name='shop_page_data'),
    path('product/<int:product_id>/', views.product_detail_view, name='product_detail'),
    path('api/get-product/<int:product_id>/', views.get_product_api, name='get-product-api'),
    path('api/invoice/create/', api_views.create_invoice, name='create_invoice'),
    path("banners/api/<int:pk>/", api_views.banner_detail_api, name="banner_detail_api"),
    path("banners/api/<int:pk>/delete/", api_views.banner_delete_api, name="banner_delete_api"),
    path("api/banner/create/", api_views.banner_create_api, name="banner_add"),
    # Cities (new)
    path("cities/api/<int:pk>/", api_views.city_detail_api, name="city_detail_api"),
    path("cities/api/<int:pk>/delete/", api_views.city_delete_api, name="city_delete_api"),
    path("cities/create/", api_views.create_city, name="create_city"),
    path("cities/api/list/", api_views.city_list_api, name="city_list_api"),
    path('brand/add/', api_views.brand_add, name='brand_add'),
    path('brand/update/<int:brand_id>/', api_views.brand_update, name='brand_update'),
    path('brand/delete/<int:brand_id>/', api_views.brand_delete, name='brand_delete'),
    path('api/brands/', api_views.get_brands, name='get_brands'),




]
