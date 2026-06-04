import 'package:flutter/material.dart';
import '../../models/models.dart';
import '../../services/api_service.dart';
import 'order_detail_screen.dart';
import 'create_order_screen.dart';

class EnquiryListScreen extends StatefulWidget {
  const EnquiryListScreen({super.key});
  @override
  State<EnquiryListScreen> createState() => _EnquiryListScreenState();
}

class _EnquiryListScreenState extends State<EnquiryListScreen> {
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
      if (ApiService.instance.permissions == null) {
        await ApiService.instance.getPermissions();
      }
      final data = await ApiService.instance.getHolidays(status: 'PENDING');
      if (mounted) setState(() { _bookings = data; _loading = false; });
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = 'Failed to load enquiries'; _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final canCreate = ApiService.instance.permissions?.canCreate ?? true;
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4F8),
      body: RefreshIndicator(
        onRefresh: _load,
        color: _teal,
        child: _loading
            ? const Center(child: CircularProgressIndicator(color: _teal))
            : _error != null
                ? _ErrorView(message: _error!, onRetry: _load)
                : _bookings.isEmpty
                    ? _EmptyView(
                        icon: Icons.help_outline,
                        message: 'No enquiries found',
                        subtitle: 'Create a new booking to get started',
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: _bookings.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (_, i) => _BookingCard(
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
      floatingActionButton: canCreate
          ? FloatingActionButton.extended(
              backgroundColor: _teal,
              foregroundColor: Colors.white,
              onPressed: () async {
                await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CreateOrderScreen()));
                _load();
              },
              icon: const Icon(Icons.add),
              label: const Text('New Booking'),
            )
          : null,
    );
  }
}

class _BookingCard extends StatelessWidget {
  final HolidayBooking booking;
  final VoidCallback onTap;
  const _BookingCard({required this.booking, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: _statusColor(booking.status).withOpacity(0.12),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      booking.bookingNumber,
                      style: TextStyle(fontWeight: FontWeight.bold, color: _statusColor(booking.status), fontSize: 13),
                    ),
                  ),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: _statusColor(booking.status).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(booking.statusLabel, style: TextStyle(color: _statusColor(booking.status), fontSize: 11, fontWeight: FontWeight.w600)),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  const Icon(Icons.person_outline, size: 16, color: Colors.grey),
                  const SizedBox(width: 6),
                  Expanded(child: Text(booking.bookedBy, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15), overflow: TextOverflow.ellipsis)),
                ],
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  const Icon(Icons.place_outlined, size: 16, color: Colors.grey),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      '${booking.departureLocation} → ${booking.destination}',
                      style: TextStyle(color: Colors.grey.shade700, fontSize: 13),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  const Icon(Icons.calendar_today_outlined, size: 16, color: Colors.grey),
                  const SizedBox(width: 6),
                  Text(_formatDate(booking.tripDate), style: TextStyle(color: Colors.grey.shade700, fontSize: 13)),
                  if (booking.returnDate != null) ...[
                    Text(' → ${_formatDate(booking.returnDate!)}', style: TextStyle(color: Colors.grey.shade700, fontSize: 13)),
                  ],
                  const Spacer(),
                  Text('₹${booking.totalAmount}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Color(0xFF00838F))),
                ],
              ),
              if (booking.bookedVehicle != null) ...[
                const SizedBox(height: 6),
                Row(
                  children: [
                    const Icon(Icons.directions_car_outlined, size: 16, color: Colors.grey),
                    const SizedBox(width: 6),
                    Text(booking.bookedVehicle!, style: TextStyle(color: Colors.grey.shade700, fontSize: 13)),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'PENDING': return const Color(0xFF2196F3);
      case 'CONFIRMED': return const Color(0xFF4CAF50);
      case 'COMPLETED': return const Color(0xFF00838F);
      case 'CANCELLED': return Colors.red;
      default: return Colors.grey;
    }
  }

  String _formatDate(String d) {
    try {
      final parts = d.split('-');
      const months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      return '${parts[2]} ${months[int.parse(parts[1])]} ${parts[0]}';
    } catch (_) { return d; }
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});
  @override
  Widget build(BuildContext context) => ListView(
    children: [
      const SizedBox(height: 120),
      Center(
        child: Column(children: [
          Icon(Icons.error_outline, size: 56, color: Colors.red.shade300),
          const SizedBox(height: 16),
          Text(message, textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade700)),
          const SizedBox(height: 20),
          ElevatedButton(onPressed: onRetry, child: const Text('Retry')),
        ]),
      ),
    ],
  );
}

class _EmptyView extends StatelessWidget {
  final IconData icon;
  final String message;
  final String subtitle;
  const _EmptyView({required this.icon, required this.message, required this.subtitle});
  @override
  Widget build(BuildContext context) => ListView(
    children: [
      const SizedBox(height: 120),
      Center(
        child: Column(children: [
          Icon(icon, size: 64, color: Colors.grey.shade300),
          const SizedBox(height: 16),
          Text(message, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFF1A2E3B))),
          const SizedBox(height: 8),
          Text(subtitle, style: TextStyle(color: Colors.grey.shade500, fontSize: 14)),
        ]),
      ),
    ],
  );
}
