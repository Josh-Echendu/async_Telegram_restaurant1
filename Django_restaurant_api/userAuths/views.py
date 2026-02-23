from django.shortcuts import render, redirect
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
        print('data: ', request.data)
        serializer = TelegramUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        print('data-serializer: ', data)


        user, created = TelegramUser.objects.update_or_create(
            telegram_id=data.get('telegram_id'),
            defaults={
                "first_name": data.get("first_name", ""),
                "username": data.get("username", ""),
            },
        )
        return Response(
            {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "created": created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

telegram_user_create_api_view = TelegramUserCreateAPIView.as_view()


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



def admin_login_view(request):
    if request.method == 'POST':

        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)
        if user is not None and user.is_staff:

            # Login successful
            login(request, user)

            return redirect("useradmin:dashboard")

        else:
            # Login failed
            messages.error(request, 'Invalid login credentials. Please try again.')
            return redirect("userauths:admin_login")

    return render(request, 'userauths/admin_login.html')

def admin_logout_view(request):
    logout(request)
    return redirect("userauths:admin_login")


# what do you mean here: Optional Enhancements

# Make the link unique per user session → avoids conflicts if multiple users are ordering at the same time.

# Send a dynamic receipt PDF via WhatsApp after checkout.

# Use shortened links or QR codes in the restaurant to reduce typing friction.

# Track click-through → order conversion for analytics.