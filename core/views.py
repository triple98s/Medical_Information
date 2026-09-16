# core/views.py
import os
import logging
from functools import lru_cache, wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import translation
from django.conf import settings
from .models import PlantHistory, SavedPlant, Message, MedicinalPlant, AdminHistory
from .forms import RegisterForm, LoginForm, MessageForm, MedicinalPlantForm
from django.contrib.auth.models import User
import json
import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing import image # type: ignore
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input # type: ignore

logger = logging.getLogger(__name__)

# Taarifa za dawa zinaruhusiwa tu baada ya model kuitambua picha kwa uhakika
# wa 75% au zaidi.  Hii hulinda dhidi ya majibu ya mmea kwa picha zisizo za
# mimea, kama karatasi, au picha zisizo wazi.
MINIMUM_PLANT_CONFIDENCE = 75.0
FEATURE_PROFILES_FILENAME = 'plant_feature_profiles.json'
# Hili ni class la picha ambazo si mimea. Linatengenezwa wakati wa training
# kutoka folder `dataset/Sio_mmea/` na halipaswi kamwe kuonyesha taarifa za dawa.
NON_PLANT_CLASS_NAMES = {"sio_mmea", "not_a_plant", "not_plant", "non_plant"}


@lru_cache(maxsize=1)
def load_plant_identification_assets(model_path, class_indices_path, feature_profiles_path):
    """Load the TensorFlow model once per Gunicorn worker, not once per image."""
    model = tf.keras.models.load_model(model_path)
    with open(class_indices_path, 'r', encoding='utf-8') as file:
        class_indices = json.load(file)
    with open(feature_profiles_path, 'r', encoding='utf-8') as file:
        feature_profiles = json.load(file)['profiles']

    # The final classifier and its penultimate feature vector are evaluated in
    # one pass, keeping the open-set check fast.
    inference_model = tf.keras.Model(
        inputs=model.input,
        outputs=[model.output, model.layers[-2].output],
    )
    return inference_model, {index: name for name, index in class_indices.items()}, feature_profiles


