from django.urls import path
from . import views ,api_views

app_name = "WA_provider"

urlpatterns = [
    # Home / Health Check
    path('', views.index, name='index'),

    # Send OTP / Message API Endpoint
    path('send-otp/', views.send_otp, name='send_otp'),

    # User Registration
    path('accounts/register/', views.register_view, name='register_user'),

    # Choose Message Package
    path('choose-package/', views.choose_package, name='choose_package'),

    # Checkout / Payment Simulation
    path('checkout/', views.checkout, name='checkout'),

    # Dashboard (API Key + Message Balance + Usage)
    path('client/dashboard/', views.dashboard, name='dashboard'),
    path('WA/dashboard/', views.WA_dashboard, name='WA_dashboard'),
    #sitex_pay_controller_
    path("merchant/dashboard/", views.merchant_dashboard, name="merchant_dashboard"),
    path("merchant/register/", views.merchant_register, name="merchant_register"),
    path("merchant/payment-links/", views.payment_links, name="payment_links"),
    path("merchant/payment-links/edit/<int:link_id>/", views.edit_payment_link, name="edit_payment_link"),
    path("merchant/payment-links/delete/<int:link_id>/", views.delete_payment_link, name="delete_payment_link"),
    path("pay/<str:reference>/", views.customer_payment_link, name="customer_payment_link"),
    path("payment-success/<int:transaction_id>/", views.payment_success, name="payment_success"),
    path("merchant/transactions/", views.transaction_list, name="transaction_list"),
    path("merchant/invoices/", views.invoice_list, name="invoice_list"),
    path("merchant/invoices/create/", views.create_invoice, name="create_invoice"),
    path("merchant/invoices/<int:invoice_id>/edit/",views.edit_invoice,name="edit_invoice"),
    path("invoices/delete/<int:invoice_id>/", views.delete_invoice, name="delete_invoice"),
    path("merchant/payouts/", views.payout_list, name="payout_list"),
    path("merchant/subscription/", views.merchant_subscription, name="merchant_subscription"),
    path("merchant/settings/", views.merchant_settings, name="merchant_settings"),
    path("api/subscribe/", api_views.subscribe_package, name="api_subscribe_package"),
    path('merchant/onboarding/', views.merchant_onboarding, name='merchant_onboarding'),
    path("merchant/analytics/", views.merchant_analytics, name="merchant_analytics"),


]
