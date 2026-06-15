# userAdmin/context_processors.py
def restaurant_context(request):
    restaurant_id = request.session.get('restaurant_id')
    if restaurant_id:
        from restaurants.models import Restaurant
        restaurant = Restaurant.objects.filter(rid=restaurant_id).first()
        return {'restaurant': restaurant}
    return {}