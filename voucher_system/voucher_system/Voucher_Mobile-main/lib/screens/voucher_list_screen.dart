// lib/screens/voucher_list_screen.dart

import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import 'login_screen.dart';
import 'voucher_detail_screen.dart';

class VoucherListScreen extends StatefulWidget {
  const VoucherListScreen({super.key});

  @override
  State<VoucherListScreen> createState() => _VoucherListScreenState();
}

class _VoucherListScreenState extends State<VoucherListScreen> {
  List<VoucherSummary> _vouchers = [];
  bool _loading = true;
  String? _error;
  String _statusFilter = 'PENDING';

  final _filters = [
    ('Pending',  'PENDING',  Color(0xFFFEF3C7), Color(0xFF92400E), Color(0xFFF59E0B)),
    ('Approved', 'APPROVED', Color(0xFFDCFCE7), Color(0xFF166534), Color(0xFF22C55E)),
    ('Rejected', 'REJECTED', Color(0xFFFEE2E2), Color(0xFF991B1B), Color(0xFFEF4444)),
  ];

  @override
  void initState() {
    super.initState();
    _load();
  }

  // ── CHANGE 3: Returns true when this PENDING voucher is waiting on [currentUsername] ──
  bool _needsMyApproval(VoucherSummary v, String currentUsername) {
    if (v.status != 'PENDING') return false;
    final raw = v.waitingForUsername;
    if (raw == null || raw.isEmpty) return false;
    return raw.split(',').map((u) => u.trim()).contains(currentUsername);
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final list = await ApiService.instance.getVouchers(status: _statusFilter);

      // ── CHANGE 3: sort "needs my approval" vouchers to the top ──
      final currentUsername =
          ApiService.instance.currentUser?.username ?? '';
      list.sort((a, b) {
        final aNeedsMe = _needsMyApproval(a, currentUsername);
        final bNeedsMe = _needsMyApproval(b, currentUsername);
        if (aNeedsMe && !bNeedsMe) return -1;
        if (!aNeedsMe && bNeedsMe) return 1;
        return 0; // preserve server order for equal items
      });

      if (mounted) setState(() { _vouchers = list; _loading = false; });
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _loading = false; });
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Network error. Check your connection.';
          _loading = false;
        });
      }
    }
  }

  Future<void> _logout() async {
    await ApiService.instance.logout();
    if (!mounted) return;
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  void _showCompanySwitcher() {
    final user = ApiService.instance.currentUser;
    if (user == null || user.companies.isEmpty) return;

    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey.shade300,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Switch Company',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              ...user.companies.map((company) {
                final isActive =
                    ApiService.instance.activeCompany?.id == company.id;
                return ListTile(
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                  leading: ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: company.logoUrl != null
                        ? Image.network(
                            company.logoUrl!,
                            width: 44,
                            height: 44,
                            fit: BoxFit.contain,
                            errorBuilder: (_, __, ___) => _MiniLogoPlaceholder(),
                          )
                        : _MiniLogoPlaceholder(),
                  ),
                  title: Text(
                    company.name,
                    style: TextStyle(
                      fontWeight:
                          isActive ? FontWeight.bold : FontWeight.normal,
                      color:
                          isActive ? const Color(0xFF667EEA) : Colors.black87,
                    ),
                  ),
                  subtitle: Text(
                    company.designation != null
                        ? '${company.role} · ${company.designation}'
                        : company.role,
                    style: const TextStyle(fontSize: 12),
                  ),
                  trailing: isActive
                      ? const Icon(Icons.check_circle,
                          color: Color(0xFF667EEA), size: 20)
                      : null,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                  tileColor: isActive
                      ? const Color(0xFF667EEA).withOpacity(0.06)
                      : null,
                  onTap: isActive
                      ? null
                      : () {
                          ApiService.instance.setActiveCompany(company);
                          Navigator.pop(context);
                          _load();
                          setState(() {});
                        },
                );
              }),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final company = ApiService.instance.activeCompany;

    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: false,
        title: GestureDetector(
          onTap: _showCompanySwitcher,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Vouchers',
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
                  ),
                  if (company != null)
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          company.name,
                          style: const TextStyle(
                              fontSize: 11, color: Colors.white70),
                        ),
                        const SizedBox(width: 3),
                        const Icon(Icons.arrow_drop_down,
                            size: 14, color: Colors.white70),
                      ],
                    ),
                ],
              ),
            ],
          ),
        ),
        actions: [
          IconButton(
            icon: _loading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        color: Colors.white, strokeWidth: 2),
                  )
                : const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: _loading ? null : _load,
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Logout',
            onPressed: _logout,
          ),
        ],
      ),
      body: Column(
        children: [
          // ── Filter chips ───────────────────────────────────────
          Container(
            color: const Color(0xFF667EEA),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Row(
                children: _filters.map((f) {
                  final selected = _statusFilter == f.$2;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      label: Text(f.$1),
                      selected: selected,
                      onSelected: (_) {
                        setState(() => _statusFilter = f.$2);
                        _load();
                      },
                      backgroundColor: Colors.white,
                      selectedColor: f.$3,
                      checkmarkColor: f.$4,
                      labelStyle: TextStyle(
                        color: selected ? f.$4 : Colors.black87,
                        fontWeight:
                            selected ? FontWeight.w600 : FontWeight.normal,
                      ),
                      side: selected
                          ? BorderSide(color: f.$5.withOpacity(0.5))
                          : BorderSide(color: Colors.grey.shade300),
                    ),
                  );
                }).toList(),
              ),
            ),
          ),

          // ── Content ────────────────────────────────────────────
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? _ErrorView(message: _error!, onRetry: _load)
                    : _vouchers.isEmpty
                        ? _EmptyView(filter: _statusFilter)
                        : RefreshIndicator(
                            onRefresh: _load,
                            child: ListView.builder(
                              padding: const EdgeInsets.all(12),
                              itemCount: _vouchers.length,
                              itemBuilder: (_, i) => _VoucherCard(
                                voucher: _vouchers[i],
                                onTap: () async {
                                  await Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder: (_) => VoucherDetailScreen(
                                        voucherId: _vouchers[i].id,
                                      ),
                                    ),
                                  );
                                  _load();
                                },
                              ),
                            ),
                          ),
          ),
        ],
      ),
    );
  }
}

