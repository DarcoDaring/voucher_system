import 'package:flutter/material.dart';
import '../../models/models.dart';
import '../../services/api_service.dart';
import 'repair_create_screen.dart';
import 'repair_detail_screen.dart';

class RepairListScreen extends StatefulWidget {
  const RepairListScreen({super.key});
  @override
  State<RepairListScreen> createState() => _RepairListScreenState();
}

class _RepairListScreenState extends State<RepairListScreen> {
  static const _teal = Color(0xFF00838F);
  List<RepairRecord> _repairs = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      if (ApiService.instance.permissions == null) {
        await ApiService.instance.getPermissions();
      }
      final data = await ApiService.instance.getRepairs();
      if (mounted) setState(() { _repairs = data; _loading = false; });
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4F8),
      body: RefreshIndicator(
        onRefresh: _load,
        color: _teal,
        child: _loading
            ? const Center(child: CircularProgressIndicator(color: _teal))
            : _error != null
                ? ListView(children: [const SizedBox(height: 120), Center(child: Column(children: [
                    Icon(Icons.error_outline, size: 56, color: Colors.red.shade300),
                    const SizedBox(height: 16), Text(_error!),
                    const SizedBox(height: 20), ElevatedButton(onPressed: _load, child: const Text('Retry')),
                  ]))])
                : _repairs.isEmpty
                    ? ListView(children: [const SizedBox(height: 120), Center(child: Column(children: [
                        Icon(Icons.build_outlined, size: 64, color: Colors.grey.shade300),
                        const SizedBox(height: 16),
                        const Text('No repairs yet', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                        Text('Create a repair to get started', style: TextStyle(color: Colors.grey.shade500)),
                      ]))])
                    : ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: _repairs.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (_, i) => _RepairCard(
                          repair: _repairs[i],
                          onTap: () async {
                            await Navigator.of(context).push(
                              MaterialPageRoute(builder: (_) => RepairDetailScreen(repairId: _repairs[i].id)),
                            );
                            _load();
                          },
                        ),
                      ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: _teal,
        foregroundColor: Colors.white,
        onPressed: () async {
          await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const RepairCreateScreen()));
          _load();
        },
        icon: const Icon(Icons.add),
        label: const Text('New Repair'),
      ),
    );
  }
}

class _RepairCard extends StatelessWidget {
  final RepairRecord repair;
  final VoidCallback onTap;
  const _RepairCard({required this.repair, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final statusColor = _statusColor(repair.status);
    final bankColor = _bankColor(repair.bankStatus);
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(color: statusColor.withOpacity(0.1), borderRadius: BorderRadius.circular(20)),
                child: Text(repair.repairNumber, style: TextStyle(fontWeight: FontWeight.bold, color: statusColor, fontSize: 13)),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(color: statusColor.withOpacity(0.1), borderRadius: BorderRadius.circular(20)),
                child: Text(repair.statusLabel, style: TextStyle(color: statusColor, fontSize: 11, fontWeight: FontWeight.w600)),
              ),
            ]),
            const SizedBox(height: 10),
            if (repair.vehicle != null) Row(children: [
              const Icon(Icons.directions_car_outlined, size: 15, color: Colors.grey),
              const SizedBox(width: 6),
              Text(repair.vehicle!, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            ]),
            const SizedBox(height: 6),
            Row(children: [
              const Icon(Icons.build_circle_outlined, size: 15, color: Colors.grey),
              const SizedBox(width: 6),
              Text('${repair.itemsCount} item${repair.itemsCount != 1 ? 's' : ''}', style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
              const SizedBox(width: 12),
              const Icon(Icons.calendar_today_outlined, size: 14, color: Colors.grey),
              const SizedBox(width: 4),
              Text(repair.createdAt, style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
              const Spacer(),
              Text('₹${repair.totalAmount}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Color(0xFF00838F))),
            ]),
            if (repair.bankStatus != null) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(color: bankColor.withOpacity(0.1), borderRadius: BorderRadius.circular(20)),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(_bankIcon(repair.bankStatus), size: 12, color: bankColor),
                  const SizedBox(width: 4),
                  Text(_bankLabel(repair.bankStatus), style: TextStyle(color: bankColor, fontSize: 11, fontWeight: FontWeight.w600)),
                ]),
              ),
            ],
          ]),
        ),
      ),
    );
  }

  Color _statusColor(String s) {
    switch (s) {
      case 'DRAFT': return const Color(0xFF2196F3);
      case 'SUBMITTED': return const Color(0xFFFF9800);
      case 'APPROVED': return const Color(0xFF4CAF50);
      default: return Colors.grey;
    }
  }

  Color _bankColor(String? s) {
    if (s == 'APPROVED') return const Color(0xFF4CAF50);
    if (s == 'PENDING_APPROVAL') return const Color(0xFFFF9800);
    return Colors.grey;
  }

  IconData _bankIcon(String? s) {
    if (s == 'APPROVED') return Icons.check_circle;
    if (s == 'PENDING_APPROVAL') return Icons.hourglass_empty;
    return Icons.account_balance;
  }

  String _bankLabel(String? s) {
    if (s == 'APPROVED') return 'Bank Approved';
    if (s == 'PENDING_APPROVAL') return 'Pending Bank';
    return 'Bank';
  }
}
