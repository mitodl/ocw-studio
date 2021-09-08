"""project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path, re_path

from main.views import public_index, restricted_index


urlpatterns = [
    path("admin/", admin.site.urls),
    path("status/", include("server_status.urls")),
    path("robots.txt", include("robots.urls")),
    path("", include("social_django.urls", namespace="social")),
    url(r"^hijack/", include("hijack.urls", namespace="hijack")),
    # Example view
    re_path("^$", public_index, name="main-index"),
    path("login/", public_index, name="login"),
    re_path(r"^sites/.*$", restricted_index, name="sites"),
    path("new-site/", restricted_index, name="new-site"),
    path("markdown-editor", restricted_index, name="markdown-editor-test"),
    re_path(r"^collections/.*$", restricted_index, name="collections"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", include("news.urls")),
    path("", include("websites.urls")),
    path("", include("mitol.authentication.urls.saml")),
    path("", include("mitol.mail.urls")),
    path("", include("videos.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar  # pylint: disable=wrong-import-position, wrong-import-order

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
