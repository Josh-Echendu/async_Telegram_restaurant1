from django.shortcuts import redirect
from django.urls import reverse
from restaurants.models import RestaurantMembership

class OwnerOnboardingMiddleware:
    """
    Ensures that any authenticated AdminUser MUST have a RestaurantMembership 
    before they can access the dashboard.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Only check if the user is logged in
        if request.user.is_authenticated:
            
            # 2. Ignore static files, admin panel, login, logout, and the onboarding page itself
            ignored_paths = [
                '/admin/', 
                '/login/', 
                '/accounts/',  # allauth urls
                '/userauths/', 
                '/static/',
                reverse('userauths:create_restaurant') # We will create this URL
            ]
            
            if not any(request.path.startswith(path) for path in ignored_paths):
                
                # 3. Check if they have a membership
                has_membership = RestaurantMembership.objects.filter(
                    user=request.user
                ).exists()

                # 4. If no membership, force them to onboarding
                if not has_membership:
                    return redirect('userauths:create_restaurant')

        return self.get_response(request)