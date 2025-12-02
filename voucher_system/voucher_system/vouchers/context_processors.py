# vouchers/context_processors.py
from .models import CompanyDetail

def company_context(request):
    company = CompanyDetail.load()
    logo_url = company.logo.url if company.logo else None
    return {
        'company_logo_url': logo_url,
        'company_name': company.name if company.name else 'Voucher System',
    }