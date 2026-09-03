from django.urls import path
from . import views
from django.views.i18n import set_language

urlpatterns = [
    path('', views.home, name='home'),
    path('history/', views.history, name='history'),
    path('saved/', views.saved_plants, name='saved'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('reset-password/', views.reset_password_view, name='reset_password'),
    path('message/', views.message_view, name='message'),
    path('message/<int:msg_id>/', views.message_detail, name='message_detail'),
    path('inbox/', views.admin_inbox, name='admin_inbox'),
    path('contact/', views.contact_view, name='contact'),
    path('settings/', views.admin_settings, name='admin_settings'),
    path('settings/backup/download/<str:filename>/', views.download_backup, name='download_backup'),
    path('user-settings/', views.user_settings, name='user_settings'),
    path('about/', views.about_view, name='about'),
    path('privacy/', views.privacy_policy, name='privacy'),
    path('terms/', views.terms_of_service, name='terms'),
    path('set_language/<str:lang_code>/', views.set_language, name='set_language'),
    path('api/notifications/', views.notifications_api, name='notifications_api'),
    path('api/notifications/<int:msg_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('api/notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('api/search/', views.search_plant_api, name='search_plant_api'),
    path('api/identify/', views.identify_plant_api, name='identify_plant_api'),
    path('api/search-plant/', views.search_plant_text, name='search_plant_text'),
    path('api/save/', views.save_plant_api, name='save_plant_api'),
]
