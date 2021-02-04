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
from django.contrib import admin
from django.urls import path, re_path

from main.views import index


urlpatterns = [
    path("admin/", admin.site.urls),
    path("status/", include("server_status.urls")),
    path("robots.txt", include("robots.urls")),
    url(r"^hijack/", include("hijack.urls", namespace="hijack")),
    # Example view
    path("", index, name="main-index"),
    re_path(r"^sites/.*$", index),
    path("markdown-editor", index, name="markdown-editor-test"),
    path("", include("news.urls")),
    path("", include("websites.urls")),
]

if settings.DEBUG:
    import debug_toolbar  # pylint: disable=wrong-import-position, wrong-import-order

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
