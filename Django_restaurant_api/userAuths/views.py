from django.shortcuts import get_object_or_404, render, redirect
from .serializers import TelegramUserSerializer
from .models import TelegramUser
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.db import transaction, IntegrityError
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from restaurants.models import Restaurant, RestaurantMembership
from .models import AuthToken
from django.http import HttpResponse, JsonResponse
from django.conf import settings 
from django.shortcuts import redirect
from django.http import HttpResponse
from .models import AuthToken
import secrets
from django.utils import timezone
from datetime import timedelta
import json
from orders.redis_client import redis_client
from django.urls import reverse
import logging
import hashlib
import hmac
import time
from datetime import datetime
from django.conf import settings
from django.contrib.auth import login
from userAuths.models import AdminUser


logger = logging.getLogger(__name__)


# Create your views here.
class TelegramUserCreateAPIView(APIView):
    """
    Production-grade endpoint:
    - Idempotent
    - Concurrency-safe
    - Zero duplicate records
    - Handles race conditions automatically
    """
    """
    Indempodent: An operation is idempotent if: You can run it once or many times, and the result is always the same.
        First request → creates user ✅
        Second request → updates same user ✅
        Third request → still same user ✅

        No duplicates. No errors. Same final state.
    """

    @transaction.atomic
    def post(self, request):
        data = request.data

        try:
            restaurant = Restaurant.objects.get(rid=data.get('restaurant_id'))
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with id {data.get('restaurant_id')} not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        telegram_id = data.get("telegram_id")
        defaults = {
            "first_name": data.get("first_name", ""),
            "username": data.get("username", ""),
        }

        try:
            # Look for user with this telegram_id
            # If found → update it
            # If not found → create it
            user, created = TelegramUser.objects.update_or_create(
                telegram_id=telegram_id,
                defaults=defaults,
            )

            # 2️⃣ Link USER ↔ RESTAURANT
            RestaurantMembership.objects.get_or_create(
                customer_user=user,
                restaurant=restaurant
            )
            
            return Response(
                {
                    "id": user.id,
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "created": created,
                    "restaurant": restaurant.name
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except IntegrityError:
            # Another request created it at the same time → fetch the existing one
            user = TelegramUser.objects.get(telegram_id=telegram_id)
            
            return Response(
                {
                    "id": user.id,
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "created": False,
                    "restaurant": restaurant.name
                },
                status=status.HTTP_200_OK,
            )

telegram_user_create_api_view = TelegramUserCreateAPIView.as_view()



class WhatsAppUserCreateAPIView(APIView):
    """
    WhatsApp version of user registration.
    Required fields: whatsapp_id, phone_number, first_name, restaurant_id
    """

    @transaction.atomic
    def post(self, request):
        data = request.data

        try:
            restaurant = Restaurant.objects.get(rid=data.get('restaurant_id'))
        except Restaurant.DoesNotExist:
            return Response(
                {"error": f"Restaurant with id {data.get('restaurant_id')} not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        whatsapp_id = data.get("whatsapp_id")
        phone_number = data.get("phone_number")
        platform = data.get('platform')
        
        # WhatsApp requires phone number
        if not phone_number:
            return Response(
                {"error": "phone_number is required for WhatsApp users"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        defaults = {
            "first_name": data.get("first_name", ""),
            "username": data.get("username", ""),
            "phone_number": phone_number,
        }

        try:
            user=None
            created=None

            # Unofficial: identify by phone_number
            if platform == 'whatsapp2' and not whatsapp_id:
                user, created = TelegramUser.objects.update_or_create(
                    phone_number=phone_number,
                    defaults=defaults,
                )
            else:
                # Official: identify by whatsapp_id
                user, created = TelegramUser.objects.update_or_create(
                    whatsapp_id=whatsapp_id,
                    defaults=defaults,
                )
            
            RestaurantMembership.objects.get_or_create(
                customer_user=user,
                restaurant=restaurant
            )
            
            return Response(
                {
                    "id": user.id,
                    "whatsapp_id": user.whatsapp_id,
                    "phone_number": user.phone_number,
                    "username": user.username,
                    "created": created,
                    "restaurant": restaurant.name
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except IntegrityError:
            user = TelegramUser.objects.get(whatsapp_id=whatsapp_id)
            
            return Response(
                {
                    "id": user.id,
                    "whatsapp_id": user.whatsapp_id,
                    "phone_number": user.phone_number,
                    "username": user.username,
                    "created": False,
                    "restaurant": restaurant.name
                },
                status=status.HTTP_200_OK,
            )

whatsapp_user_create_api_view = WhatsAppUserCreateAPIView.as_view()


class CreateAuthTokenAPIView(APIView):
    """
    Enterprise-grade token creation:
    - Rate limiting recommended
    - Input validation
    - No Redis storage needed (DB is sufficient)
    """
    
    def post(self, request):

        # ✅ Input validation
        user_id = request.data.get("user_id")
        platform = request.data.get("platform")
        restaurant_id = request.data.get("restaurant_id")

        
        if not all([user_id, platform, restaurant_id]):
            return Response(
                {"error": "Missing required fields: user_id, platform, restaurant_id"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        platform = (platform or "").lower()

        if platform not in ['whatsapp', 'whatsapp2', 'facebook']:
            return Response(
                {"error": "Invalid platform. Must be 'whatsapp' or 'telegram'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if platform == 'whatsapp':
            active_user = get_object_or_404(TelegramUser, whatsapp_id=user_id)
        elif platform == 'facebook':
            active_user = get_object_or_404(TelegramUser, page_id=user_id)
        else:
            active_user = get_object_or_404(TelegramUser, phone_number=user_id)
        
        # ✅ Verify restaurant exists
        restaurant = get_object_or_404(Restaurant, rid=restaurant_id)

        # Check membership
        if not RestaurantMembership.objects.filter(
            user=active_user,
            restaurant=restaurant
        ).exists():
            return Response({"error": "User not linked to this restaurant"}, status=status.HTTP_403_FORBIDDEN)
       
        print("i am a member of this restaurant........")

        # ✅ Generate token (DB only, no Redis)
        token = AuthToken.generate(
            user_id=user_id,
            platform=platform,
            restaurant=restaurant,
            mode=request.data.get("mode"),
        )

        # 🔥 ADD THIS DEBUG
        print(f"   is_used: {token.is_used}")
        
        # ✅ Secure URL construction with NGROK_DJANGO
        base_url = settings.NGROK_DJANGO.rstrip('/')

        if platform == 'whatsapp':
            url = f"{base_url}/userauths/whatsapp/callback/{restaurant_id}/?token={token.token}"
        
        elif platform == 'facebook':
            url = f"{base_url}/userauths/facebook/callback/{restaurant_id}/?token={token.token}"
        
        return Response({
            "token": token.token,
            "url": url,
            "expires_in": 300  # 5 minutes in seconds
        }, status=status.HTTP_201_CREATED)
    
whatsapp_init_session_api_view = CreateAuthTokenAPIView.as_view()


def whatsapp_callback_view(request, restaurant_id):
    
    # 🔥 Block Facebook crawler immediately
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    if 'facebookexternalhit' in user_agent:
        print("🚫 Blocked Facebook crawler access")
        return HttpResponse("VibeFlow - Restaurant Ordering System", status=200)
    
    token = request.GET.get("token")
    print(f"   User agent: {request.META.get('HTTP_USER_AGENT')}")
    
    if not token:

        # ✅ No hardcoded URL!
        error_url = reverse('userauths:whatsapp_error', args=[restaurant_id])
        return redirect(f"{error_url}?code=missing_token")
    
    # ✅ Validate token from DATABASE only
    try:
        auth = AuthToken.objects.select_related('restaurant').get(
            token=token,
            restaurant__rid=restaurant_id
        )
    except AuthToken.DoesNotExist:

        # ✅ No hardcoded URL!
        error_url = reverse('userauths:whatsapp_error', args=[restaurant_id])
        logger.info('Invalid token provided for restaurant_id %s', restaurant_id)
        return redirect(f"{error_url}?code=invalid_token")

    # ✅ Check existing session
    if (
        request.session.get("user_id") == auth.user_id and
        request.session.get("restaurant_id") == restaurant_id and
        request.session.get("mode") == auth.mode
    ):
        print("reuse existing session..........")
        menu_url = reverse('orders:restaurant-detail', args=[restaurant_id])
        logger.info("Existing session found for restaurant_id %s", restaurant_id)
        return redirect(f"{menu_url}")

    print("no existing session, validating token..........")
    if not auth.is_valid():        
        reverse_url = reverse('userauths:whatsapp_error', args=[restaurant_id])
        print('Expired or used token provided for restaurant_id', restaurant_id)
        return redirect(f"{reverse_url}?code=invalid_token")  # ← FIXED
    

    # ✅ Reset session if different user
    if (request.session.get("user_id") != auth.user_id or
        request.session.get("restaurant_id") != restaurant_id):
        logger.info('Session reset for restaurant_id %s', restaurant_id)
        print("session flushed..........")
        request.session.flush()


    # ✅ Create session
    request.session["user_id"] = auth.user_id
    request.session["platform"] = auth.platform
    request.session["restaurant_id"] = restaurant_id
    request.session["mode"] = auth.mode

    # ✅ Mark token as used (one-time use)
    auth.use()

    logger.info('Token used successfully for restaurant_id %s', restaurant_id)
    restaurant_menu_url = reverse('orders:restaurant-detail', args=[restaurant_id])

    join = request.GET.get("join", "").lower() == "true"
    
    if join:
        logger.info('User joined via join link for restaurant_id %s', restaurant_id)
        return redirect(f"{restaurant_menu_url}?join=true")
    
    return redirect(f"{restaurant_menu_url}")


# views.py - Add Facebook callback
def facebook_callback_view(request, restaurant_id):
    """
    Handle Facebook menu URL callback
    """
    
    # 🔥 Block Facebook crawler immediately
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    if 'facebookexternalhit' in user_agent:
        print("🚫 Blocked Facebook crawler access")
        return HttpResponse("VibeFlow - Restaurant Ordering System", status=200)
    
    token = request.GET.get("token")
    
    if not token:
        error_url = reverse('userauths:facebook_error', args=[restaurant_id])
        return redirect(f"{error_url}?code=missing_token")
    
    # ✅ Validate token from DATABASE
    try:
        auth = AuthToken.objects.select_related('restaurant').get(
            token=token,
            restaurant__rid=restaurant_id
        )
    except AuthToken.DoesNotExist:
        error_url = reverse('userauths:facebook_error', args=[restaurant_id])
        logger.info('Invalid token provided for restaurant_id %s', restaurant_id)
        return redirect(f"{error_url}?code=invalid_token")
    
    # ✅ Check existing session
    if (
        request.session.get("user_id") == auth.user_id and
        request.session.get("restaurant_id") == restaurant_id and
        request.session.get("mode") == auth.mode
    ):
        print("reusing existing session...")
        menu_url = reverse('orders:restaurant-detail', args=[restaurant_id])
        logger.info("Existing session found for restaurant_id %s", restaurant_id)
        return redirect(f"{menu_url}")
    
    # ✅ Validate token
    if not auth.is_valid():
        error_url = reverse('userauths:facebook_error', args=[restaurant_id])
        print('Expired or used token provided for restaurant_id', restaurant_id)
        return redirect(f"{error_url}?code=invalid_token")
    
    # ✅ Reset session if different user
    if (request.session.get("user_id") != auth.user_id or
        request.session.get("restaurant_id") != restaurant_id):
        logger.info('Session reset for restaurant_id %s', restaurant_id)
        request.session.flush()
    
    # ✅ Create session
    request.session["user_id"] = auth.user_id
    request.session["platform"] = auth.platform
    request.session["restaurant_id"] = restaurant_id
    request.session["mode"] = auth.mode
    
    # ✅ Mark token as used (one-time use)
    auth.use()
    
    logger.info('Token used successfully for Facebook user %s', auth.user_id)
    restaurant_menu_url = reverse('orders:restaurant-detail', args=[restaurant_id])
    return redirect(f"{restaurant_menu_url}")


def whatsapp_login(request, restaurant_id):
    """
    Enterprise-grade login view:
    - Validates old token from DB only
    - Creates new token linked to same user
    - No Redis fallback (DB is source of truth)
    """
    old_token = request.GET.get("token")

    if not old_token:
        error_url = reverse('userauths:whatsapp_error', args=[restaurant_id])
        return redirect(f"{error_url}?code=missing_token")
    
    # ✅ Validate old token from DATABASE only (source of truth)
    try:
        auth_data = AuthToken.objects.get(
            token=old_token,
            restaurant__rid=restaurant_id
        )
    except AuthToken.DoesNotExist:

        # Token not in DB = invalid
        error_url = reverse('userauths:whatsapp_error', args=[restaurant_id])
        return redirect(f"{error_url}?code=invalid_token")

    # ✅ Generate NEW token linked to same user
    new_token = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timedelta(minutes=5)

    restaurant = get_object_or_404(Restaurant, rid=restaurant_id)   
    
    AuthToken.objects.create(
        user_id=auth_data.user_id,  # Same user
        token=new_token,
        platform='whatsapp',
        restaurant=restaurant,
        expires_at=expires_at,
        is_used=False,
        mode=auth_data.mode,
    )
    
    # ✅ Mark old token as used (prevents replay)
    auth_data.use()
    
    # Create the full link

    # ✅ Create the full link by extracting your ngrok URL and removes any trailing slash.
    base_url = settings.NGROK_DJANGO.rstrip('/')
    callback_path = reverse('userauths:whatsapp_callback', args=[restaurant_id])
    whatsapp_link = f"{base_url}{callback_path}?token={new_token}"
    
    # Generate QR code URL
    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={whatsapp_link}"
    
    context = {
        'restaurant_id': restaurant_id,
        'qr_code_url': qr_code_url,
        'whatsapp_link': whatsapp_link,
        'message': 'Scan the QR code or click the link below to continue ordering.',
        'expires_in_minutes': 5
    }
    return render(request, 'restaurant/whatsapp_login.html', context)


def whatsapp_error_view(request, restaurant_id):
    error_code = request.GET.get("code", "unknown")
    
    # Get restaurant details
    try:
        restaurant = Restaurant.objects.get(rid=restaurant_id)
        whatsapp_link = restaurant.get_whatsapp_deep_url_or_clean_phone(deep_url=True)  # Assuming you have this method to generate the WhatsApp link
    except Restaurant.DoesNotExist:
        whatsapp_link = "#"

    messages = {
        "missing_token": {
            "title": "🔐 Authentication Required",
            "message": "No authentication token found. Please start over.",
            "action": "Send 'order' to our WhatsApp bot to get a valid link."
        },
        "invalid_token": {
            "title": "⚠️ Invalid Link",
            "message": "The link you clicked is invalid or has been tampered with.",
            "action": "Please send 'order' to our WhatsApp bot to get a fresh link."
        },
        "expired_token": {
            "title": "⏰ Link Expired",
            "message": "This link has expired or has already been used.",
            "action": "Send 'order' to our WhatsApp bot to get a new link."
        },

        "unknown": {
            "title": "❌ Something Went Wrong",
            "message": "We couldn't process your request.",
            "action": "Please try again by sending 'order' to our WhatsApp bot."
        }
    }
    
    info = messages.get(error_code, messages["unknown"])
    
    context = {
        'restaurant_id': restaurant_id,
        'error_title': info["title"],
        'error_message': info["message"],
        'action_message': info["action"],
        'whatsapp_link': whatsapp_link,
        'restaurant_name': restaurant.name if restaurant else "the restaurant",
    }
    
    return render(request, 'restaurant/whatsapp_error.html', context)

from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

from django.contrib import messages # Make sure this is imported

@csrf_exempt
@xframe_options_exempt
def telegram_callback(request):
    data = request.GET.dict()
    
    role = data.pop('role', 'manager')
    restaurant_id = data.pop('restaurant_id', None)
    received_hash = data.pop('hash', None)
    
    # 1. Missing Hash
    if not received_hash:
        messages.error(request, "Authentication failed: Missing hash.")
        url = reverse('userauths:manager_login')
        return redirect(f"{url}?role={role}&restaurant_id={restaurant_id}")

    # 2. Verify Hash
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(settings.TELEGRAM_BOT_TOKEN.encode()).digest()
    calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        messages.error(request, "Authentication failed: Invalid signature.")
        url = reverse('userauths:manager_login')
        return redirect(f"{url}?role={role}&restaurant_id={restaurant_id}")

    # 3. Replay Attack Check (15 minutes)
    auth_date = int(data.get('auth_date', 0))
    if time.time() - auth_date > 120:
        messages.error(request, "Authentication failed: Session expired. Please log in again.")
        url = reverse('userauths:manager_login')
        return redirect(f"{url}?role={role}&restaurant_id={restaurant_id}")

    # 4. Extract Data
    telegram_id = int(data.get('id'))
    username = data.get('username', f"tg_{telegram_id}")
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    photo_url = data.get('photo_url', None)
    auth_datetime = timezone.make_aware(datetime.fromtimestamp(auth_date))

    # 5. Try to find the user first
    user = AdminUser.objects.filter(telegram_id=telegram_id).first()
    
    if not user:
        # 2. If they don't exist, create them. 
        # (Django will create them with email='' or None, but we will fix it immediately)
        user = AdminUser(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            photo_url=photo_url,
            auth_date=auth_datetime,
            is_active=True,
        )
        # ✅ FORCE email to be None BEFORE saving
        user.email = None
        user.save()
    else:
        # 3. Update existing user
        user.email = None
        user.first_name = first_name
        user.last_name = last_name
        user.photo_url = photo_url
        user.auth_date = auth_datetime
        user.save()

    # 6. Create Membership
    if restaurant_id:
        try:
            restaurant = Restaurant.objects.get(rid=restaurant_id)
            
            RestaurantMembership.objects.get_or_create(
                customer_user=user,
                restaurant=restaurant,
                defaults={'role': role, 'is_active': True}
            )
            
            request.session['restaurant_id'] = restaurant.rid
            
        except Restaurant.DoesNotExist:
            messages.error(request, "The invited restaurant no longer exists.")
            url = reverse('userauths:manager_login')
            return redirect(f"{url}?role={role}&restaurant_id={restaurant_id}")

    # 7. Log them in
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    
    return redirect('useradmin:dashboard')


def manager_login_view(request):
    """
    Renders the page with ONLY the Telegram widget.
    The widget picks up ?role=manager&restaurant_id=xyz from the URL.
    """
    return render(request, 'userauths/manager_login.html')



from django.contrib.auth.decorators import login_required


@login_required
def create_restaurant_view(request):
    
    # If they already have a restaurant membership, don't let them create another one
    if RestaurantMembership.objects.filter(user=request.user).exists():
        return redirect('useradmin:dashboard')

    if request.method == 'POST':
        restaurant_name = request.POST.get('restaurant_name')
        business_type = request.POST.get('business_type')
        service_mode = request.POST.get('service_mode')
        image = request.FILES.get('image')


        if not restaurant_name:
            messages.error(request, "Restaurant name is required.")
        else:
            # 1. Create the Restaurant
            restaurant = Restaurant.objects.create(
                name=restaurant_name,
                business_type=business_type,
                service_mode=service_mode,
                # image=image,
                
                # Add any other required fields here (like address, phone, etc.)
            )

            # 2. Link the user as the Owner
            RestaurantMembership.objects.create(
                user=request.user,
                restaurant=restaurant,
                role='owner'
            )

            messages.success(request, f"Welcome! {restaurant_name} has been created.")
            return redirect('useradmin:dashboard')

    return render(request, 'userauths/create_restaurant.html')


def admin_login_view(request):
    if request.user.is_authenticated:
        return redirect('useradmin:dashboard')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)
        if user is not None and user.is_staff:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect("useradmin:dashboard")
        else:
            messages.error(request, 'Invalid login credentials. Please try again.')
            return redirect("userauths:admin_login")

    return render(request, 'userauths/admin_login.html')



# thk_live_RMVtCxksDOYF9Rl6CTo0Y5t2AXmOOgu9msvOYLf99qUb-XNuk1QNPFxgIrMZ4asa

@login_required
def admin_logout_view(request):

    logout(request)

    # ✅ Clear the messages list completely
    from django.contrib.messages import get_messages
    list(get_messages(request))  # Iterating through them empties the queue
    
    return redirect("userauths:admin_login")


class TelegramUserListAPIView(ListAPIView):
    queryset = TelegramUser.objects.all()
    serializer_class = TelegramUserSerializer
    permission_classes = [AllowAny]

    def get_queryset(self, *args, **kwargs):
        return TelegramUser.objects.all()
    
    # DRF will take the queryset returned by get_queryset(), pass it to the serializer, and then automatically generate the Response in the list() method.
    def list(self, request, *args, **kwargs): # Override list() to ensure JSON + 200 status
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

telegram_list_api_view = TelegramUserListAPIView.as_view()

# what do you mean here: Optional Enhancements

# Make the link unique per user session → avoids conflicts if multiple users are ordering at the same time.

# Send a dynamic receipt PDF via WhatsApp after checkout.

# Use shortened links or QR codes in the restaurant to reduce typing friction.

# Track click-through → order conversion for analytics.