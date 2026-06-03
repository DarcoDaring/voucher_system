import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import 'home_screen.dart';
import 'login_screen.dart';

class CompanySelectScreen extends StatefulWidget {
  const CompanySelectScreen({super.key});
  @override
  State<CompanySelectScreen> createState() => _CompanySelectScreenState();
}

class _CompanySelectScreenState extends State<CompanySelectScreen> {
  static const _teal = Color(0xFF00838F);
  List<Company> _companies = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final user = ApiService.instance.currentUser;
    if (user == null) {
      _logout();
      return;
    }
    final holidayCompanies = user.companies.where((c) => c.enableHolidays).toList();
    setState(() {
      _companies = holidayCompanies;
      _loading = false;
    });
    if (_companies.isEmpty) {
      if (mounted) {
        _showNoAccessDialog();
      }
      return;
    }
    if (_companies.length == 1) {
      await _select(_companies.first);
    }
  }

  Future<void> _select(Company company) async {
    await ApiService.instance.setActiveCompany(company);
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const HomeScreen()),
    );
  }

  void _logout() {
    ApiService.instance.logout();
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
    );
  }

  void _showNoAccessDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('No Access'),
        content: const Text(
          'You are not assigned to any company with the Holidays module enabled.\n\n'
          'Please contact your administrator.',
        ),
        actions: [
          ElevatedButton(
            onPressed: _logout,
            child: const Text('Logout'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4F8),
      appBar: AppBar(
        title: const Text('Select Company'),
        backgroundColor: _teal,
        foregroundColor: Colors.white,
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Logout',
            onPressed: _logout,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: _teal))
          : ListView.separated(
              padding: const EdgeInsets.all(20),
              itemCount: _companies.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (_, i) {
                final c = _companies[i];
                return Card(
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(16),
                    onTap: () => _select(c),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        children: [
                          Container(
                            width: 52,
                            height: 52,
                            decoration: BoxDecoration(
                              color: _teal.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: c.logoUrl != null
                                ? ClipRRect(
                                    borderRadius: BorderRadius.circular(12),
                                    child: CachedNetworkImage(imageUrl: c.logoUrl!, fit: BoxFit.cover),
                                  )
                                : const Icon(Icons.business, color: _teal, size: 28),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(c.name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                                const SizedBox(height: 4),
                                Text(c.role, style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
                                if (c.designation != null)
                                  Text(c.designation!, style: TextStyle(color: _teal, fontSize: 12)),
                              ],
                            ),
                          ),
                          const Icon(Icons.chevron_right, color: Colors.grey),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
    );
  }
}
