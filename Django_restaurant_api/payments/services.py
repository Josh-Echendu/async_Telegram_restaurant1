import uuid
import hashlib
import hmac
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.urls import reverse
import jwt


def get_vpay_public_key():
    """Return the appropriate VPay public key based on the domain."""
    if settings.VPAY_DOMAIN == 'sandbox':
        return settings.VPAY_SANDBOX_PUBLIC_KEY
    return settings.VPAY_LIVE_PUBLIC_KEY


def generate_transaction_reference(order_id):
    """
    Generate a unique, idempotent transaction reference.
    Format: FORK-{order_id}-{uuid4_hex[:8]}
    This ensures uniqueness even if called multiple times for the same order.
    """
    unique_suffix = uuid.uuid4().hex[:12]
    return f"FORK-{order_id}-{unique_suffix}"



import math

def calculate_payment_amounts(subtotal, service_mode, restaurant):
    delivery_fee = Decimal(str(restaurant.delivery_fee)) if restaurant.delivery_fee else Decimal('0.00')
    
    vat = subtotal * Decimal('0.075')
    vat_rounded = vat.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    grand_total = (subtotal + vat_rounded + delivery_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if service_mode == 'delivery' else (subtotal + vat_rounded).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    transfer_fee = Decimal('100.00')
    transfer_total_raw = grand_total + transfer_fee
    transfer_total = Decimal(str(math.ceil(float(transfer_total_raw))))
    
    card_fee_raw = grand_total * Decimal('0.015')
    card_total_raw = grand_total + card_fee_raw
    card_total = Decimal(str(math.ceil(float(card_total_raw))))
    
    return {
        'vat': vat_rounded,
        'grand_total': grand_total,
        'transfer_fee': transfer_fee,
        'transfer_total': transfer_total,
        'card_fee': card_fee_raw,
        'card_total': card_total,
    }


logger = logging.getLogger(__name__)

def verify_vpay_webhook(request):
    """
    Verify the VPay webhook using Option 1: Secret Key Authentication.
    
    VPay sends a JWT token in the x-payload-auth header.
    The JWT payload contains {secret: your_secret_key}.
    We decode and verify the secret matches our configured key.
    """
    token = request.headers.get('x-payload-auth')
    
    if not token:
        logger.warning("Webhook received without x-payload-auth header")
        return False
    
    try:
        # Decode the JWT without verification first to extract the secret
        # VPay's JWT contains {secret: your_secret_key} as payload
        decoded = jwt.decode(token, options={"verify_signature": False})
        webhook_secret = decoded.get('secret')
        
        if not webhook_secret:
            logger.warning("Webhook JWT does not contain secret")
            return False
        
        # Verify the secret matches our configured key
        if webhook_secret != settings.VPAY_WEBHOOK_SECRET:
            logger.warning("Webhook secret does not match configured key")
            return False
        
        return True
        
    except jwt.DecodeError as e:
        logger.error(f"Failed to decode JWT: {e}")
        return False
    except Exception as e:
        logger.error(f"Webhook verification error: {e}")
        return False