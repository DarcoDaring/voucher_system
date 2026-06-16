# vouchers/middleware.py

from django.shortcuts import redirect
from django.urls import reverse
from django.http import Http404


class AdminLocalhostOnlyMiddleware:
    """Allow access to admin pages only from the server machine (localhost)."""

    # Add any admin URL prefixes your project uses
    ADMIN_PATHS = ['/admin/', '/godmode/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_admin_path(request.path):
            ip = self._get_client_ip(request)
            if ip not in ('127.0.0.1', '::1'):
                raise Http404
        return self.get_response(request)

    def _is_admin_path(self, path):
        for admin_path in self.ADMIN_PATHS:
            # Match both /godmode/ and /godmode (without trailing slash)
            if path.startswith(admin_path) or path == admin_path.rstrip('/'):
                return True
        return False

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


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
        except Exception:
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