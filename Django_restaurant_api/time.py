import pytz

print([(tz, tz) for tz in pytz.common_timezones])

from datetime import datetime, timezone

now_utc = datetime.now(timezone.utc)
print()
print("london utc: ", now_utc) # london utc:  2026-04-21 13:03:56.382293+00:00
print("london utc time: ", now_utc.time()) # london utc time:  13:03:56.382293
print("london utc date: ", now_utc.date()) # london utc date:  2026-04-21


restaurant_tz = pytz.timezone('Africa/Lagos')  # UTC+1
print("restaurant_tz: ", restaurant_tz) # restaurant_tz:  Africa/Lagos
print("type restaurant_tz: ", type(restaurant_tz)) # type restaurant_tz:  <class 'pytz.tzfile.Africa/Lagos'>
now_local = now_utc.astimezone(restaurant_tz) 
print()
print("Africa/Lagos: ", now_local)  # Africa/Lagos:  2026-04-21 14:03:56.382293+01:00
print("Africa/Lagos: time", now_local.time())  # Africa/Lagos: time 14:03:56.382293
print("Africa/Lagos: date", now_local.date())  # Africa/Lagos: date 2026-04-21


