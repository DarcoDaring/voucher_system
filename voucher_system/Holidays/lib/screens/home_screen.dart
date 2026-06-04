import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import 'login_screen.dart';
import 'company_select_screen.dart';
import 'bookings/enquiry_list_screen.dart';
import 'bookings/upcoming_list_screen.dart';
import 'settlement/settlement_list_screen.dart';
import 'bank/bank_list_screen.dart';
import 'repair/repair_list_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  static const _teal = Color(0xFF00838F);
  int _tab = 0;
  DashboardStats? _stats;
  bool _statsLoading = true;

  // Each entry is a counter; incrementing it forces that tab's widget to rebuild
  final List<int> _tabKeys = [0, 0, 0, 0, 0];

  Widget _buildTab(int index) {
    final key = ValueKey('tab_${index}_${_tabKeys[index]}');
    switch (index) {
      case 0: return _DashboardTab(key: key, stats: _stats, loading: _statsLoading, onStatsTap: _switchTab, onRefresh: _loadStats);
      case 1: return EnquiryListScreen(key: key);
      case 2: return UpcomingListScreen(key: key);
      case 3: return SettlementListScreen(key: key);
      case 4: return RepairListScreen(key: key);
      default: return const SizedBox.shrink();
    }
  }

  void _switchTab(int index) {
    setState(() {
      _tabKeys[index]++;   // force the incoming tab to reload
      _tab = index;
    });
    if (index == 0) _loadStats();   // always refresh dashboard stats
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _loadStats();
    ApiService.instance.getPermissions().catchError((_) {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      if (ApiService.instance.isSessionExpired()) _doLogout();
    }
  }

  Future<void> _loadStats() async {
    setState(() => _statsLoading = true);
    try {
      final s = await ApiService.instance.getStats();
      if (mounted) setState(() { _stats = s; _statsLoading = false; });
    } catch (_) {
      if (mounted) setState(() => _statsLoading = false);
    }
  }

  void _doLogout() async {
    await ApiService.instance.logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  void _switchCompany() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const CompanySelectScreen()),
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final company = ApiService.instance.activeCompany;
    return Scaffold(
      appBar: AppBar(
        backgroundColor: _teal,
        foregroundColor: Colors.white,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Holidays', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            if (company != null)
              Text(company.name, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.normal)),
          ],
        ),
        actions: [
          if (_tab == 0)
            IconButton(icon: const Icon(Icons.refresh), onPressed: () => _switchTab(0)),
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert),
            onSelected: (v) {
              if (v == 'switch') _switchCompany();
              if (v == 'logout') _doLogout();
            },
            itemBuilder: (_) => [
              const PopupMenuItem(value: 'switch', child: ListTile(leading: Icon(Icons.business), title: Text('Switch Company'), dense: true)),
              const PopupMenuItem(value: 'logout', child: ListTile(leading: Icon(Icons.logout), title: Text('Logout'), dense: true)),
            ],
          ),
        ],
      ),
      body: _buildTab(_tab),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: _switchTab,
        backgroundColor: Colors.white,
        indicatorColor: _teal.withOpacity(0.15),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.dashboard_outlined),
            selectedIcon: const Icon(Icons.dashboard, color: _teal),
            label: 'Dashboard',
          ),
          NavigationDestination(
            icon: _badge(Icons.help_outline, _stats?.enquiryCount),
            selectedIcon: _badge(Icons.help, _stats?.enquiryCount, color: _teal),
            label: 'Enquiries',
          ),
          NavigationDestination(
            icon: _badge(Icons.event_outlined, _stats?.upcomingCount),
            selectedIcon: _badge(Icons.event, _stats?.upcomingCount, color: _teal),
            label: 'Upcoming',
          ),
          NavigationDestination(
            icon: _badge(Icons.receipt_long_outlined, _stats?.settlementPending),
            selectedIcon: _badge(Icons.receipt_long, _stats?.settlementPending, color: _teal),
            label: 'Settlement',
          ),
          NavigationDestination(
            icon: _badge(Icons.build_outlined, _stats?.repairActive),
            selectedIcon: _badge(Icons.build, _stats?.repairActive, color: _teal),
            label: 'Repair',
          ),
        ],
      ),
    );
  }

  Widget _badge(IconData icon, int? count, {Color? color}) {
    final w = Icon(icon, color: color);
    if (count == null || count == 0) return w;
    return Badge(
      label: Text('$count', style: const TextStyle(fontSize: 10)),
      backgroundColor: const Color(0xFFFF6B35),
      child: w,
    );
  }
}

