from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from main import views

handler404 = views.t404_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # language switcher
    path('i18n/', include('django.conf.urls.i18n')),

    # main app (existing)
    path('', include('main.urls')),

    # pages app (NEW)
    path('', include('WA_provider.urls')),   # or 'pages/' if you want prefix
]

# Custom 404 page (production)
if not settings.DEBUG:
    urlpatterns += [
        path('404/', views.t404_view, name='t404_view'),
    ]

# Serve static & media in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
