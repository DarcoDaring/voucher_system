# vouchers/middleware.py

from django.shortcuts import redirect
from django.urls import reverse

class CompanySelectionMiddleware:
    """
    Ensure user has selected a company before accessing protected pages.
    Redirects to company selector if no company is active in session.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Paths that don't require company selection
        exempt_paths = [
            '/accounts/login/',
            '/accounts/logout/',
            '/admin/',
            '/static/',
            '/media/',
        ]
        
        # Add dynamic URLs
        try:
            exempt_paths.extend([
                reverse('login'),
                reverse('logout'),
                reverse('select_company'),
                reverse('set_company'),
            ])
        except:
            pass  # URLs might not be loaded yet
        
        # Check if current path is exempt
        is_exempt = any(request.path.startswith(path) for path in exempt_paths)
        
        if request.user.is_authenticated and not is_exempt:
            # Check if user has selected a company
            active_company_id = request.session.get('active_company_id')
            
            if not active_company_id:
                # User needs to select a company
                return redirect('select_company')
        
        response = self.get_response(request)
        return response