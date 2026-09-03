# core/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

User = get_user_model()

class MedicinalPlant(models.Model):
    scientific_name = models.CharField(max_length=255, unique=True)
    local_name = models.CharField(max_length=255, db_index=True)
    common_name = models.CharField(max_length=255, blank=True, db_index=True)
    benefits_en = models.TextField(help_text="Benefits of the plant (English)")
    benefits_sw = models.TextField(help_text="Faida za mmea (Kiswahili)")
    medicinal_uses_en = models.TextField(help_text="Medicinal uses/treatments (English)")
    medicinal_uses_sw = models.TextField(help_text="Matibabu ya dawa (Kiswahili)")
    precautions_en = models.TextField(help_text="Precautions/Side effects (English)", blank=True, null=True)
    precautions_sw = models.TextField(help_text="Tahadhari/Madhara (Kiswahili)", blank=True, null=True)

    class Meta:
        verbose_name = "Medicinal Plant"
        verbose_name_plural = "Medicinal Plants"
        ordering = ['local_name']

    def __str__(self):
        return f"{self.local_name} ({self.scientific_name})"

class PlantHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plant_histories', null=True, blank=True)
    plant = models.ForeignKey(MedicinalPlant, on_delete=models.SET_NULL, null=True, blank=True, related_name='histories')
    image = models.ImageField(upload_to='plant_images/')
    local_name = models.CharField(max_length=255)
    scientific_name = models.CharField(max_length=255)
    common_name = models.CharField(max_length=255, blank=True)
    medicinal_uses = models.TextField(blank=True)
    precautions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.local_name} ({self.scientific_name})"

class SavedPlant(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_plants')
    plant = models.ForeignKey(PlantHistory, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ('user', 'plant')
        ordering = ['-saved_at']

    def __str__(self):
        return f"Saved {self.plant} by {self.user}"

class Message(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    subject = models.CharField(max_length=255)
    body = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Message from {self.user or 'Anonymous'}: {self.subject}"

class AdminHistory(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_histories')
    action_type = models.CharField(max_length=50)
    description_sw = models.TextField()
    description_en = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.admin.username} - {self.action_type} at {self.created_at}"

class UserProfile(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

class Customer(User):
    class Meta:
        proxy = True
        verbose_name = 'Customer'
        verbose_name_plural = 'Manage Customers'

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
