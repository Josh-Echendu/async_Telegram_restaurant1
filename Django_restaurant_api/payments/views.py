import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal

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
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from orders.models import OrderBatch
from orders.models import CheckoutSession
from .service import verify_vpay_webhook

logger = logging.getLogger(__name__)


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