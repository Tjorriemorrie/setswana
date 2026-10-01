from django.contrib import admin
from django.urls import path

from main import views

urlpatterns = [
    path('', views.index, name='index'),
    path('card/', views.card, name='card'),
    path('answer/', views.answer, name='answer'),
    path('admin/', admin.site.urls),
]
