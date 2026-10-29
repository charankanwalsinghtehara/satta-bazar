from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from rest_framework.renderers import JSONOpenAPIRenderer
from rest_framework.schemas import get_schema_view

from apps.game.views import health, home

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path(
        "password-reset/",
        TemplateView.as_view(template_name="game/password_reset.html"),
        name="password-reset-page",
    ),
    path("api/v1/", include("apps.game.urls")),
    path(
        "api/schema/",
        get_schema_view(
            title="Satta Bazar API",
            version="1.0.0",
            renderer_classes=[JSONOpenAPIRenderer],
            public=True,
        ),
        name="openapi-schema",
    ),
    path(
        "api/docs/",
        TemplateView.as_view(template_name="game/api_docs.html"),
        name="api-docs",
    ),
]
