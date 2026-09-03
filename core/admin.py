from django.contrib import admin
from .models import MedicinalPlant, PlantHistory, SavedPlant, Message, UserProfile, Customer
from django.contrib.auth.admin import UserAdmin

@admin.register(MedicinalPlant)
class MedicinalPlantAdmin(admin.ModelAdmin):
    list_display = ('local_name', 'scientific_name', 'common_name')
    search_fields = ('local_name', 'scientific_name', 'common_name')

@admin.register(PlantHistory)
class PlantHistoryAdmin(admin.ModelAdmin):
    list_display = ('local_name', 'scientific_name', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('local_name', 'scientific_name', 'user__username')

@admin.register(SavedPlant)
class SavedPlantAdmin(admin.ModelAdmin):
    list_display = ('user', 'plant', 'saved_at')
    list_filter = ('saved_at',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'user', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('subject', 'body', 'user__username')

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile Info'
    fk_name = 'user'

@admin.register(Customer)
class CustomerAdmin(UserAdmin):
    inlines = (UserProfileInline, )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_phone')

    def get_phone(self, instance):
        return instance.profile.phone if hasattr(instance, 'profile') else ''
    get_phone.short_description = 'Phone'
