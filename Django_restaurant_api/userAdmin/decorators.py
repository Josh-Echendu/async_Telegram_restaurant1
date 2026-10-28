from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from restaurants.models import RestaurantMembership


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        
        # ✅ ONLY check if they are logged in AND are staff
        if not request.user.is_authenticated or not request.user.is_staff:
            messages.error(request, "You must be an owner or Manager to access this page.")
            return redirect('userauths:admin_login')
            
        # If they are staff, let them through to the view!
        return view_func(request, *args, **kwargs)
    return wrapper




def owner_required(view_func):
    """
    Decorator for views that checks that the user is logged in, is an AdminUser,
    AND has the role of 'owner'. Managers will be blocked.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        
        # 1. Ensure the user is logged in and is an AdminUser
        if not request.user.is_authenticated or not request.user.is_staff:
            messages.error(request, "You must be an admin to access this page.")
            return redirect('userauths:admin_login')

        # 2. Check if they have an active membership
        membership = RestaurantMembership.objects.filter(
            user=request.user,
            is_active=True
        ).first()

        if not membership:
            messages.error(request, "You are not linked to any restaurant.")
            raise PermissionDenied("No active restaurant membership.")

        # 3. ✅ Check if their role is 'owner'
        if membership.role != 'owner':
            messages.error(request, "Only the restaurant owner can access this page.")
            raise PermissionDenied("Only the restaurant owner can access this page.")
            
        # 4. If they are the Owner, let them in
        return view_func(request, *args, **kwargs)
    return wrapper