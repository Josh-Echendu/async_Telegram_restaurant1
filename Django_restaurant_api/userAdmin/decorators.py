from functools import wraps
from django.contrib import messages
from django.shortcuts import render, redirect
from django.core.exceptions import PermissionDenied


def admin_required(view_func):

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("restaurant_id"):
            messages.error(request, "You are not authorized for this restaurant.")
            raise PermissionDenied("No restaurant selected.")
        
        if not request.user.is_authenticated or not request.user.is_staff:
            messages.error(request, "You must be an admin to access this page.")
            return redirect('userauths:admin_login')
        return view_func(request, *args, **kwargs)
    return wrapper