class _DashboardTab extends StatelessWidget {
  final DashboardStats? stats;
  final bool loading;
  final void Function(int tab) onStatsTap;
  final VoidCallback onRefresh;

  const _DashboardTab({
    super.key,
    this.stats,
    this.loading = false,
    required this.onStatsTap,
    required this.onRefresh,
  });

  static const _teal = Color(0xFF00838F);
  static const _darkTeal = Color(0xFF006064);

  @override
  Widget build(BuildContext context) {
    final company = ApiService.instance.activeCompany;
    final perms = ApiService.instance.permissions;
    return RefreshIndicator(
      onRefresh: () async => onRefresh(),
      color: _teal,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Hero header ──────────────────────────────────────────
            Container(
              width: double.infinity,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [_teal, _darkTeal],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
              padding: const EdgeInsets.fromLTRB(28, 36, 28, 48),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: const Icon(Icons.directions_bus_filled, color: Colors.white, size: 36),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'HOLIDAYS',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 26,
                                fontWeight: FontWeight.w900,
                                letterSpacing: 3,
                              ),
                            ),
                            Text(
                              company?.name ?? '',
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.75),
                                fontSize: 13,
                                fontWeight: FontWeight.w400,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  if (perms?.isApprover == true) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFF6B35),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.verified, color: Colors.white, size: 14),
                          SizedBox(width: 5),
                          Text('Bank Approver', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700)),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),

            // ── Stat cards pulled up over the header ─────────────────
            Transform.translate(
              offset: const Offset(0, -28),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: loading
                    ? const SizedBox(
                        height: 120,
                        child: Center(child: CircularProgressIndicator(color: _teal)),
                      )
                    : Row(
                        children: [
                          Expanded(
                            child: _BigStatCard(
                              label: 'Enquiries',
                              value: stats?.enquiryCount ?? 0,
                              icon: Icons.help_rounded,
                              color: const Color(0xFFFFC107),
                              textColor: const Color(0xFF7B5800),
                              onTap: () => onStatsTap(1),
                            ),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: _BigStatCard(
                              label: 'Upcoming',
                              value: stats?.upcomingCount ?? 0,
                              icon: Icons.event_available_rounded,
                              color: const Color(0xFF1A9E4E),
                              onTap: () => onStatsTap(2),
                            ),
                          ),
                        ],
                      ),
              ),
            ),

            // ── Create booking CTA ────────────────────────────────────
            if (perms?.canCreate ?? true)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                child: _CreateBookingCard(onTap: () => onStatsTap(1)),
              ),

            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

class _BigStatCard extends StatelessWidget {
  final String label;
  final int value;
  final IconData icon;
  final Color color;
  final Color? textColor;
  final VoidCallback onTap;

  const _BigStatCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
    this.textColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: color.withValues(alpha: 0.15),
              blurRadius: 20,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(height: 16),
            Text(
              '$value',
              style: TextStyle(
                fontSize: 40,
                fontWeight: FontWeight.w800,
                color: textColor ?? color,
                height: 1,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Color(0xFF546E7A),
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Text(
                  'View all',
                  style: TextStyle(fontSize: 12, color: textColor ?? color, fontWeight: FontWeight.w600),
                ),
                const SizedBox(width: 2),
                Icon(Icons.arrow_forward_rounded, size: 14, color: textColor ?? color),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _CreateBookingCard extends StatelessWidget {
  final VoidCallback onTap;
  const _CreateBookingCard({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFFFF6B35), Color(0xFFFF8C00)],
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
          ),
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFFFF6B35).withValues(alpha: 0.35),
              blurRadius: 20,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: const Row(
          children: [
            Icon(Icons.add_circle_outline_rounded, color: Colors.white, size: 32),
            SizedBox(width: 16),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Create New Booking',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.3,
                  ),
                ),
                SizedBox(height: 2),
                Text(
                  'Start a new holiday trip order',
                  style: TextStyle(color: Colors.white70, fontSize: 12),
                ),
              ],
            ),
            Spacer(),
            Icon(Icons.arrow_forward_ios_rounded, color: Colors.white70, size: 18),
          ],
        ),
      ),
    );
  }
}
