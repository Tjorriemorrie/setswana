from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from main import views

urlpatterns = [
    path('', views.index, name='index'),
    path('card/', views.card, name='card'),
    path('answer/', views.answer, name='answer'),
    path('audio/<int:lexeme_id>/', views.audio, name='audio'),
    path('admin/', admin.site.urls),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]
