# restaurants/tasks.py (or wherever your Celery/ARQ tasks are)
from celery import shared_task
import httpx
from django.conf import settings
from django.utils import timezone
import logging
from django.db import transaction
from restaurants.models import Restaurant
import json
import redis
from celery.signals import worker_ready
import logging





logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def complete_whatsapp_onboarding(self, restaurant_rid):
    
    try:
        restaurant = Restaurant.objects.get(rid=restaurant_rid)
    except Restaurant.DoesNotExist:
        return
    
    # If already completed, skip
    if restaurant.whatsapp_setup_status == 'completed':
        logger.info(f"✅ Restaurant {restaurant_rid} already onboarded")
        return
    
    access_token = restaurant.whatsapp_access_token
    if not access_token:
        restaurant.whatsapp_setup_status = 'failed'
        restaurant.save(update_fields=['whatsapp_setup_status'])
        return
    
    restaurant.whatsapp_setup_status = 'in_progress'
    restaurant.save(update_fields=['whatsapp_setup_status'])
    
    try:
        # STEP 2: Debug token
        user_id = None
        if not restaurant.whatsapp_user_id:  # Check if already have it
            debug_url = 'https://graph.facebook.com/v20.0/debug_token'
            debug_params = {
                'input_token': access_token,
                'access_token': f"{settings.META_APP_ID}|{settings.META_APP_SECRET}",
            }
            debug_response = httpx.get(debug_url, params=debug_params, timeout=30)
            debug_response.raise_for_status()  # Better error handling
            debug_data = debug_response.json()
            user_id = debug_data['data']['user_id']
            granted_scopes = debug_data['data'].get('scopes', [])
            logger.info(f"✅ Token debugged: user_id={user_id}")
            
            # Save user_id immediately to avoid re-doing Step 2 on retry
            restaurant.whatsapp_user_id = user_id
            restaurant.save(update_fields=['whatsapp_user_id'])
        else:
            user_id = restaurant.whatsapp_user_id
            logger.info(f"♻️ Reusing existing user_id: {user_id}")
        
        # STEP 3: Get WABA
        waba_id = restaurant.whatsapp_business_account_id
        if not waba_id:
            waba_url = f'https://graph.facebook.com/v20.0/{user_id}/whatsapp_business_accounts'
            waba_headers = {'Authorization': f'Bearer {access_token}'}
            waba_response = httpx.get(waba_url, headers=waba_headers, timeout=30)
            waba_response.raise_for_status()
            waba_data = waba_response.json()
            waba = waba_data['data'][0]
            waba_id = waba['id']
            waba_name = waba.get('name', '')
            logger.info(f"✅ WABA found: id={waba_id}")
            
            # Save immediately
            restaurant.whatsapp_business_account_id = waba_id
            restaurant.whatsapp_verified_name = waba_name
            restaurant.save(update_fields=['whatsapp_business_account_id', 'whatsapp_verified_name'])
        else:
            logger.info(f"♻️ Reusing existing waba_id: {waba_id}")
        
        # STEP 4: Get phone number
        phone_number_id = restaurant.whatsapp_phone_number_id
        if not phone_number_id:
            phone_url = f'https://graph.facebook.com/v20.0/{waba_id}/phone_numbers'
            phone_response = httpx.get(phone_url, headers=waba_headers, timeout=30)
            phone_response.raise_for_status()
            phone_data = phone_response.json()
            phone = phone_data['data'][0]
            phone_number_id = phone['id']
            display_phone = phone.get('display_phone_number', '')
            logger.info(f"✅ Phone found: {display_phone}")
            
            # Save immediately
            restaurant.whatsapp_phone_number_id = phone_number_id
            restaurant.whatsapp_business_phone = display_phone
            restaurant.save(update_fields=['whatsapp_phone_number_id', 'whatsapp_business_phone'])
        else:
            logger.info(f"♻️ Reusing existing phone_number_id: {phone_number_id}")
        
        # Final: Mark as complete
        with transaction.atomic():
            restaurant.is_whatsapp_active = True
            restaurant.whatsapp_setup_status = 'completed'
            restaurant.save(update_fields=['is_whatsapp_active', 'whatsapp_setup_status'])
        
        logger.info(f"🎉 WhatsApp onboarding COMPLETED for {restaurant.name}")
        
    except (KeyError, IndexError, httpx.RequestError, httpx.HTTPStatusError) as e:
        # Log the specific failure point
        logger.error(f"❌ Onboarding failed at step: {e}")
        
        # Only retry if we haven't exceeded retries AND status is not 'completed'
        if self.request.retries < self.max_retries:
            restaurant.whatsapp_setup_status = 'pending'
            restaurant.save(update_fields=['whatsapp_setup_status'])
            
            # Exponential backoff: 10, 20s, 40s, 80s
            raise self.retry(exc=e, countdown=10 * (2 ** self.request.retries))
        else:
            restaurant.whatsapp_setup_status = 'failed'
            restaurant.save(update_fields=['whatsapp_setup_status'])
            logger.error(f"💀 Onboarding permanently failed after {self.max_retries} retries")
            raise



logger = logging.getLogger(__name__)


@worker_ready.connect
def start_telegram_listener(sender, **kwargs):
    logger.info("🤖 Starting Telegram result listener...")

    # Your new at_start() logic
    process_telegram_setup_results_worker.delay()


@shared_task(bind=True, max_retries=5)
def process_telegram_setup_results_worker(self):
    r = redis.Redis.from_url(settings.REDIS_URL)

    while True:
        try:
            # Block and wait for results (with timeout)
            result_data = r.brpop("telegram:setup:results")

            if result_data:
                _, data = result_data
                data = json.loads(data)
                result = data.get('result', {})

                if data['status'] == 'success':
                    restaurant = Restaurant.objects.filter(rid=data['restaurant_id']).first()
                    
                    if not restaurant:
                        logger.warning(f"Restaurant not found: {data['restaurant_id']}")
                        continue

                    with transaction.atomic():
                        if data.get('service_mode') in ['dine_in', 'both']:
                            restaurant.kitchen_chat_id = result.get('dine_in_group_id')
                            logger.info(f"✅ Dine-in group saved for {restaurant.name}")

                        if data.get('service_mode') in ['delivery', 'both']:
                            restaurant.delivery_chat_id = result.get('delivery_group_id')
                            logger.info(f"✅ Delivery group saved for {restaurant.name}")

                        restaurant.save(update_fields=['delivery_chat_id', 'kitchen_chat_id'])
                        logger.info(f"🎉 Telegram onboarding COMPLETED for {restaurant.name}")

                else:
                    logger.error(f"❌ Setup failed: {data.get('error')}")
                    break

        except Exception as e:
            if self.request.retries < self.max_retries:
                logger.error(f"Error processing result: {e}")
                raise self.retry(exc=e, countdown=min(2 ** self.request.retries, 60))
            else:
                logger.error(f"❌ Max retries reached. Giving up.")
                raise