def json_api_errors(view):
    """Return JSON for unexpected API errors and retain the traceback in logs."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except Exception as error:
            logger.exception("Plant identification request failed")
            return JsonResponse(
                {"error": f"Plant identification failed ({type(error).__name__})."},
                status=500,
            )
    return wrapped

def identify_plant(image_path):
    """
    Real plant identification using the trained MobileNetV2 model.
    """
    model_path = os.path.join(settings.BASE_DIR, 'mobilenet_model.h5')
    class_indices_path = os.path.join(settings.BASE_DIR, 'class_indices.json')
    feature_profiles_path = os.path.join(settings.BASE_DIR, FEATURE_PROFILES_FILENAME)
    
    # Kama model haipo, rudisha ujumbe wa kosa
    if not all(os.path.exists(path) for path in (model_path, class_indices_path, feature_profiles_path)):
        print("KOSA: Model, class indices, au feature profiles haijapatikana. "
              "Run build_plant_profiles.py baada ya training.")
        return {
            'local_name': 'Model Haijapatikana',
            'scientific_name': 'Unknown',
            'common_name': 'Unknown',
            'medicinal_uses': 'Faili za uthibitisho wa model hazijapatikana. Run build_plant_profiles.py kabla ya ku-deploy model.',
            'is_confident': False,
        }
    
    try:
        # Model na labels hupakiwa mara ya kwanza tu; requests zinazofuata
        # hutumia cache ili utambuzi uwe wa haraka.
        inference_model, labels, feature_profiles = load_plant_identification_assets(
            model_path, class_indices_path, feature_profiles_path,
        )
        
        # Preprocess image kwa kutumia MobileNetV2 preprocess_input
        img = image.load_img(image_path, target_size=(224, 224))
        img_array = image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = preprocess_input(img_array)
        
        # Predict
        predictions, feature_vectors = inference_model.predict(img_array, verbose=0)
        predicted_class_index = int(np.argmax(predictions))
        plant_name = labels.get(predicted_class_index, 'Unknown')
        confidence = float(np.max(predictions)) * 100

        # Open-set check: a softmax classifier must choose one trained class,
        # even for an unknown picture. Reject it unless its feature vector is
        # sufficiently similar to genuine training examples of that class.
        profile = feature_profiles.get(plant_name)
        if not profile:
            raise ValueError(f"Missing feature profile for model class: {plant_name}")
        feature_vector = np.asarray(feature_vectors[0], dtype=np.float32)
        feature_norm = np.linalg.norm(feature_vector)
        centroid = np.asarray(profile['centroid'], dtype=np.float32)
        similarity = float(np.dot(feature_vector, centroid) / (feature_norm * np.linalg.norm(centroid) + 1e-8))
        if similarity < float(profile['min_similarity']):
            is_swahili = (translation.get_language() or '').lower().startswith('sw')
            return {
                'local_name': 'Haitambuliki (Nje ya Mafunzo)',
                'scientific_name': 'Unknown',
                'common_name': 'Unknown',
                'medicinal_uses': (
                    'Picha hii haifanani vya kutosha na mimea iliyofundishwa. Tafadhali pakia picha ya mmea iliyo wazi.'
                    if is_swahili else
                    'This image does not sufficiently match any trained plant. Please upload a clear plant image.'
                ),
                'confidence': confidence,
                'is_confident': False,
            }

        # Model iliyofundishwa na class `Sio_mmea` inaweza kukataa picha za
        # karatasi, desktop, watu, au vitu vingine visivyo mimea hata ikiwa
        # confidence yake ni kubwa.
        normalized_plant_name = plant_name.strip().lower().replace('-', '_').replace(' ', '_')
        if normalized_plant_name in NON_PLANT_CLASS_NAMES:
            is_swahili = (translation.get_language() or '').lower().startswith('sw')
            return {
                'local_name': 'Haitambuliki (Si Mmea)',
                'scientific_name': 'Unknown',
                'common_name': 'Unknown',
                'medicinal_uses': (
                    'Picha uliyopakia haionekani kuwa ya mmea. Tafadhali pakia picha ya mmea iliyo wazi.'
                    if is_swahili else
                    'The uploaded image does not appear to be a plant. Please upload a clear plant image.'
                ),
                'confidence': confidence,
                'is_confident': False,
            }
        
        # Map AI model class names to database local_names
        # Hii inasaidia kufananisha majina ya model (k.m "Swaumu") na yale ya kwenye database ("Kitunguu saumu")
        NAME_MAPPING = {
            "Swaumu": "Kitunguu Saumu",
            "Manjano": "Bizari Manjano",
            "Mkundekunde": "Mkundekunde au Mkunde Pori",
        }
        if plant_name in NAME_MAPPING:
            plant_name = NAME_MAPPING[plant_name]
            
        print(f"==================================================")
        print(f"AI PREDICTION (MobileNetV2): {plant_name} (Confidence: {confidence:.2f}%)")
        print(f"==================================================")
        
        # Usitoe utambuzi wala taarifa za dawa chini ya 75% ya uhakika.
        if confidence < MINIMUM_PLANT_CONFIDENCE:
            is_swahili = (translation.get_language() or '').lower().startswith('sw')
            return {
                'local_name': 'Haitambuliki (Uhakika Mdogo)',
                'scientific_name': 'Unknown',
                'common_name': 'Unknown',
                'medicinal_uses': (
                    'Picha haitambuliki vizuri. Tafadhali jaribu kupiga picha iliyo wazi zaidi.'
                    if is_swahili else
                    'The image could not be identified with enough confidence. Please upload a clearer plant image.'
                ),
                'confidence': confidence,
                'is_confident': False,
            }
        
        # Fetch from DB
        plant_db = MedicinalPlant.objects.filter(local_name__iexact=plant_name).first()
        
        if plant_db:
            return {
                'local_name': plant_db.local_name,
                'scientific_name': plant_db.scientific_name,
                'common_name': plant_db.common_name,
                'medicinal_uses': f"Faida: {plant_db.benefits_sw}\n\nMatumizi: {plant_db.medicinal_uses_sw}",
                'precautions': plant_db.precautions_sw if plant_db.precautions_sw else "Hakuna tahadhari maalum zilizorekodiwa.",
                'confidence': confidence,
                'is_confident': True,
            }
        else:
            return {
                'local_name': plant_name,
                'scientific_name': 'Unknown',
                'common_name': 'Unknown',
                'medicinal_uses': 'Taarifa za matibabu hazijapatikana kwenye kanzidata.',
                'precautions': 'Hakuna tahadhari zilizopatikana.',
                'confidence': confidence,
                'is_confident': True,
            }
            
    except Exception as e:
        print(f"Error during AI inference: {e}")
        return {
            'local_name': 'Unknown',
            'scientific_name': 'Error',
            'common_name': 'Error',
            'medicinal_uses': 'Kuna hitilafu katika mfumo wa utambuzi. Tafadhali jaribu tena.',
            'precautions': 'Hakuna tahadhari zilizopatikana.',
            'is_confident': False,
        }

def home(request):
    if request.user.is_authenticated and request.user.is_superuser:
        edit_id = request.GET.get('edit')
        edit_instance = None
        if edit_id:
            edit_instance = get_object_or_404(MedicinalPlant, id=edit_id)
            
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'save_plant':
                form = MedicinalPlantForm(request.POST, request.FILES, instance=edit_instance)
                if form.is_valid():
                    plant = form.save()
                    action_type = 'PLANT_EDITED' if edit_instance else 'PLANT_ADDED'
                    AdminHistory.objects.create(
                        admin=request.user,
                        action_type=action_type,
                        description_sw=f'Taarifa za mmea "{plant.local_name}" zimehifadhiwa.',
                        description_en=f'Plant info for "{plant.local_name}" was saved.'
                    )
                    messages.success(request, 'Taarifa za mmea zimehifadhiwa kikamilifu.' if request.LANGUAGE_CODE == 'sw' else 'Plant information saved successfully.')
                    return redirect('home')
                else:
                    messages.error(request, 'Tafadhali kagua makosa katika fomu.' if request.LANGUAGE_CODE == 'sw' else 'Please correct the errors in the form.')
            elif action == 'delete_plant':
                plant_id = request.POST.get('plant_id')
                plant = get_object_or_404(MedicinalPlant, id=plant_id)
                plant_name = plant.local_name
                plant.delete()
                AdminHistory.objects.create(
                    admin=request.user,
                    action_type='PLANT_DELETED',
                    description_sw=f'Mmea "{plant_name}" umefutwa.',
                    description_en=f'Plant "{plant_name}" was deleted.'
                )
                messages.success(request, 'Mmea umefutwa kikamilifu.' if request.LANGUAGE_CODE == 'sw' else 'Plant deleted successfully.')
                return redirect('home')
        else:
            form = MedicinalPlantForm(instance=edit_instance)
            
        plants = MedicinalPlant.objects.all().order_by('local_name')
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_count = User.objects.count()
        plant_count = plants.count()
        return render(request, 'core/home.html', {
            'form': form,
            'plants': plants,
            'edit_instance': edit_instance,
            'user_count': user_count,
            'plant_count': plant_count
        })
        
    return render(request, 'core/home.html')

@login_required
def history(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_history':
            history_id = request.POST.get('history_id')
            item = get_object_or_404(PlantHistory, id=history_id, user=request.user)
            item.delete()
            messages.success(request, 'Historia imefutwa kikamilifu.' if request.LANGUAGE_CODE == 'sw' else 'History deleted successfully.')
            return redirect('history')
        elif action == 'clear_admin_history' and (request.user.is_superuser or request.user.is_staff):
            AdminHistory.objects.all().delete()
            messages.success(request, 'Historia yote imefutwa kikamilifu.' if request.LANGUAGE_CODE == 'sw' else 'All history cleared successfully.')
            return redirect('history')
        elif action == 'bulk_delete_admin_history' and (request.user.is_superuser or request.user.is_staff):
            history_ids = request.POST.getlist('history_ids')
            if history_ids:
                AdminHistory.objects.filter(id__in=history_ids).delete()
                messages.success(request, f'Matukio {len(history_ids)} yamefutwa kikamilifu.' if request.LANGUAGE_CODE == 'sw' else f'{len(history_ids)} events deleted successfully.')
            return redirect('history')

    is_admin = request.user.is_superuser or request.user.is_staff
    
    if is_admin:
        admin_histories = AdminHistory.objects.all().order_by('-created_at')
        return render(request, 'core/history.html', {'admin_histories': admin_histories, 'is_admin': True})
    else:
        histories = PlantHistory.objects.filter(user=request.user).order_by('-created_at')
        return render(request, 'core/history.html', {'histories': histories, 'is_admin': False})

@login_required
def saved_plants(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_saved':
            saved_id = request.POST.get('saved_id')
            item = get_object_or_404(SavedPlant, id=saved_id, user=request.user)
            item.delete()
            messages.success(request, 'Taarifa iliyohifadhiwa imefutwa kikamilifu.' if request.LANGUAGE_CODE == 'sw' else 'Saved item deleted successfully.')
            return redirect('saved')

    saved = SavedPlant.objects.filter(user=request.user).select_related('plant')
    return render(request, 'core/saved.html', {'saved': saved})

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Registration successful. Please login.')
            return redirect('register')
    else:
        form = RegisterForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        
        from django.core.cache import cache
        from django.utils.timezone import now
        from datetime import timedelta
        
        cache_key_lock = f"login_lockout_{username}"
        cache_key_attempts = f"login_attempts_{username}"
        
        email_error = None
        password_error = None
        
        lockout_time = cache.get(cache_key_lock)
        if lockout_time:
            remaining = int((lockout_time - now()).total_seconds() / 60)
            if remaining > 0:
                password_error = f'Account temporarily locked due to multiple failed login attempts. Please try again in {remaining} minute(s).'
                form = LoginForm()
                return render(request, 'core/login.html', {
                    'form': form,
                    'entered_username': username,
                    'entered_password': password,
                    'password_error': password_error
                })
            else:
                cache.delete(cache_key_lock)
                cache.delete(cache_key_attempts)

        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user is not None:
                login(request, user)
                cache.delete(cache_key_lock)
                cache.delete(cache_key_attempts)
                messages.success(request, 'Logged in successfully.')
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('home')
        else:
            from django.contrib.auth import get_user_model
            from django.db.models import Q
            User = get_user_model()
            u = User.objects.filter(Q(username=username) | Q(email=username)).first()
            if not u:
                email_error = 'Invalid email address or username.'
            elif not u.is_active:
                email_error = 'Your account has been suspended by an administrator.'
            else:
                if not u.check_password(password):
                    attempts = cache.get(cache_key_attempts, 0) + 1
                    cache.set(cache_key_attempts, attempts, 3600)
                    if attempts >= 3:
                        lock_until = now() + timedelta(minutes=30)
                        cache.set(cache_key_lock, lock_until, 30 * 60)
                        password_error = 'For your security, your account has been temporarily locked for 30 minutes after 3 failed login attempts.'
                    else:
                        password_error = f'Incorrect password. You have {3 - attempts} attempt(s) remaining before your account is locked.'
                else:
                    password_error = 'A technical error occurred. Please try again later.'
                
        return render(request, 'core/login.html', {
            'form': form,
            'email_error': email_error,
            'password_error': password_error,
            'entered_username': username,
            'entered_password': password
        })
    else:
        form = LoginForm()
    return render(request, 'core/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


def reset_password_view(request):
    """Three-step password reset: 0) get email, 1) verify OTP (sent automatically), 2) set new password."""
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    import random
    User = get_user_model()

    if request.method == 'POST':
        step = request.POST.get('step', '0')

        if step == '0':
            # Step 0: User submitted their email
            email = request.POST.get('email', '').strip()
            if not email:
                messages.error(request, 'Please enter your email address.')
                return render(request, 'core/reset_password.html', {'step': 0})
            
            try:
                user = User.objects.get(email=email)
                # Generate 6-digit OTP
                otp = str(random.randint(100000, 999999))
                request.session['reset_otp'] = otp
                request.session['reset_email'] = email
                
                # Send OTP via email
                subject = 'Plant Species ID . Medicine - Password Reset Verification'
                message = (
                    f"Dear {user.first_name or user.username},\n\n"
                    f"We received a request to reset the password associated with your account.\n"
                    f"Your verification code is:\n\n"
                    f"   {otp}\n\n"
                    f"For security reasons, please do not share this code with anyone.\n\n"
                    f"If you did not request a password reset, you can safely ignore this email.\n\n"
                    f"Thank you,\n"
                    f"The Plant Species ID . Medicine Security Team"
                )
                
                from_email = f'"Plant Species ID . Medicine" <{settings.DEFAULT_FROM_EMAIL}>'
                
                send_mail(
                    subject,
                    message,
                    from_email,
                    [email],
                    fail_silently=False,
                )
                
                return render(request, 'core/reset_password.html', {
                    'step': 1,
                    'email': email,
                    'otp_sent': True,
                })
            except User.DoesNotExist:
                messages.error(request, 'Email not found. Please register or try again.')
                return render(request, 'core/reset_password.html', {'step': 0, 'email': email})
            except Exception as e:
                messages.error(request, f'Failed to send email: {str(e)}')
                return render(request, 'core/reset_password.html', {'step': 0, 'email': email})

        elif step == '1':
            # Step 1: Verify OTP
            email = request.POST.get('email', '').strip()
            otp_input = request.POST.get('otp', '').strip()
            session_otp = request.session.get('reset_otp')
            session_email = request.session.get('reset_email')

            if not otp_input:
                messages.error(request, 'Please enter the OTP code.')
                return render(request, 'core/reset_password.html', {'step': 1, 'email': email})

            if otp_input == session_otp and email == session_email:
                messages.success(request, 'OTP verified. Please enter your new password.')
                return render(request, 'core/reset_password.html', {
                    'step': 2,
                    'email': email,
                    'otp': otp_input,
                })
            else:
                messages.error(request, 'Invalid or expired OTP code.')
                return render(request, 'core/reset_password.html', {'step': 1, 'email': email})

        elif step == '2':
            # Step 2: Set new password
            email = request.POST.get('email', '').strip()
            otp_input = request.POST.get('otp', '').strip()
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            session_otp = request.session.get('reset_otp')
            session_email = request.session.get('reset_email')

            # Extra security verification
            if otp_input != session_otp or email != session_email:
                messages.error(request, 'Session expired or invalid token. Please try again.')
                return redirect('login')

            if not new_password or not confirm_password:
                messages.error(request, 'Please fill in both password fields.')
                return render(request, 'core/reset_password.html', {
                    'step': 2,
                    'email': email,
                    'otp': otp_input,
                })

            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'core/reset_password.html', {
                    'step': 2,
                    'email': email,
                    'otp': otp_input,
                })

            if len(new_password) < 4:
                messages.error(request, 'Password must be at least 4 characters.')
                return render(request, 'core/reset_password.html', {
                    'step': 2,
                    'email': email,
                    'otp': otp_input,
                })

            try:
                user = User.objects.get(email=email)
                user.set_password(new_password)
                user.save()
                # Clear session
                request.session.pop('reset_otp', None)
                request.session.pop('reset_email', None)
                messages.success(request, 'Password reset successful! You can now login.')
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'User not found. Please try again.')
                return redirect('login')

    # GET request 
    email = request.GET.get('email', '').strip()
    
    if email:
        try:
            user = User.objects.get(email=email)
            # Generate 6-digit OTP
            otp = str(random.randint(100000, 999999))
            request.session['reset_otp'] = otp
            request.session['reset_email'] = email
            
            # Send OTP via email
            subject = 'Plant Species ID . Medicine - Password Reset Verification'
            message = (
                f"Dear {user.first_name or user.username},\n\n"
                f"We received a request to reset the password associated with your account.\n"
                f"Your verification code is:\n\n"
                f"   {otp}\n\n"
                f"For security reasons, please do not share this code with anyone.\n\n"
                f"If you did not request a password reset, you can safely ignore this email.\n\n"
                f"Thank you,\n"
                f"The Plant Species ID . Medicine Security Team"
            )
            
            from_email = f'"Plant Species ID . Medicine" <{settings.DEFAULT_FROM_EMAIL}>'
            
            send_mail(
                subject,
                message,
                from_email,
                [email],
                fail_silently=False,
            )
            
            return render(request, 'core/reset_password.html', {
                'step': 1,
                'email': email,
                'otp_sent': True,
            })
        except User.DoesNotExist:
            messages.error(request, 'Email not found. Please try again.')
            return render(request, 'core/reset_password.html', {'step': 0, 'email': email})
        except Exception as e:
            messages.error(request, f'Failed to send email: {str(e)}')
            return render(request, 'core/reset_password.html', {'step': 0, 'email': email})

    # No email provided, just render step 0
    return render(request, 'core/reset_password.html', {'step': 0})


def message_view(request):
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            if not request.user.is_authenticated:
                request.session['draft_message'] = {
                    'subject': form.cleaned_data['subject'],
                    'body': form.cleaned_data['body']
                }
                messages.info(request, 'Tafadhali ingia kwenye mfumo (login) au tengeneza akaunti (register) ili kutuma ujumbe.' if getattr(request, 'LANGUAGE_CODE', 'en') == 'sw' else 'Please login or register to send the message.')
                return redirect('/login/?next=/message/')
                
            msg = form.save(commit=False)
            msg.user = request.user
            msg.save()
            messages.success(request, 'Ujumbe umetumwa kikamilifu.' if getattr(request, 'LANGUAGE_CODE', 'en') == 'sw' else 'Message sent to admin.')
            return redirect('home')
    else:
        draft = request.session.pop('draft_message', None)
        if draft:
            form = MessageForm(initial=draft)
        else:
            form = MessageForm()
    return render(request, 'core/message.html', {'form': form})

@user_passes_test(lambda u: u.is_superuser)
def message_detail(request, msg_id):
    """View to display details of a single message."""
    msg = get_object_or_404(Message, id=msg_id)
    if not msg.is_read:
        msg.is_read = True
        msg.save()
    return render(request, 'core/message_detail.html', {'msg': msg})

@user_passes_test(lambda u: u.is_superuser)
def admin_inbox(request):
    """View to display messages grouped by user like a chat app."""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_conversation':
            user_id = request.POST.get('user_id')
            if user_id:
                Message.objects.filter(user_id=user_id).delete()
                messages.success(request, 'Mazungumzo yamefutwa kikamilifu.' if request.LANGUAGE_CODE == 'sw' else 'Conversation deleted successfully.')
            return redirect('admin_inbox')
        elif action == 'delete_selected':
            selected_ids = request.POST.getlist('selected_users')
            if selected_ids:
                Message.objects.filter(user_id__in=selected_ids).delete()
                count = len(selected_ids)
                messages.success(request, f'Mazungumzo {count} yamefutwa kikamilifu.' if request.LANGUAGE_CODE == 'sw' else f'{count} conversation(s) deleted successfully.')
            return redirect('admin_inbox')
        elif action == 'delete_message':
            msg_id = request.POST.get('msg_id')
            redirect_user_id = request.POST.get('user_id')
            if msg_id:
                Message.objects.filter(id=msg_id).delete()
                messages.success(request, 'Ujumbe umefutwa.' if request.LANGUAGE_CODE == 'sw' else 'Message deleted.')
            if redirect_user_id:
                return redirect(f"/inbox/?user_id={redirect_user_id}")
            return redirect('admin_inbox')

    selected_user_id = request.GET.get('user_id')
    active_conversation = None
    chat_messages = []
    
    if selected_user_id:
        try:
            user_id_int = int(selected_user_id)
            active_conversation = User.objects.get(id=user_id_int)
            # Mark all messages from this user as read
            Message.objects.filter(user_id=user_id_int, is_read=False).update(is_read=True)
            # Get chat messages for this user (oldest first for chat layout)
            chat_messages = list(Message.objects.filter(user_id=user_id_int).order_by('created_at'))
            # Trim extra whitespace/newlines from the messages to prevent huge vertical gaps
            for msg in chat_messages:
                if msg.body:
                    msg.body = msg.body.strip()
        except (ValueError, User.DoesNotExist):
            pass

    all_messages = Message.objects.all().select_related('user').order_by('-created_at')
    
    conversations = []
    seen_users = set()
    
    for msg in all_messages:
        if not msg.user:
            continue
        uid = msg.user.id
        if uid not in seen_users:
            seen_users.add(uid)
            conversations.append({
                'user': msg.user,
                'last_message': msg,
                'unread_count': 0
            })
            
        if not msg.is_read:
            for conv in conversations:
                if conv['user'].id == uid:
                    conv['unread_count'] += 1
                    break
            
    return render(request, 'core/admin_inbox.html', {
        'conversations': conversations,
        'active_conversation': active_conversation,
        'chat_messages': chat_messages
    })

from django.contrib.auth import update_session_auth_hash

@user_passes_test(lambda u: u.is_superuser)
def admin_settings(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'change_password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if not request.user.check_password(current_password):
                messages.error(request, 'Siri ya sasa (Current Password) sio sahihi.')
            elif new_password != confirm_password:
                messages.error(request, 'Siri mpya hazifanani.')
            elif len(new_password) < 4:
                messages.error(request, 'Siri mpya inatakiwa iwe na walau herufi 4.')
            else:
                request.user.set_password(new_password)
                request.user.save()
                update_session_auth_hash(request, request.user)
        elif action == 'update_profile_pic':
            avatar = request.FILES.get('avatar')
            if not avatar:
                messages.error(request, 'Tafadhali chagua picha.')
            elif avatar.size > 3 * 1024 * 1024:  # 3MB
                messages.error(request, 'Picha uliyochagua ni kubwa mno (inazidi 3MB).')
            else:
                from .models import UserProfile
                profile, created = UserProfile.objects.get_or_create(user=request.user)
                profile.avatar = avatar
                profile.save()
                messages.success(request, 'Picha ya wasifu imesasishwa kikamilifu.')
                return redirect('admin_settings')

        elif action == 'change_username':
            new_username = request.POST.get('new_username')
            
            if not new_username:
                messages.error(request, 'Tafadhali ingiza username mpya.')
            else:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                # Check if username exists
                if User.objects.filter(username=new_username).exclude(pk=request.user.pk).exists():
                    messages.error(request, 'Username hii inatumika. Tafadhali chagua nyingine.')
                else:
                    request.user.username = new_username
                    request.user.save()
                    messages.success(request, 'Username imebadilishwa kikamilifu.')
                    return redirect('admin_settings')

        elif action == 'edit_customer':
            customer_id = request.POST.get('customer_id')
            c_username = request.POST.get('username')
            c_email = request.POST.get('email')
            c_phone = request.POST.get('phone')
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                customer = User.objects.get(id=customer_id, is_superuser=False)
                if User.objects.filter(username=c_username).exclude(id=customer_id).exists():
                    messages.error(request, f'Username {c_username} tayari inatumika.')
                else:
                    customer.username = c_username
                    customer.email = c_email
                    customer.save()
                    
                    from .models import UserProfile
                    profile, _ = UserProfile.objects.get_or_create(user=customer)
                    profile.phone = c_phone
                    profile.save()
                    messages.success(request, 'Taarifa za mteja zimesasishwa kikamilifu.')
            except User.DoesNotExist:
                messages.error(request, 'Mteja hajapatikana.')
            return redirect('admin_settings')

        elif action == 'block_customer':
            customer_id = request.POST.get('customer_id')
            from django.contrib.auth import get_user_model
            from django.core.mail import send_mail
            import threading
            User = get_user_model()
            try:
                customer = User.objects.get(id=customer_id, is_superuser=False)
                if customer.is_active:
                    customer.is_active = False
                    customer.save()
                    AdminHistory.objects.create(
                        admin=request.user,
                        action_type='USER_BLOCKED',
                        description_sw=f'Akaunti ya mtumiaji "{customer.username}" imezuiliwa (Blocked).',
                        description_en=f'User account "{customer.username}" was blocked.'
                    )
                    messages.success(request, f'Mteja {customer.username} amezuiwa (Blocked) kikamilifu.')
                    if customer.email:
                        try:
                            threading.Thread(target=send_mail, args=(
                                'Plant Species ID . Medicine',
                                f'Habari {customer.username},\n\nAkaunti yako kwenye mfumo imezuiwa na msimamizi (Admin). Hutaweza kuingia kwenye mfumo tena.\nKama unaona ni kosa, tafadhali wasiliana na utawala.',
                                f'"Plant Species ID . Medicine" <{settings.DEFAULT_FROM_EMAIL}>',
                                [customer.email],
                            ), kwargs={'fail_silently': True}).start()
                        except Exception:
                            pass
                else:
                    customer.is_active = True
                    customer.save()
                    AdminHistory.objects.create(
                        admin=request.user,
                        action_type='USER_UNBLOCKED',
                        description_sw=f'Akaunti ya mtumiaji "{customer.username}" imeruhusiwa (Unblocked).',
                        description_en=f'User account "{customer.username}" was unblocked.'
                    )
                    messages.success(request, f'Mteja {customer.username} ameruhusiwa (Unblocked) kikamilifu.')
                    if customer.email:
                        try:
                            threading.Thread(target=send_mail, args=(
                                'Plant Species ID . Medicine',
                                f'Habari {customer.username},\n\nAkaunti yako kwenye mfumo imeruhusiwa tena na msimamizi (Admin). Sasa unaweza kuingia kwenye mfumo kama kawaida.',
                                f'"Plant Species ID . Medicine" <{settings.DEFAULT_FROM_EMAIL}>',
                                [customer.email],
                            ), kwargs={'fail_silently': True}).start()
                        except Exception:
                            pass
            except User.DoesNotExist:
                messages.error(request, 'Mteja hajapatikana.')
            return redirect('admin_settings')

        elif action == 'delete_customer':
            customer_id = request.POST.get('customer_id')
            from django.contrib.auth import get_user_model
            from django.core.mail import send_mail
            import threading
            User = get_user_model()
            try:
                customer = User.objects.get(id=customer_id, is_superuser=False)
                email = customer.email
                username = customer.username
                customer.delete()
                AdminHistory.objects.create(
                    admin=request.user,
                    action_type='USER_DELETED',
                    description_sw=f'Akaunti ya mtumiaji "{username}" imefutwa.',
                    description_en=f'User account "{username}" was deleted.'
                )
                messages.success(request, 'Mteja amefutwa kikamilifu.')
                if email:
                    try:
                        threading.Thread(target=send_mail, args=(
                            'Plant Species ID . Medicine',
                            f'Habari {username},\n\nAkaunti yako kwenye mfumo imefutwa kabisa na msimamizi (Admin).',
                            f'"Plant Species ID . Medicine" <{settings.DEFAULT_FROM_EMAIL}>',
                            [email],
                        ), kwargs={'fail_silently': True}).start()
                    except Exception:
                        pass
            except User.DoesNotExist:
                messages.error(request, 'Mteja hajapatikana.')
            return redirect('admin_settings')

        elif action == 'create_backup':
            import datetime, os, shutil, subprocess
            from django.conf import settings
            backup_dir = os.path.join(settings.BASE_DIR, 'backups')
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            backup_filename = f'backup_{timestamp}.sql'
            backup_path = os.path.join(backup_dir, backup_filename)
            
            try:
                database = settings.DATABASES['default']
                db_name = database['NAME']
                db_user = database.get('USER', '')
                db_password = database.get('PASSWORD', '')
                db_host = database.get('HOST', '127.0.0.1')
                db_port = str(database.get('PORT', '5432'))

                # Allow deployments to provide their own pg_dump location, then
                # fall back to PATH and the standard Windows installation path.
                pg_dump_candidates = [
                    os.environ.get('PG_DUMP_PATH'),
                    shutil.which('pg_dump'),
                    r'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe',
                ]
                pg_dump_path = next(
                    (path for path in pg_dump_candidates if path and os.path.isfile(path)),
                    None,
                )
                if not pg_dump_path:
                    raise FileNotFoundError(
                        'pg_dump haijapatikana. Weka PG_DUMP_PATH kwenye .env '
                        'au ongeza PostgreSQL bin folder kwenye PATH.'
                    )

                env = os.environ.copy()
                env['PGPASSWORD'] = db_password
                pg_dump_cmd = [
                    pg_dump_path,
                    '-U', db_user,
                    '-h', db_host,
                    '-p', db_port,
                    '-d', db_name,
                    '-f', backup_path
                ]
                subprocess.run(pg_dump_cmd, env=env, check=True)
                messages.success(request, 'Backup imetengenezwa kikamilifu.' if request.LANGUAGE_CODE == 'sw' else 'Backup created successfully.')
            except Exception as e:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                messages.error(request, f'Kuna tatizo: {e}' if request.LANGUAGE_CODE == 'sw' else f'Error creating backup: {e}')
            return redirect('admin_settings')

        elif action == 'delete_backup':
            filename = request.POST.get('filename')
            if filename and filename.startswith('backup_') and filename.endswith('.sql'):
                import os
                from django.conf import settings
                backup_path = os.path.join(settings.BASE_DIR, 'backups', filename)
                if os.path.exists(backup_path):
                    try:
                        os.remove(backup_path)
                        messages.success(request, 'Backup imefutwa kikamilifu.' if request.LANGUAGE_CODE == 'sw' else 'Backup deleted successfully.')
                    except Exception as e:
                        messages.error(request, f'Kuna tatizo: {e}' if request.LANGUAGE_CODE == 'sw' else f'Error deleting backup: {e}')
                else:
                    messages.error(request, 'Backup haijapatikana.' if request.LANGUAGE_CODE == 'sw' else 'Backup not found.')
            return redirect('admin_settings')

    import os, datetime
    from django.conf import settings
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    backups = []
    if os.path.exists(backup_dir):
        for f in os.listdir(backup_dir):
            if f.startswith('backup_') and f.endswith('.sql'):
                filepath = os.path.join(backup_dir, f)
                stat = os.stat(filepath)
                size_kb = stat.st_size / 1024
                date = datetime.datetime.fromtimestamp(stat.st_mtime)
                backups.append({
                    'filename': f,
                    'size': f"{size_kb:.2f} KB",
                    'date': date.strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': stat.st_mtime
                })
        backups.sort(key=lambda x: x['timestamp'], reverse=True)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    customers = User.objects.filter(is_superuser=False).select_related('profile').order_by('-date_joined')

    return render(request, 'core/admin_settings.html', {'customers': customers, 'backups': backups})

@login_required
def download_backup(request, filename):
    if not request.user.is_superuser:
        return redirect('home')
        
    import os
    from django.conf import settings
    from django.http import FileResponse, Http404
    
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    filepath = os.path.join(backup_dir, filename)
    
    if os.path.exists(filepath) and filename.startswith('backup_') and filename.endswith('.sql'):
        response = FileResponse(open(filepath, 'rb'), as_attachment=True, filename=filename)
        return response
    else:
        raise Http404("Backup not found")



@login_required
def user_settings(request):
    if request.user.is_superuser:
        return redirect('admin_settings')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'change_username':
            new_username = request.POST.get('new_username')
            if not new_username:
                messages.error(request, 'Tafadhali ingiza username mpya.')
            else:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                # Check if username exists
                if User.objects.filter(username=new_username).exclude(pk=request.user.pk).exists():
                    messages.error(request, 'Username hii inatumika. Tafadhali chagua nyingine.')
                else:
                    request.user.username = new_username
                    request.user.save()
                    messages.success(request, 'Username imebadilishwa kikamilifu.')
                    return redirect('user_settings')
                    
        elif action == 'change_password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if not request.user.check_password(current_password):
                messages.error(request, 'Siri ya sasa (Current Password) sio sahihi.')
            elif new_password != confirm_password:
                messages.error(request, 'Siri mpya hazifanani.')
            elif len(new_password) < 4:
                messages.error(request, 'Siri mpya inatakiwa iwe na walau herufi 4.')
            else:
                request.user.set_password(new_password)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password yako imebadilishwa kikamilifu.')
                return redirect('user_settings')

        elif action == 'update_profile_pic':
            avatar = request.FILES.get('avatar')
            if not avatar:
                messages.error(request, 'Tafadhali chagua picha.')
            elif avatar.size > 3 * 1024 * 1024:  # 3MB
                messages.error(request, 'Picha uliyochagua ni kubwa mno (inazidi 3MB).')
            else:
                from .models import UserProfile
                profile, created = UserProfile.objects.get_or_create(user=request.user)
                profile.avatar = avatar
                profile.save()
                messages.success(request, 'Picha ya wasifu imesasishwa kikamilifu.')
                return redirect('user_settings')

    return render(request, 'core/user_settings.html')

def contact_view(request):
    """Render contact information page."""
    return render(request, 'core/contact.html')

def about_view(request):
    """Render about page."""
    return render(request, 'core/about.html')

def privacy_policy(request):
    """Render privacy policy page."""
    return render(request, 'core/privacy.html')

def terms_of_service(request):
    """Render terms of service page."""
    return render(request, 'core/terms.html')

def set_language(request, lang_code):
    from django.conf import settings
    response = redirect(request.META.get('HTTP_REFERER', '/'))
    if lang_code in dict(settings.LANGUAGES):
        translation.activate(lang_code)
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            lang_code,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )
    return response


@user_passes_test(lambda u: u.is_superuser)
def notifications_api(request):
    """Return user messages as JSON for admin notification panel."""
    msgs = Message.objects.filter(is_read=False)[:20]
    unread_count = msgs.count()
    data = {
        'unread_count': unread_count,
        'messages': [
            {
                'id': m.id,
                'subject': m.subject,
                'body': m.body,
                'user': m.user.username if m.user else 'Anonymous',
                'is_read': m.is_read,
                'created_at': m.created_at.strftime('%d/%m/%Y %H:%M'),
            }
            for m in msgs
        ]
    }
    return JsonResponse(data)


@user_passes_test(lambda u: u.is_superuser)
def mark_notification_read(request, msg_id):
    """Mark a specific message as read."""
    msg = get_object_or_404(Message, id=msg_id)
    msg.is_read = True
    msg.save()
    return JsonResponse({'status': 'ok'})


@user_passes_test(lambda u: u.is_superuser)
def mark_all_read(request):
    """Mark all messages as read."""
    Message.objects.filter(is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})


from django.views.decorators.csrf import csrf_exempt
from django.db import models as django_models
import json
import base64
from django.core.files.base import ContentFile

def get_translated_plant_data(plant, lang_code):
    """Helper to serialize a MedicinalPlant instance with language preferences."""
    is_sw = lang_code and lang_code.startswith('sw')
    return {
        'id': plant.id,
        'local_name': plant.local_name,
        'scientific_name': plant.scientific_name,
        'common_name': plant.common_name,
        'benefits': plant.benefits_sw if is_sw else plant.benefits_en,
        'medicinal_uses': plant.medicinal_uses_sw if is_sw else plant.medicinal_uses_en,
        'precautions': plant.precautions_sw if is_sw else plant.precautions_en,
        'benefits_sw': plant.benefits_sw,
        'benefits_en': plant.benefits_en,
        'medicinal_uses_sw': plant.medicinal_uses_sw,
        'medicinal_uses_en': plant.medicinal_uses_en,
        'precautions_sw': plant.precautions_sw,
        'precautions_en': plant.precautions_en,
        'image_url': None
    }

def search_plant_api(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'error': 'No query provided'}, status=400)
    
    lang_code = translation.get_language()
    
    # Search by local, common, or scientific name
    plants = MedicinalPlant.objects.filter(
        django_models.Q(local_name__icontains=query) |
        django_models.Q(common_name__icontains=query) |
        django_models.Q(scientific_name__icontains=query)
    )
    
    results = [get_translated_plant_data(p, lang_code) for p in plants]
    return JsonResponse({'results': results})

import urllib.request
import urllib.parse

def search_plant_text(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'error': 'Tafadhali ingiza jina la mmea.' if translation.get_language() == 'sw' else 'Please enter a plant name.'}, status=400)
    
    # Search by local, common, or scientific name
    plant = MedicinalPlant.objects.filter(
        django_models.Q(local_name__icontains=query) |
        django_models.Q(common_name__icontains=query) |
        django_models.Q(scientific_name__icontains=query)
    ).first()
    
    if not plant:
        return JsonResponse({
            'error': f"Samahani, mmea wa '{query}' haujapatikana kwenye kanzidata yetu." if translation.get_language() == 'sw' else f"Sorry, the plant '{query}' was not found in our database."
        }, status=404)

    # Fetch image from Wikipedia using scientific name
    image_url = ''
    if plant.scientific_name and plant.scientific_name != 'Unknown':
        try:
            # Format scientific name correctly (Genus capitalized, species lowercase) e.g., "Azadirachta indica"
            formatted_name = plant.scientific_name.capitalize()
            encoded_title = urllib.parse.quote(formatted_name)
            wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={encoded_title}&prop=pageimages&format=json&pithumbsize=500&redirects=1"
            req = urllib.request.Request(wiki_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                pages = data.get('query', {}).get('pages', {})
                for page_id, page_data in pages.items():
                    if 'thumbnail' in page_data:
                        image_url = page_data['thumbnail'].get('source', '')
                        break
        except Exception as e:
            print(f"Error fetching Wikipedia image: {e}")

    lang_code = translation.get_language()
    plant_data = get_translated_plant_data(plant, lang_code)
    plant_data['image_url'] = image_url
    
    return JsonResponse(plant_data)

@csrf_exempt
@json_api_errors
def identify_plant_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    lang_code = translation.get_language()
    
    # Check if a file is uploaded, or base64 webcam image is sent
    image_file = None
    filename = 'captured_plant.jpg'
    
    if 'image' in request.FILES:
        image_file = request.FILES['image']
        filename = image_file.name
    elif request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            if 'image_base64' in data:
                base64_str = data['image_base64']
                if 'base64,' in base64_str:
                    base64_str = base64_str.split('base64,')[1]
                image_data = base64.b64decode(base64_str)
                image_file = ContentFile(image_data, name='captured_plant.jpg')
        except Exception as e:
            return JsonResponse({'error': f'Failed to parse base64 image: {str(e)}'}, status=400)
            
    if not image_file:
        return JsonResponse({'error': 'No image data provided'}, status=400)
        
    # Save the uploaded image to a temporary history entry so the AI can read the file
    history_entry = PlantHistory.objects.create(
        user=request.user if request.user.is_authenticated else None,
        image=image_file,
        local_name='Pending',
        scientific_name='Pending',
    )
    
    # Run AI Identification
    ai_result = identify_plant(history_entry.image.path)
    predicted_name = ai_result.get('local_name', 'Unknown')

    # Ulinzi wa mwisho: usisome kanzidata ya dawa wala kuhifadhi history kama
    # model haijafikia kiwango cha uhakika wa 75%.
    if not ai_result.get('is_confident', False):
        history_entry.delete()
        msg = ai_result.get('medicinal_uses', 'Tafadhali jaribu picha nyingine.')
        return JsonResponse({'error': msg}, status=422)
    
    # Find the predicted plant in the database
    matched_plant = MedicinalPlant.objects.filter(local_name__iexact=predicted_name).first()
    
    if not matched_plant:
        # Plant recognized by model, but not in DB
        history_entry.delete()
        msg = "Taarifa za mmea huu hazipo kwenye kanzidata yetu. Tafadhali subiri utawala uweke taarifa zake." if lang_code == 'sw' else "Information for this plant is not available in our database yet."
        return JsonResponse({'error': msg}, status=404)
        
    # Update history entry with accurate database info
    is_sw = lang_code == 'sw'
    history_entry.plant = matched_plant
    history_entry.local_name = matched_plant.local_name
    history_entry.scientific_name = matched_plant.scientific_name
    history_entry.common_name = matched_plant.common_name
    history_entry.medicinal_uses = matched_plant.medicinal_uses_sw if is_sw else matched_plant.medicinal_uses_en
    history_entry.save()
    
    response_data = get_translated_plant_data(matched_plant, lang_code)
    response_data['history_id'] = history_entry.id
    return JsonResponse(response_data)

@csrf_exempt
@json_api_errors
def save_plant_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
        
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
        
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST
        
    history_id = data.get('history_id')
    plant_id = data.get('plant_id')
    
    history_entry = None
    
    if history_id:
        history_entry = PlantHistory.objects.filter(id=history_id, user=request.user).first()

    if not history_entry and plant_id:
        # User searched by text and wants to save it without existing history.
        # We create a snapshot if the displayed result came from search, or if
        # its previous history belongs to a different/anonymous browser session.
        plant = get_object_or_404(MedicinalPlant, id=plant_id)
        lang_code = translation.get_language()
        is_sw = lang_code == 'sw'
        history_entry = PlantHistory.objects.create(
            user=request.user,
            plant=plant,
            image='', # blank for search history
            local_name=plant.local_name,
            scientific_name=plant.scientific_name,
            common_name=plant.common_name,
            medicinal_uses=plant.medicinal_uses_sw if is_sw else plant.medicinal_uses_en
        )
        
    if not history_entry:
        return JsonResponse({'error': 'Invalid request parameters'}, status=400)
        
    saved_plant, created = SavedPlant.objects.get_or_create(
        user=request.user,
        plant=history_entry
    )
    
    return JsonResponse({'status': 'ok', 'created': created})
