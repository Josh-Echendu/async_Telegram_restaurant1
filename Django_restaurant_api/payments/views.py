import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
from .services import verify_vpay_webhook
from orders.models import CheckoutSession, OrderBatch
from rest_framework.views import APIView
from django.db import transaction


logger = logging.getLogger(__name__)



class VPayWebhookAPIView(APIView):

    def post(self, request, *args, **kwargs):
        """
        Handle VPay payment confirmation webhook.
        
        VPay sends a POST request when a payment is completed.
        We find the CheckoutSession by transactionref and mark everything as paid.
        """

        if not verify_vpay_webhook(request):
            logger.warning("Webhook verification failed")
            return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=403)

        for attempt in range(3):  # Retry mechanism for transient issues
            try:
                data = json.loads(request.body)
                print("Received VPay webhook data:", data)  # Debug log to see the incoming data
                transaction_ref = data.get('transactionref')
                transaction_status = data.get('transaction_status') # Only for card
                amount_paid = data.get('amount') # Amount in cents
                fee = data.get('fee')
                session_id = data.get('session_id') 

                logger.info(
                    f"Webhook received: ref={transaction_ref}, "
                    f"status={transaction_status}, amount={amount_paid}"
                )

                # Step 2: Find the checkout session
                session = get_object_or_404(
                    CheckoutSession,
                    transaction_reference=transaction_ref
                )

                # Step 3: Determine if payment was successful
                is_successful = False
                
                if transaction_status is not None:       # This IS a card payment
                    is_successful = transaction_status == 'success'  # True if "success", False if "failed"
                
                else:  # No transaction_status field = bank transfer
                    is_successful = True # Bank transfer: webhook only fires on success

                if not is_successful:
                    logger.info(f"Payment failed for session {session.session_id}")
                    return JsonResponse({'status': 'ok', 'message': 'Recorded failed payment'})
                
                # Step 4: Verify amount matches expected (with tolerance for rounding)
                if session.expected_amount:
                    expected = float(session.expected_amount)  # Decimal to float
                    if amount_paid and abs(float(amount_paid) - expected) > 1.0:
                        logger.warning(
                            f"Amount mismatch for session {session.session_id}: "
                            f"expected={expected}, received={amount_paid}"
                        )
                        return JsonResponse({'status': 'error', 'message': 'Amount mismatch'}, status=400)
                    
                with transaction.atomic():
                    
                    # Step 5: Mark session and order batch as paid
                    session.payment_status = 'paid'
                    session.paid_at = timezone.now()
                    session.amount_received = amount_paid if amount_paid else None
                    session.is_active = False
                    session.bank_fee = fee if fee else None
                    session.webhook_payload = data  # Store the entire payload for auditing
                    session.save()

                    # Step 6: Update all OrderBatches in this session
                    updated_count = OrderBatch.objects.filter(checkout_session=session).update(payment_status='paid')
                    
                logger.info(
                    f"Session {session.session_id} marked as paid. "
                    f"{updated_count} order batches updated."
                )

                # Step 7: Send kitchen notification for each paid order
                from orders.tasks import send_order_notifications
            
                # Prefetch related data for efficiency
                paid_batches = session.session_batches.filter(
                    checkout_session=session,
                    payment_status='paid'
                )

                for batch in paid_batches:
                    if batch.restaurant and batch.telegram_user:
                        send_order_notifications.delay(batch.restaurant.rid, batch.bid, batch.telegram_user.telegram_id)
                        logger.info(f"Kitchen notification queued for batch {batch.bid}")

                return JsonResponse({'status': 'ok', 'message': 'Payment recorded successfully'})
            
            except CheckoutSession.DoesNotExist:
                logger.error(f"CheckoutSession not found for transactionref: {transaction_ref}")
                return JsonResponse({'status': 'error', 'message': 'Session not found'}, status=404)

            except Exception as e:
                logger.exception(f"Webhook processing failed: {e}")
                # Return 200 anyway so VPay doesn't retry indefinitely
                # We'll investigate and manually fix any issues from the logs

                if attempt == 2:
                    return JsonResponse({'status': 'error', 'message': 'Internal error'}, status=500)
            
vpay_webhook_api_view = csrf_exempt(VPayWebhookAPIView.as_view())