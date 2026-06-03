import 'package:flutter/material.dart';
import '../../models/models.dart';
import '../../services/api_service.dart';
import 'settlement_form_screen.dart';
import '../bank/bank_list_screen.dart';

class SettlementListScreen extends StatefulWidget {
  const SettlementListScreen({super.key});
  @override
  State<SettlementListScreen> createState() => _SettlementListScreenState();
}

class _SettlementListScreenState extends State<SettlementListScreen> with SingleTickerProviderStateMixin {
  static const _teal = Color(0xFF00838F);
  late TabController _tabs;
  List<HolidayBooking> _completed = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _load();
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await ApiService.instance.getCompletedHolidays();
      if (mounted) setState(() { _completed = data; _loading = false; });
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Tab bar inside the body — no AppBar to avoid Hero conflicts
        Container(
          color: _teal,
          child: TabBar(
            controller: _tabs,
            indicatorColor: Colors.white,
            labelColor: Colors.white,
            unselectedLabelColor: Colors.white70,
            tabs: const [
              Tab(text: 'Trip Settlement'),
              Tab(text: 'Bank'),
            ],
          ),
        ),
        Expanded(
          child: TabBarView(
            controller: _tabs,
            children: [
              _TripSettlementTab(bookings: _completed, loading: _loading, error: _error, onRefresh: _load),
              const BankListScreen(embedded: true),
            ],
          ),
        ),
      ],
    );
  }
}

class _TripSettlementTab extends StatelessWidget {
  final List<HolidayBooking> bookings;
  final bool loading;
  final String? error;
  final VoidCallback onRefresh;
  const _TripSettlementTab({required this.bookings, required this.loading, this.error, required this.onRefresh});

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator(color: Color(0xFF00838F)));
    if (error != null) return Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
      Icon(Icons.error_outline, size: 48, color: Colors.red.shade300),
      const SizedBox(height: 12),
      Text(error!),
      const SizedBox(height: 16),
      ElevatedButton(onPressed: onRefresh, child: const Text('Retry')),
    ]));
    if (bookings.isEmpty) return Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
      Icon(Icons.receipt_long_outlined, size: 64, color: Colors.grey.shade300),
      const SizedBox(height: 16),
      const Text('No completed trips yet', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
      Text('Completed trips appear here for settlement', style: TextStyle(color: Colors.grey.shade500, fontSize: 13)),
    ]));

    return RefreshIndicator(
      onRefresh: () async => onRefresh(),
      color: const Color(0xFF00838F),
      child: ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: bookings.length,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (ctx, i) => _SettlementCard(booking: bookings[i], onRefresh: onRefresh),
      ),
    );
  }
}

class _SettlementCard extends StatelessWidget {
  final HolidayBooking booking;
  final VoidCallback onRefresh;
  const _SettlementCard({required this.booking, required this.onRefresh});

  String _fmt(String d) {
    try {
      final p = d.split('-');
      const m = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      return '${p[2]} ${m[int.parse(p[1])]}';
    } catch (_) { return d; }
  }

  @override
  Widget build(BuildContext context) {
    final settled = booking.hasSettlement;
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () async {
          await Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => SettlementFormScreen(booking: booking)),
          );
          onRefresh();
        },
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Expanded(child: Text(booking.bookingNumber, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15))),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: settled ? const Color(0xFF4CAF50).withOpacity(0.1) : const Color(0xFFFF9800).withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Icon(settled ? Icons.check_circle : Icons.pending_outlined,
                        size: 14, color: settled ? const Color(0xFF4CAF50) : const Color(0xFFFF9800)),
                    const SizedBox(width: 4),
                    Text(settled ? 'Settled' : 'Pending',
                        style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600,
                            color: settled ? const Color(0xFF4CAF50) : const Color(0xFFFF9800))),
                  ]),
                ),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                const Icon(Icons.person_outline, size: 15, color: Colors.grey),
                const SizedBox(width: 6),
                Expanded(child: Text(booking.bookedBy, style: const TextStyle(fontSize: 14))),
              ]),
              const SizedBox(height: 4),
              Row(children: [
                const Icon(Icons.place_outlined, size: 15, color: Colors.grey),
                const SizedBox(width: 6),
                Expanded(child: Text('${booking.departureLocation} → ${booking.destination}',
                    style: TextStyle(color: Colors.grey.shade600, fontSize: 13), overflow: TextOverflow.ellipsis)),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                _chip(_fmt(booking.tripDate), const Color(0xFF00838F)),
                const SizedBox(width: 8),
                if (booking.bookedVehicle != null) _chip(booking.bookedVehicle!, const Color(0xFF2196F3)),
                const Spacer(),
                Text('₹${booking.totalAmount}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Color(0xFF00838F))),
              ]),
            ],
          ),
        ),
      ),
    );
  }

  Widget _chip(String label, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
    decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(20)),
    child: Text(label, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600)),
  );
}
