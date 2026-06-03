import 'package:flutter/material.dart';
import '../../models/models.dart';
import '../../services/api_service.dart';
import 'order_detail_screen.dart';

class UpcomingListScreen extends StatefulWidget {
  const UpcomingListScreen({super.key});
  @override
  State<UpcomingListScreen> createState() => _UpcomingListScreenState();
}

class _UpcomingListScreenState extends State<UpcomingListScreen> {
  static const _teal = Color(0xFF00838F);
  List<HolidayBooking> _bookings = [];
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
      final data = await ApiService.instance.getHolidays(status: 'CONFIRMED');
      if (mounted) setState(() { _bookings = data; _loading = false; });
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
                ? _errorView()
                : _bookings.isEmpty
                    ? _emptyView()
                    : ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: _bookings.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (_, i) => _UpcomingCard(
                          booking: _bookings[i],
                          onTap: () async {
                            await Navigator.of(context).push(
                              MaterialPageRoute(builder: (_) => OrderDetailScreen(bookingId: _bookings[i].id)),
                            );
                            _load();
                          },
                        ),
                      ),
      ),
    );
  }

  Widget _errorView() => ListView(children: [
    const SizedBox(height: 120),
    Center(child: Column(children: [
      Icon(Icons.error_outline, size: 56, color: Colors.red.shade300),
      const SizedBox(height: 16),
      Text(_error!, textAlign: TextAlign.center),
      const SizedBox(height: 20),
      ElevatedButton(onPressed: _load, child: const Text('Retry')),
    ])),
  ]);

  Widget _emptyView() => ListView(children: [
    const SizedBox(height: 120),
    Center(child: Column(children: [
      Icon(Icons.event_outlined, size: 64, color: Colors.grey.shade300),
      const SizedBox(height: 16),
      const Text('No upcoming trips', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
      const SizedBox(height: 8),
      Text('Confirmed bookings will appear here', style: TextStyle(color: Colors.grey.shade500)),
    ])),
  ]);
}

class _UpcomingCard extends StatelessWidget {
  final HolidayBooking booking;
  final VoidCallback onTap;
  const _UpcomingCard({required this.booking, required this.onTap});

  String _fmt(String d) {
    try {
      final p = d.split('-');
      const m = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      return '${p[2]} ${m[int.parse(p[1])]}';
    } catch (_) { return d; }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Column(
          children: [
            // Green top banner
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: const BoxDecoration(
                color: Color(0xFF4CAF50),
                borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
              ),
              child: Row(
                children: [
                  Text(booking.bookingNumber, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14)),
                  const Spacer(),
                  const Icon(Icons.check_circle, color: Colors.white, size: 18),
                  const SizedBox(width: 4),
                  const Text('Confirmed', style: TextStyle(color: Colors.white, fontSize: 12)),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(booking.bookedBy, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                            const SizedBox(height: 4),
                            Row(children: [
                              const Icon(Icons.place_outlined, size: 14, color: Colors.grey),
                              const SizedBox(width: 4),
                              Expanded(child: Text('${booking.departureLocation} → ${booking.destination}',
                                  style: TextStyle(color: Colors.grey.shade600, fontSize: 13), overflow: TextOverflow.ellipsis)),
                            ]),
                          ],
                        ),
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text('₹${booking.totalAmount}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Color(0xFF00838F))),
                          Text('Balance: ₹${booking.balanceAmount}', style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      _chip(Icons.calendar_today_outlined, _fmt(booking.tripDate), const Color(0xFF4CAF50)),
                      const SizedBox(width: 8),
                      if (booking.returnDate != null)
                        _chip(Icons.event_available_outlined, _fmt(booking.returnDate!), const Color(0xFF00838F)),
                      const SizedBox(width: 8),
                      _chip(Icons.people_outline, '${booking.noOfPassengers} pax', const Color(0xFF2196F3)),
                    ],
                  ),
                  if (booking.bookedVehicle != null) ...[
                    const SizedBox(height: 8),
                    Row(children: [
                      const Icon(Icons.directions_car_outlined, size: 14, color: Colors.grey),
                      const SizedBox(width: 4),
                      Text(booking.bookedVehicle!, style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: booking.acType == 'AC' ? Colors.blue.shade50 : Colors.grey.shade100,
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(booking.acType, style: TextStyle(fontSize: 11, color: booking.acType == 'AC' ? Colors.blue : Colors.grey.shade600)),
                      ),
                    ]),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(IconData icon, String label, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(20)),
    child: Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 13, color: color),
      const SizedBox(width: 4),
      Text(label, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600)),
    ]),
  );
}
