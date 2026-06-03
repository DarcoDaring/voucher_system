import 'package:flutter/material.dart';
import '../../models/models.dart';
import '../../services/api_service.dart';
import 'create_order_screen.dart';
import '../settlement/settlement_form_screen.dart';

class OrderDetailScreen extends StatefulWidget {
  final int bookingId;
  const OrderDetailScreen({super.key, required this.bookingId});
  @override
  State<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends State<OrderDetailScreen> {
  static const _teal = Color(0xFF00838F);
  HolidayBooking? _booking;
  bool _loading = true;
  String? _error;
  bool _actionLoading = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final b = await ApiService.instance.getHolidayDetail(widget.bookingId);
      if (mounted) setState(() { _booking = b; _loading = false; });
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _loading = false; });
    }
  }

  Future<void> _confirm() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Confirm Booking'),
        content: Text('Confirm booking ${_booking!.bookingNumber}? This will move it to Upcoming.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(context, true), child: const Text('Confirm')),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _actionLoading = true);
    try {
      await ApiService.instance.confirmHoliday(widget.bookingId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Booking confirmed!'), backgroundColor: Color(0xFF4CAF50)),
      );
      _load();
    } on ApiException catch (e) {
      if (mounted) _showError(e.message);
    } finally {
      if (mounted) setState(() => _actionLoading = false);
    }
  }

  Future<void> _delete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Delete Booking'),
        content: const Text('This action cannot be undone. Are you sure?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _actionLoading = true);
    try {
      await ApiService.instance.deleteHoliday(widget.bookingId);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (mounted) _showError(e.message);
      setState(() => _actionLoading = false);
    }
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.red));
  }

  @override
  Widget build(BuildContext context) {
    final perms = ApiService.instance.permissions;
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4F8),
      appBar: AppBar(
        title: Text(_booking?.bookingNumber ?? 'Booking Detail'),
        backgroundColor: _teal,
        foregroundColor: Colors.white,
        actions: [
          if (_booking != null && perms?.canEdit == true && _booking!.status == 'PENDING' && !_booking!.isBankApproved)
            IconButton(
              icon: const Icon(Icons.edit_outlined),
              onPressed: () async {
                await Navigator.of(context).push(MaterialPageRoute(builder: (_) => CreateOrderScreen(existing: _booking)));
                _load();
              },
            ),
          if (_booking != null && perms?.canDelete == true && !_booking!.isBankApproved)
            IconButton(icon: const Icon(Icons.delete_outline), onPressed: _actionLoading ? null : _delete),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: _teal))
          : _error != null
              ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Icon(Icons.error_outline, size: 56, color: Colors.red.shade300),
                  const SizedBox(height: 16),
                  Text(_error!),
                  const SizedBox(height: 20),
                  ElevatedButton(onPressed: _load, child: const Text('Retry')),
                ]))
              : _buildBody(),
    );
  }

  Widget _buildBody() {
    final b = _booking!;
    final perms = ApiService.instance.permissions;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Status banner
          _statusBanner(b),
          const SizedBox(height: 16),
          // Customer info
          _card('Customer Information', [
            _row('Booked By', b.bookedBy),
            _row('Contact', b.contactNumber),
            if (b.secondContactNumber?.isNotEmpty == true)
              _row('Contact 2', b.secondContactNumber!),
          ]),
          // Trip info
          _card('Trip Details', [
            _row('From', b.departureLocation),
            _row('To', b.destination),
            if (b.purposeOfBooking?.isNotEmpty == true)
              _row('Purpose', b.purposeOfBooking!),
            _row('Passengers', b.noOfPassengers.toString()),
            _row('Trip Date', _fmtDate(b.tripDate)),
            if (b.returnDate != null) _row('Return Date', _fmtDate(b.returnDate!)),
            if (b.departureTime != null) _row('Departure Time', b.departureTime!),
            if (b.returnTime != null) _row('Return Time', b.returnTime!),
          ]),
          // Vehicle info
          _card('Vehicle & Payment', [
            _row('Vehicle', b.bookedVehicle ?? 'Not assigned'),
            _row('AC Type', b.acType == 'AC' ? 'AC' : 'Non-AC'),
            if (b.paymentTypeLabel?.isNotEmpty == true)
              _row('Payment', b.paymentTypeLabel!),
            if (b.maxKm != null) _row('Max KM', b.maxKm.toString()),
            if (b.extraKmCharge != null) _row('Extra KM Rate', '₹${b.extraKmCharge}'),
          ]),
          // Pricing
          _card('Pricing', [
            _row('Total Rent', '₹${b.totalRent}'),
            _row('Service Charge', '₹${b.serviceCharge}'),
            _row('Total Amount', '₹${b.totalAmount}', bold: true),
            _row('Advance', '₹${b.advanceAmount}'),
            _row('Balance Due', '₹${b.balanceAmount}', highlight: true),
          ]),
          if (b.specialInstructions?.isNotEmpty == true)
            _card('Special Instructions', [
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Text(b.specialInstructions!, style: TextStyle(color: Colors.grey.shade700)),
              ),
            ]),
          if (b.createdBy != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text('Created by ${b.createdBy} · ${b.createdAt ?? ''}',
                  style: TextStyle(color: Colors.grey.shade500, fontSize: 12), textAlign: TextAlign.center),
            ),
          // Actions
          if (_actionLoading)
            const Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator(color: _teal))
          else ...[
            if (b.status == 'PENDING' && perms?.canEdit == true)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  icon: const Icon(Icons.check_circle_outline),
                  label: const Text('Confirm Booking'),
                  style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF4CAF50)),
                  onPressed: _confirm,
                ),
              ),
            const SizedBox(height: 8),
            if (b.status == 'COMPLETED' && perms?.canEdit == true)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  icon: const Icon(Icons.receipt_long),
                  label: Text(b.hasSettlement ? 'View Settlement' : 'Create Settlement'),
                  onPressed: () async {
                    await Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => SettlementFormScreen(booking: b)),
                    );
                    _load();
                  },
                ),
              ),
          ],
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _statusBanner(HolidayBooking b) {
    final color = _statusColor(b.status);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Icon(_statusIcon(b.status), color: color, size: 28),
          const SizedBox(width: 12),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(b.statusLabel, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 16)),
            if (b.isBankApproved)
              const Text('Bank Approved', style: TextStyle(color: Color(0xFF4CAF50), fontSize: 12)),
          ]),
        ],
      ),
    );
  }

  Widget _card(String title, List<Widget> children) => Card(
    margin: const EdgeInsets.only(bottom: 12),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Color(0xFF00838F))),
        const Divider(height: 16),
        ...children,
      ]),
    ),
  );

  Widget _row(String label, String value, {bool bold = false, bool highlight = false}) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(width: 130, child: Text(label, style: TextStyle(color: Colors.grey.shade600, fontSize: 13))),
        Expanded(child: Text(value, style: TextStyle(
          fontSize: 13,
          fontWeight: bold || highlight ? FontWeight.bold : FontWeight.normal,
          color: highlight ? const Color(0xFF00838F) : const Color(0xFF1A2E3B),
        ))),
      ],
    ),
  );

  String _fmtDate(String d) {
    try {
      final p = d.split('-');
      const m = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      return '${p[2]} ${m[int.parse(p[1])]} ${p[0]}';
    } catch (_) { return d; }
  }

  Color _statusColor(String s) {
    switch (s) {
      case 'PENDING': return const Color(0xFF2196F3);
      case 'CONFIRMED': return const Color(0xFF4CAF50);
      case 'COMPLETED': return const Color(0xFF00838F);
      case 'CANCELLED': return Colors.red;
      default: return Colors.grey;
    }
  }

  IconData _statusIcon(String s) {
    switch (s) {
      case 'PENDING': return Icons.hourglass_empty;
      case 'CONFIRMED': return Icons.check_circle;
      case 'COMPLETED': return Icons.done_all;
      case 'CANCELLED': return Icons.cancel;
      default: return Icons.info;
    }
  }
}
