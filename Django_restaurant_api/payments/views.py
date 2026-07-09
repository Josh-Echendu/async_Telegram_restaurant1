import json
import logging
from sys import platform
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from decimal import Decimal

from django.conf import settings

from .service import pos_payment_amounts, verify_vpay_webhook
from orders.models import CheckoutSession, OrderBatch
from rest_framework.views import APIView
from django.db import transaction
from restaurants.models import Restaurant, RestaurantMembership
from userAuths.models import TelegramUser
from rest_framework.response import Response  # ✅ CORRECT
from rest_framework import status  # ✅ CORRECT
from .models import POSConfig
from django.db.models import OuterRef, Subquery, Sum, Value, F
from decimal import Decimal, ROUND_HALF_UP
import math
from .service import calculate_payment_amounts, generate_transaction_reference, get_vpay_public_key


from .services.moniepoint import moniepoint_push_payment
from .services.opay import opay_push_and_wait      # When ready
from .services.palmpay import palmpay_push_and_wait    # When ready


logger = logging.getLogger(__name__)
import time
import json
import logging
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from orders.models import OrderBatch
from orders.models import CheckoutSession
from .service import verify_vpay_webhook

logger = logging.getLogger(__name__)


import redis
redis_client = redis.Redis.from_url(settings.REDIS_URL)


