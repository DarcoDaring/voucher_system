# vouchers/context_processors.py

from .models import Company, CompanyMembership

def company_context(request):
    """
    Inject active company and user's available companies into all templates.
    """
    context = {
        'active_company': None,
        'user_companies': [],
        'company_logo_url': None,
        'company_name': 'Voucher System',
    }
    
    if request.user.is_authenticated:
        # Get active company from session
        active_company_id = request.session.get('active_company_id')
        
        if active_company_id:
            try:
                active_company = Company.objects.get(id=active_company_id, is_active=True)
                context['active_company'] = active_company
                context['company_logo_url'] = active_company.logo.url if active_company.logo else None
                context['company_name'] = active_company.name
            except Company.DoesNotExist:
                # Company was deleted or deactivated, clear session
                request.session.pop('active_company_id', None)
        
        # Get all companies user has access to
        context['user_companies'] = CompanyMembership.objects.filter(
            user=request.user,
            is_active=True,
            company__is_active=True
        ).select_related('company', 'designation').order_by('company__name')
    
    return context