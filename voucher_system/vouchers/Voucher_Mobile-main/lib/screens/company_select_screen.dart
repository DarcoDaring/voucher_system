// lib/screens/company_select_screen.dart

import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import 'voucher_list_screen.dart';

class CompanySelectScreen extends StatelessWidget {
  final AuthUser user;

  const CompanySelectScreen({super.key, required this.user});

  void _select(BuildContext context, Company company) {
    ApiService.instance.setActiveCompany(company);
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => const VoucherListScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Auto-select if only 1 company
    if (user.companies.length == 1) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _select(context, user.companies.first);
      });
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Select Company'),
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Logout',
            onPressed: () async {
              await ApiService.instance.logout();
              if (context.mounted) {
                Navigator.pushNamedAndRemoveUntil(
                  context, '/', (_) => false,
                );
              }
            },
          ),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Welcome banner
          Container(
            width: double.infinity,
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF667EEA), Color(0xFF764BA2)],
              ),
            ),
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Welcome, ${user.fullName}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${user.companies.length} ${user.companies.length == 1 ? "company" : "companies"} available',
                  style: const TextStyle(color: Colors.white70, fontSize: 13),
                ),
              ],
            ),
          ),

          const Padding(
            padding: EdgeInsets.fromLTRB(16, 20, 16, 8),
            child: Text(
              'Select a company to continue',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 15,
                color: Colors.black54,
              ),
            ),
          ),

          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              itemCount: user.companies.length,
              itemBuilder: (ctx, i) {
                final company = user.companies[i];
                return _CompanyCard(
                  company: company,
                  onTap: () => _select(context, company),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _CompanyCard extends StatelessWidget {
  final Company company;
  final VoidCallback onTap;

  const _CompanyCard({required this.company, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              // Logo or placeholder
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: company.logoUrl != null
                    ? Image.network(
                        company.logoUrl!,
                        width: 56,
                        height: 56,
                        fit: BoxFit.contain,
                        errorBuilder: (_, __, ___) => _LogoPlaceholder(),
                      )
                    : _LogoPlaceholder(),
              ),
              const SizedBox(width: 14),

              // Info
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      company.name,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        _badge(company.role, Colors.blue),
                        if (company.designation != null) ...[
                          const SizedBox(width: 6),
                          _badge(company.designation!, Colors.purple),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: Colors.grey),
            ],
          ),
        ),
      ),
    );
  }

  Widget _badge(String label, Color color) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: color.shade700,
            fontSize: 11,
            fontWeight: FontWeight.w500,
          ),
        ),
      );
}

class _LogoPlaceholder extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 56,
      height: 56,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF667EEA), Color(0xFF764BA2)],
        ),
        borderRadius: BorderRadius.circular(10),
      ),
      child: const Icon(Icons.business, color: Colors.white, size: 28),
    );
  }
}

extension on Color {
  Color get shade700 {
    final hsl = HSLColor.fromColor(this);
    return hsl.withLightness((hsl.lightness - 0.2).clamp(0.0, 1.0)).toColor();
  }
}