from django.urls import path

from . import views

app_name = "share"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/files/", views.list_files, name="list-files"),
    path("api/upload/", views.upload, name="upload"),
    path("api/clipboard/", views.clipboard, name="clipboard"),
    path("api/clipboard/add/", views.clipboard_add, name="clipboard-add"),
    path("api/clipboard/<str:entry_id>/delete/", views.clipboard_delete, name="clipboard-delete"),
    path("api/clipboard/clear/", views.clipboard_clear, name="clipboard-clear"),
    path("files/<path:relpath>", views.download, name="download"),
]