class VPayWebhookAPIView(APIView):

    def post(self, request, *args, **kwargs):
        """
        Handle VPay payment confirmation webhook.
        
        VPay sends a POST request when a payment is completed.
        We find the CheckoutSession by transactionref and mark everything as paid.
        """

        print("request data: ", request.data)
        if not verify_vpay_webhook(request):
            logger.warning("Webhook verification failed")
            return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=403)

        for attempt in range(3):
            try:
                data = json.loads(request.body)
                logger.debug(f"Received VPay webhook data: {data}")

                transaction_ref = data.get('transactionref')
                transaction_status = data.get('transaction_status')  # Only for card
                amount_paid = data.get('amount')  # Amount in cents
                fee = data.get('fee')
                session_id = data.get('session_id')

                logger.info(
                    f"Webhook received: ref={transaction_ref}, "
                    f"status={transaction_status}, amount={amount_paid}"
                )

                # Step 1: Find the checkout session
                session = get_object_or_404(
                    CheckoutSession,
                    transaction_reference=transaction_ref
                )

                # Step 2: Determine if payment was successful
                is_successful = False

                if transaction_status is not None:  # This IS a card payment
                    is_successful = transaction_status == 'success'
                else:  # No transaction_status field = bank transfer
                    is_successful = True  # Bank transfer: webhook only fires on success

                if not is_successful:
                    logger.info(f"Payment failed for session {session.session_id}")
                    return JsonResponse({'status': 'ok', 'message': 'Recorded failed payment'})

                # Step 3: Verify amount matches expected (with tolerance for rounding)
                if session.expected_amount:
                    expected = float(session.expected_amount)
                    if amount_paid and abs(float(amount_paid) - expected) > 1.0:
                        logger.warning(
                            f"Amount mismatch for session {session.session_id}: "
                            f"expected={expected}, received={amount_paid}"
                        )
                        return JsonResponse({'status': 'error', 'message': 'Amount mismatch'}, status=400)

                with transaction.atomic():
                    # Step 4: Mark session and order batch as paid
                    session.payment_status = 'paid'
                    session.paid_at = timezone.now()
                    session.amount_received = amount_paid if amount_paid else None
                    session.is_active = False
                    session.bank_fee = fee if fee else None
                    session.bank_choice = 'vpay'
                    session.webhook_payload = data
                    session.save()

                    # Step 5: Update all OrderBatches in this session
                    updated_count = OrderBatch.objects.filter(
                        checkout_session=session
                    ).update(payment_status='paid')


                # Remove the user's active session from Redis
                if session.platform == 'telegram':
                    redis_key = f"telegram_dine_user_session:{session.telegram_user.telegram_id}"
                elif session.platform == 'whatsapp':
                    redis_key = f"whatsapp_dine_user_session:{session.telegram_user.whatsapp_id}"
                else:
                    redis_key = None

                if redis_key:
                    redis_client.delete(redis_key)

                logger.info(
                    f"Session {session.session_id} marked as paid. "
                    f"{updated_count} order batches updated."
                )

                # Step 6: Send kitchen notification for each paid order
                from orders.tasks import send_order_notifications

                paid_batches = session.session_batches.filter(
                    checkout_session=session,
                    payment_status='paid'
                )

                for batch in paid_batches:
                    if batch.restaurant and batch.telegram_user:
                        send_order_notifications.delay(
                            batch.restaurant.rid,
                            batch.bid,
                            batch.telegram_user.telegram_id,
                        )
                        logger.info(f"Kitchen notification queued for batch {batch.bid}")

                return JsonResponse({'status': 'ok', 'message': 'Payment recorded successfully'})

            except CheckoutSession.DoesNotExist:
                logger.error(f"CheckoutSession not found for transactionref: {transaction_ref}")
                return JsonResponse({'status': 'error', 'message': 'Session not found'}, status=404)

            except Exception as e:
                logger.exception(f"Webhook processing failed (attempt {attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(1)
                else:
                    return JsonResponse({'status': 'error', 'message': 'Internal error'}, status=500)

        return JsonResponse({'status': 'error', 'message': 'Internal error'}, status=500)


vpay_webhook_api_view = csrf_exempt(VPayWebhookAPIView.as_view())




class HandlePOSAPIView(APIView):
    """
    Customer clicks "Pay with Card" in Telegram/WhatsApp.
    This view tries each active POS config the restaurant has.
    First success wins. Cancelled stops. Timeout/Error moves to next brand.
    """

    def post(self, request, *args, **kwargs):
        # ------------------------------------------------------------------
        # 1. Parse request
        # ------------------------------------------------------------------
        platform = (request.data.get('platform') or "").lower()
        restaurant_id = (request.data.get('restaurant_id') or "").lower()  # fixed typo
        telegram_id = request.data.get('telegram_id')
        whatsapp_id = request.data.get('whatsapp_id')

        if not platform or not restaurant_id or not (telegram_id or whatsapp_id):
            logger.warning("Invalid POS webhook payload: missing required fields")
            return Response(
                {'status': 'error', 'message': 'Missing required fields'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------------------------------
        # 2. Resolve user
        # ------------------------------------------------------------------
        user = None
        if platform == 'telegram':
            user = TelegramUser.objects.filter(telegram_id=telegram_id).first()
        elif platform == 'whatsapp':
            user = TelegramUser.objects.filter(whatsapp_id=whatsapp_id).first()

        if not user:
            logger.warning("User not found for POS webhook")
            return Response(
                {'status': 'error', 'message': 'User not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ------------------------------------------------------------------
        # 3. Resolve restaurant
        # ------------------------------------------------------------------
        restaurant = get_object_or_404(Restaurant, rid=restaurant_id)

        membership_exists = RestaurantMembership.objects.filter(
            user=user,
            restaurant=restaurant,
        ).exists()

        if not membership_exists:
            return Response(
                {"message": "User not linked to this restaurant"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------------------------------
        # 4. Get active checkout session
        # ------------------------------------------------------------------
        session = (
            CheckoutSession.objects
            .filter(
                restaurant=restaurant,
                telegram_user=user,
                is_active=True,
            )
            .order_by('-date_created')
            .first()
        )

        if not session:
            return Response({
                "success": False,
                "error": "Session not found",
                "message": "You haven't ordered any items. Order some items.",
            }, status=status.HTTP_400_BAD_REQUEST)

        # ------------------------------------------------------------------
        # 5. Calculate total
        # ------------------------------------------------------------------
        orders = session.session_batches.all()
        total_price = Decimal(
            orders.aggregate(total_price=Sum('total_price'))['total_price'] or 0
        )
        pos_amount = pos_payment_amounts(total_price)['pos_total']

        # ------------------------------------------------------------------
        # 6. Get active POS configs
        # ------------------------------------------------------------------
        active_configs = restaurant.pos_configs.filter(is_active=True)

        if not active_configs.exists():
            logger.error(f"No active POS config for restaurant {restaurant.rid}")
            return Response(
                {'status': 'error', 'message': 'No active POS config'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------------------------------
        # 7. Try each brand in order
        # ------------------------------------------------------------------
        last_error = None

        for config in active_configs:
            brand = config.brand
            logger.info(
                f"Trying {brand} | "
                f"restaurant={restaurant.rid} "
                f"amount={pos_amount} "
                f"ref={session.merchant_reference}"
            )

            # ----------------------------------------------------------
            # MONIEPOINT
            # ----------------------------------------------------------
            if brand == "moniepoint":
                result = moniepoint_push_payment(
                    terminal_serial=config.terminal_identifier,
                    amount=pos_amount,
                    merchant_reference=session.merchant_reference,
                    payment_method="CARD_PURCHASE",
                )

                if result["accepted"]:
                    return Response({
                        "success": True,
                        "brand": "moniepoint",
                        "message": "Payment sent to terminal. Please insert your card.",
                        "merchant_reference": session.merchant_reference,
                    })

                elif result["http_status"] == 401:
                    logger.info("Moniepoint: Retrying push after token refresh")
                    result = moniepoint_push_payment(
                        terminal_serial=config.terminal_identifier,
                        amount=pos_amount,
                        merchant_reference=session.merchant_reference,
                        payment_method="CARD_PURCHASE",
                    )
                    if result["accepted"]:
                        return Response({
                            "success": True,
                            "brand": "moniepoint",
                            "message": "Payment sent to terminal. Please insert your card.",
                            "merchant_reference": session.merchant_reference,
                        })
                    else:
                        last_error = result["error"] or "Moniepoint authentication failed"
                        continue
                else:
                    last_error = result["error"] or "Moniepoint push failed"
                    continue

            # ----------------------------------------------------------
            # OPAY (placeholder — same pattern)
            # ----------------------------------------------------------
            elif brand == "opay":
                result = opay_push_and_wait(
                    terminal_serial=config.terminal_identifier,
                    amount=pos_amount,
                    merchant_reference=session.merchant_reference,
                    payment_method="CARD_PURCHASE",
                )

                if result["accepted"]:
                    return Response({
                        "success": True,
                        "brand": "opay",
                        "message": "Payment sent to terminal. Please insert your card.",
                        "merchant_reference": session.merchant_reference,
                    })
                else:
                    last_error = result["error"] or "Opay push failed"
                    continue

            # ----------------------------------------------------------
            # PALMPAY (placeholder — same pattern)
            # ----------------------------------------------------------
            elif brand == "palmpay":
                result = palmpay_push_and_wait(
                    terminal_serial=config.terminal_identifier,
                    amount=pos_amount,
                    merchant_reference=session.merchant_reference,
                    payment_method="CARD_PURCHASE",
                )

                if result["accepted"]:
                    return Response({
                        "success": True,
                        "brand": "palmpay",
                        "message": "Payment sent to terminal. Please insert your card.",
                        "merchant_reference": session.merchant_reference,
                    })
                else:
                    last_error = result["error"] or "Palmpay push failed"
                    continue


from django.db import transaction, IntegrityError


def save_session_with_unique_reference(session, max_retries=3):
    """Save session with retry on transaction_reference collision."""
    
    for attempt in range(max_retries):
        try:
            session.transaction_reference = generate_transaction_reference(session.session_id)
            session.save(update_fields=['transaction_reference'])
            return session
        except IntegrityError:
            if attempt == max_retries - 1:
                raise
            # Generate a new reference and retry
            continue
    return session




def dine_in_paymentview(request, restaurant_id, session_id, platform):
    """
    Handles dine-in payment. Uses session_id from URL to get user and order.
    """
    
    print("Request received for dine-in payment view: ", restaurant_id, session_id, platform)

    # 1. Get restaurant
    restaurant = get_object_or_404(Restaurant, rid=restaurant_id)
    
    # 2. Get session from database (not Redis)
    session = CheckoutSession.objects.filter(
        restaurant=restaurant,
        session_id=session_id,
        service_mode='dine_in',
        is_active=True,
        payment_status='unpaid',
        platform=platform,
    ).first()

    print("session: ", session)
    
    if not session:
        return HttpResponseBadRequest(
            "No active dine-in checkout session found.",
            status=400
        )
    
    # 3. User is already linked to the session
    user = session.telegram_user
    
    # 4. Verify membership (optional, but good practice)
    membership_exists = RestaurantMembership.objects.filter(
        user=user,
        restaurant=restaurant,
    ).exists()
    
    if not membership_exists:
        return render(request, "restaurant/payment_error.html", {
            "error": "User not linked to this restaurant."
        }, status=400)
    
    # 5. Calculate payment amounts
    total_price = session.session_batches.aggregate(total=Sum('total_price'))['total'] or 0
    amounts = calculate_payment_amounts(total_price, 'dine_in', restaurant)
    batches = session.session_batches.filter(payment_status='unpaid').order_by('-id')
    
    # 6. Generate transaction reference
    session.payment_in_progress = True
    session.save(update_fields=['payment_in_progress'])
    
    context = {
        "session": session,
        "transaction_reference": session.transaction_reference,
        "public_key": get_vpay_public_key(),
        "vpay_domain": settings.VPAY_DOMAIN,

        # ✅ Use the calculated amounts directly
        "vat_amount": amounts['vat'],
        "grand_total": amounts['grand_total'],
        "card_total": amounts['card_total'],
        "transfer_total": amounts['transfer_total'],
        "card_fee": amounts['card_fee'],
        "transfer_fee": amounts['transfer_fee'],
        
        # ✅ Also pass total_price separately
        "total_price": total_price,
        "batches": batches,

    }
    
    return render(request, "restaurant/dine_in_payment.html", context)
        


class CreatePaymentSessionAPIView(APIView):
    """
    API endpoint for mini-app to create payment session.
    Expects: session_id, payment_method (card/transfer)
    Returns: VPay data
    """
    
    def post(self, request):
        try:
            session_id = request.data.get('session_id')
            payment_method = request.data.get('payment_method')
            
            if not session_id or not payment_method:
                return Response(
                    {'error': 'Missing session_id or payment_method'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # ✅ Get session directly
            session = get_object_or_404(CheckoutSession, session_id=session_id, is_active=True, service_mode='dine_in')
            
            # ✅ Calculate amounts
            total_price = session.session_batches.aggregate(total=Sum('total_price'))['total'] or 0
            amounts = calculate_payment_amounts(total_price, 'dine_in', session.restaurant)
            
            final_amount=None
            bank_fee=None

            # Set values based on payment method
            if payment_method == 'card':
                final_amount = amounts['card_total']
                bank_fee = amounts['card_fee']
            else:  # transfer
                final_amount = amounts['transfer_total']
                bank_fee = amounts['transfer_fee']
            
            #✅ Save to session
            session.vat_amount = amounts['vat']
            session.expected_amount = final_amount
            session.bank_fee = bank_fee
            session.transaction_type = payment_method
            
            # ✅ Generate transaction reference
            session = save_session_with_unique_reference(session)
            session.payment_in_progress = True
            session.save()
            
            # Return VPay data
            return Response({
                'success': True,
                'transaction_reference': session.transaction_reference,
                'public_key': get_vpay_public_key(),
                'final_amount': final_amount,
                'vpay_domain': settings.VPAY_DOMAIN,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

create_payment_session = CreatePaymentSessionAPIView.as_view()


class HandlePaymentSelection(APIView):

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        
        session_id = request.data.get('session_id')
        payment_type = (request.data.get('payment_type') or "").lower()

        if not session_id:
            return Response({"error": "Missing session_id"}, status=400)
        
        if payment_type not in ['pos', 'cash']:
            return Response({"error": "Invalid payment type. Must be 'pos' or 'cash'"}, status=400)

        # ✅ Get session directly
        session = get_object_or_404(CheckoutSession, session_id=session_id, is_active=True, service_mode="dine_in")

        # ✅ Session already has user, restaurant, everything
        if payment_type == 'cash':
            session.transaction_type = "cash"
        elif payment_type == 'pos':
            session.transaction_type = "pos"

        final_amount = session.session_batches.filter(payment_status='unpaid').aggregate(
            total=Sum('total_price')
        )['total'] or Decimal('0.00')
        final_amount = final_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        session.expected_amount = final_amount
        session.vat_amount = math.ceil(final_amount * Decimal('0.075'))
        session.payment_in_progress = True
        session.save()

        # ✅ Get table number from latest order
        last_order = session.session_batches.latest('date_created')

        data = {
            "session_id": session.session_id,
            "table_number": last_order.dine_in_table_number,
            "total": final_amount,
            "vat": session.vat_amount,
            "grand_total": math.ceil(final_amount + session.vat_amount),
            "kitchen_chat_id": session.restaurant.kitchen_chat_id,
            "waiter_telegram_id": session.dine_session.waiter_telegram_id,
            "waiter_username": session.dine_session.waiter_username,
        }

        return Response({
            "success": True,
            "message": f"Payment type set to {payment_type} for session {session.session_id}",
            "data": data
        }, status=201)

handle_payment_selection_api_view = HandlePaymentSelection.as_view()


class SavePosCashAPIView(APIView):

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        try:
            session_id = request.data.get('session_id')
            waiter_id = request.data.get('waiter_in_charge')
            payment_method = request.data.get('payment_method')

            if not session_id:
                return Response({"error": "Missing session_id"}, status=400)
            
            # ✅ Get session directly
            session = get_object_or_404(
                CheckoutSession.objects.select_related('dine_session'),
                session_id=session_id, 
                is_active=True, 
                service_mode='dine_in', 
                payment_in_progress=True
            )

            if payment_method == 'cash':
                session.transaction_type = 'cash'

            elif payment_method == 'pos':
                session.transaction_type = 'pos'

            # ✅ Mark as paid
            session.payment_status = 'paid'
            session.amount_received = session.expected_amount
            session.payment_in_progress = False  # ✅ FIXED: Should be False
            session.is_active = False
            session.waiter_for_payment = waiter_id
            session.paid_at = timezone.now()

            session.save(update_fields=[
                'payment_status', 
                'amount_received', 
                'payment_in_progress',
                'waiter_for_payment',
                'is_active',
                'paid_at',
                "transaction_type"
            ])

            # ✅ Update related dine_session separately
            if session.dine_session:
                session.dine_session.status = 'expired'
                session.dine_session.save(update_fields=['status'])

            data = {
                "payment_status": 'paid',
                "amount_received": session.amount_received,
                "payment_in_progress": False,
            }

            # ✅ Send payment notification message here using a cron job
            
            return Response({
                "success": True,
                "message": f"Payment status set to Paid for session {session.session_id}",
                "data": data
            }, status=201)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

save_pos_cash_api_view = SavePosCashAPIView.as_view()