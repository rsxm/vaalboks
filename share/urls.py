from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/files/", views.list_files, name="list-files"),
    path("api/upload/", views.upload, name="upload"),
    path("files/<path:relpath>", views.download, name="download"),
]