// ── Voucher card ──────────────────────────────────────────────────

class _VoucherCard extends StatelessWidget {
  final VoucherSummary voucher;
  final VoidCallback onTap;

  const _VoucherCard({required this.voucher, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      voucher.voucherNumber,
                      style: const TextStyle(
                          fontWeight: FontWeight.bold, fontSize: 15),
                    ),
                  ),
                  StatusBadge(status: voucher.status),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                voucher.payToDisplay,
                style: const TextStyle(fontSize: 14, color: Colors.black87),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  _meta(Icons.calendar_today_outlined, voucher.voucherDate),
                  const SizedBox(width: 14),
                  _meta(Icons.payment_outlined, voucher.paymentType),
                  const Spacer(),
                  Text(
                    '₹ ${voucher.totalAmount}',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 15,
                      color: Color(0xFF667EEA),
                    ),
                  ),
                ],
              ),
              if (voucher.status == 'PENDING') ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: voucher.requiredApproversCount > 0
                              ? voucher.approvedCount /
                                  voucher.requiredApproversCount
                              : 1.0,
                          backgroundColor: Colors.grey.shade200,
                          color: const Color(0xFF667EEA),
                          minHeight: 5,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '${voucher.approvedCount}/${voucher.requiredApproversCount}',
                      style: const TextStyle(fontSize: 11, color: Colors.grey),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                _WaitingForLabel(voucher: voucher),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _meta(IconData icon, String text) => Row(
        children: [
          Icon(icon, size: 13, color: Colors.grey),
          const SizedBox(width: 3),
          Text(text,
              style: const TextStyle(fontSize: 12, color: Colors.grey)),
        ],
      );
}

// ── Waiting-for label ─────────────────────────────────────────────

class _WaitingForLabel extends StatelessWidget {
  final VoucherSummary voucher;
  const _WaitingForLabel({required this.voucher});

  @override
  Widget build(BuildContext context) {
    final raw = voucher.waitingForUsername;
    if (raw == null || raw.isEmpty) return const SizedBox.shrink();

    final currentUser = ApiService.instance.currentUser?.username ?? '';
    final waitingUsers = raw.split(',').map((u) => u.trim()).toList();
    final isMyTurn = waitingUsers.contains(currentUser);

    if (isMyTurn) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
        decoration: BoxDecoration(
          color: Colors.green.shade50,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Colors.green.shade300),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.touch_app_outlined,
                size: 13, color: Colors.green.shade700),
            const SizedBox(width: 4),
            Text(
              'Waiting for you',
              style: TextStyle(
                fontSize: 11,
                color: Colors.green.shade800,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      );
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.hourglass_top_outlined,
            size: 13, color: Colors.orange.shade600),
        const SizedBox(width: 4),
        Flexible(
          child: Text(
            'Waiting for: $raw',
            style: TextStyle(fontSize: 11, color: Colors.orange.shade800),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}

// ── Reusable status badge ─────────────────────────────────────────

class StatusBadge extends StatelessWidget {
  final String status;
  const StatusBadge({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    final colors = switch (status) {
      'APPROVED' => (
          const Color(0xFF166534),
          const Color(0xFFDCFCE7),
          const Color(0xFF22C55E)
        ),
      'REJECTED' => (
          const Color(0xFF991B1B),
          const Color(0xFFFEE2E2),
          const Color(0xFFEF4444)
        ),
      _ => (
          const Color(0xFF92400E),
          const Color(0xFFFEF3C7),
          const Color(0xFFF59E0B)
        ),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: colors.$2,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: colors.$3.withOpacity(0.4)),
      ),
      child: Text(
        status,
        style: TextStyle(
          color: colors.$1,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

// ── Helpers ───────────────────────────────────────────────────────

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 56, color: Colors.red.shade300),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyView extends StatelessWidget {
  final String filter;
  const _EmptyView({required this.filter});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.inbox_outlined, size: 64, color: Colors.grey.shade300),
          const SizedBox(height: 12),
          Text(
            'No $filter vouchers',
            style: const TextStyle(color: Colors.grey, fontSize: 15),
          ),
        ],
      ),
    );
  }
}

class _MiniLogoPlaceholder extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF667EEA), Color(0xFF764BA2)],
        ),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Icon(Icons.business, color: Colors.white, size: 22),
    );
  }
}