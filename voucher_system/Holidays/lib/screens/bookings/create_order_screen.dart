import 'package:flutter/material.dart';
import '../../models/models.dart';
import '../../services/api_service.dart';

class CreateOrderScreen extends StatefulWidget {
  final HolidayBooking? existing;
  const CreateOrderScreen({super.key, this.existing});
  @override
  State<CreateOrderScreen> createState() => _CreateOrderScreenState();
}

class _CreateOrderScreenState extends State<CreateOrderScreen> {
  static const _teal = Color(0xFF00838F);
  final _formKey = GlobalKey<FormState>();
  bool _loading = false;
  bool _saving = false;
  String? _error;

  List<Vehicle> _vehicles = [];
  List<PaymentTypeModel> _paymentTypes = [];

  // Controllers
  final _bookedBy = TextEditingController();
  final _contact = TextEditingController();
  final _contact2 = TextEditingController();
  final _departure = TextEditingController();
  final _destination = TextEditingController();
  final _purpose = TextEditingController();
  final _passengers = TextEditingController(text: '1');
  final _totalRent = TextEditingController();
  final _serviceCharge = TextEditingController(text: '0');
  final _advance = TextEditingController(text: '0');
  final _maxKm = TextEditingController();
  final _extraKmCharge = TextEditingController();
  final _instructions = TextEditingController();

  String? _tripDate;
  String? _returnDate;
  String? _departureTime;
  String? _returnTime;
  String _acType = 'NON_AC';
  Vehicle? _selectedVehicle;
  String? _selectedPaymentType;

  bool get _isEdit => widget.existing != null;

  @override
  void initState() {
    super.initState();
    _loadMasterData();
    if (_isEdit) _populateFromExisting();
  }

  void _populateFromExisting() {
    final e = widget.existing!;
    _bookedBy.text = e.bookedBy;
    _contact.text = e.contactNumber;
    _contact2.text = e.secondContactNumber ?? '';
    _departure.text = e.departureLocation;
    _destination.text = e.destination;
    _purpose.text = e.purposeOfBooking ?? '';
    _passengers.text = e.noOfPassengers.toString();
    _totalRent.text = e.totalRent;
    _serviceCharge.text = e.serviceCharge;
    _advance.text = e.advanceAmount;
    _maxKm.text = e.maxKm?.toString() ?? '';
    _extraKmCharge.text = e.extraKmCharge ?? '';
    _instructions.text = e.specialInstructions ?? '';
    _tripDate = e.tripDate;
    _returnDate = e.returnDate;
    _departureTime = e.departureTime;
    _returnTime = e.returnTime;
    _acType = e.acType;
    _selectedPaymentType = e.paymentTypeLabel;
  }

  Future<void> _loadMasterData() async {
    setState(() => _loading = true);
    try {
      final results = await Future.wait([
        ApiService.instance.getVehicles(),
        ApiService.instance.getPaymentTypes(),
      ]);
      if (mounted) {
        setState(() {
          _vehicles = results[0] as List<Vehicle>;
          _paymentTypes = results[1] as List<PaymentTypeModel>;
          _loading = false;
          if (_isEdit && widget.existing!.bookedVehicleId != null) {
            _selectedVehicle = _vehicles.where((v) => v.id == widget.existing!.bookedVehicleId).firstOrNull;
          }
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pickDate(bool isTrip) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: DateTime.now(),
      firstDate: DateTime(2020),
      lastDate: DateTime(2030),
      builder: (ctx, child) => Theme(
        data: Theme.of(ctx).copyWith(colorScheme: const ColorScheme.light(primary: _teal)),
        child: child!,
      ),
    );
    if (picked == null) return;
    final formatted = '${picked.year}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
    setState(() { if (isTrip) _tripDate = formatted; else _returnDate = formatted; });
  }

  Future<void> _pickTime(bool isDeparture) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
      builder: (ctx, child) => Theme(
        data: Theme.of(ctx).copyWith(colorScheme: const ColorScheme.light(primary: _teal)),
        child: child!,
      ),
    );
    if (picked == null) return;
    final formatted = '${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}';
    setState(() { if (isDeparture) _departureTime = formatted; else _returnTime = formatted; });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    if (_tripDate == null) { _showError('Please select trip date'); return; }
    if (_departureTime == null) { _showError('Please select departure time'); return; }

    setState(() { _saving = true; _error = null; });
    try {
      final fields = <String, dynamic>{
        'booked_by': _bookedBy.text.trim(),
        'contact_number': _contact.text.trim(),
        'second_contact_number': _contact2.text.trim(),
        'departure_location': _departure.text.trim(),
        'destination': _destination.text.trim(),
        'purpose_of_booking': _purpose.text.trim(),
        'no_of_passengers': _passengers.text.trim(),
        'trip_date': _tripDate!,
        'return_date': _returnDate ?? '',
        'departure_time': _departureTime!,
        'return_time': _returnTime ?? '',
        'ac_type': _acType,
        'booked_vehicle': _selectedVehicle?.id.toString() ?? '',
        'payment_type_label': _selectedPaymentType ?? '',
        'total_rent': _totalRent.text.trim(),
        'service_charge': _serviceCharge.text.trim(),
        'advance_amount': _advance.text.trim(),
        'max_km': _maxKm.text.trim(),
        'extra_km_charge': _extraKmCharge.text.trim(),
        'special_instructions': _instructions.text.trim(),
      };

      if (_isEdit) {
        await ApiService.instance.updateHoliday(widget.existing!.id, fields);
      } else {
        final stringFields = fields.map((k, v) => MapEntry(k, v.toString()));
        await ApiService.instance.createHoliday(stringFields);
      }

      if (!mounted) return;
      Navigator.of(context).pop(true);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_isEdit ? 'Booking updated!' : 'Booking created!'), backgroundColor: _teal),
      );
    } on ApiException catch (e) {
      setState(() { _error = e.message; _saving = false; });
    } catch (e) {
      setState(() { _error = 'Failed to save booking'; _saving = false; });
    }
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.red));
  }

  @override
  void dispose() {
    for (final c in [_bookedBy, _contact, _contact2, _departure, _destination, _purpose,
      _passengers, _totalRent, _serviceCharge, _advance, _maxKm, _extraKmCharge, _instructions]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4F8),
      appBar: AppBar(
        title: Text(_isEdit ? 'Edit Booking' : 'New Booking'),
        backgroundColor: _teal,
        foregroundColor: Colors.white,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: _teal))
          : Form(
              key: _formKey,
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    if (_error != null) _errorBanner(),
                    _section('Customer Details', [
                      _field('Booked By *', _bookedBy, hint: 'Full name'),
                      _field('Contact Number *', _contact, hint: '10-digit mobile', type: TextInputType.phone, maxLen: 10),
                      _field('Second Contact', _contact2, hint: 'Optional', type: TextInputType.phone, maxLen: 10),
                    ]),
                    _section('Trip Details', [
                      _field('From (Departure) *', _departure, hint: 'Departure location'),
                      _field('To (Destination) *', _destination, hint: 'Destination'),
                      _field('Purpose', _purpose, hint: 'Purpose of booking'),
                      _field('Passengers *', _passengers, hint: '1', type: TextInputType.number),
                      Row(children: [
                        Expanded(child: _dateTile('Trip Date *', _tripDate, () => _pickDate(true))),
                        const SizedBox(width: 12),
                        Expanded(child: _dateTile('Return Date', _returnDate, () => _pickDate(false))),
                      ]),
                      Row(children: [
                        Expanded(child: _dateTile('Departure Time *', _departureTime, () => _pickTime(true), isTime: true)),
                        const SizedBox(width: 12),
                        Expanded(child: _dateTile('Return Time', _returnTime, () => _pickTime(false), isTime: true)),
                      ]),
                    ]),
                    _section('Vehicle & Payment', [
                      _dropdown<Vehicle>(
                        label: 'Vehicle',
                        value: _selectedVehicle,
                        items: _vehicles,
                        itemLabel: (v) => '${v.name} (${v.registrationNumber})',
                        onChanged: (v) => setState(() => _selectedVehicle = v),
                      ),
                      _acSelector(),
                      _dropdown<String>(
                        label: 'Payment Type',
                        value: _selectedPaymentType,
                        items: _paymentTypes.map((p) => p.name).toList(),
                        itemLabel: (s) => s,
                        onChanged: (s) => setState(() => _selectedPaymentType = s),
                      ),
                    ]),
                    _section('Pricing', [
                      _field('Total Rent *', _totalRent, hint: '0.00', type: TextInputType.number),
                      _field('Service Charge', _serviceCharge, hint: '0.00', type: TextInputType.number),
                      _field('Advance Amount', _advance, hint: '0.00', type: TextInputType.number),
                      _field('Max KM', _maxKm, hint: 'Optional', type: TextInputType.number),
                      _field('Extra KM Charge', _extraKmCharge, hint: 'Per KM rate', type: TextInputType.number),
                    ]),
                    _section('Other', [
                      _field('Special Instructions', _instructions, hint: 'Any special notes', maxLines: 3),
                    ]),
                    const SizedBox(height: 80),
                  ],
                ),
              ),
            ),
      floatingActionButton: _saving
          ? null
          : FloatingActionButton.extended(
              backgroundColor: _teal,
              foregroundColor: Colors.white,
              onPressed: _saving ? null : _save,
              icon: _saving
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.save),
              label: Text(_isEdit ? 'Update' : 'Create Booking'),
            ),
    );
  }

  Widget _errorBanner() => Container(
    margin: const EdgeInsets.only(bottom: 16),
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(color: const Color(0xFFFFEBEE), borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.red.shade200)),
    child: Row(children: [
      const Icon(Icons.error_outline, color: Colors.red, size: 20),
      const SizedBox(width: 10),
      Expanded(child: Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 13))),
    ]),
  );

  Widget _section(String title, List<Widget> children) => Card(
    margin: const EdgeInsets.only(bottom: 12),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Color(0xFF00838F))),
        const SizedBox(height: 14),
        ...children.map((w) => Padding(padding: const EdgeInsets.only(bottom: 12), child: w)),
      ]),
    ),
  );

  Widget _field(String label, TextEditingController ctrl, {String? hint, TextInputType type = TextInputType.text, int? maxLen, int maxLines = 1, bool required = false}) {
    return TextFormField(
      controller: ctrl,
      keyboardType: type,
      maxLength: maxLen,
      maxLines: maxLines,
      decoration: InputDecoration(labelText: label, hintText: hint, counterText: ''),
      validator: label.endsWith('*') ? (v) => (v == null || v.trim().isEmpty) ? 'Required' : null : null,
    );
  }

  Widget _dateTile(String label, String? value, VoidCallback onTap, {bool isTime = false}) => GestureDetector(
    onTap: onTap,
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Row(children: [
        Icon(isTime ? Icons.access_time : Icons.calendar_today_outlined, size: 18, color: Colors.grey),
        const SizedBox(width: 8),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
          Text(value ?? 'Select', style: TextStyle(fontSize: 13, color: value != null ? const Color(0xFF1A2E3B) : Colors.grey)),
        ])),
      ]),
    ),
  );

  Widget _acSelector() => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text('AC Type', style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
    const SizedBox(height: 8),
    Row(children: [
      _acOption('AC', 'AC'),
      const SizedBox(width: 12),
      _acOption('NON_AC', 'Non-AC'),
    ]),
  ]);

  Widget _acOption(String value, String label) => GestureDetector(
    onTap: () => setState(() => _acType = value),
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      decoration: BoxDecoration(
        color: _acType == value ? const Color(0xFF00838F) : Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _acType == value ? const Color(0xFF00838F) : Colors.grey.shade300),
      ),
      child: Text(label, style: TextStyle(color: _acType == value ? Colors.white : Colors.grey.shade700, fontWeight: FontWeight.w600)),
    ),
  );

  Widget _dropdown<T>({required String label, required T? value, required List<T> items, required String Function(T) itemLabel, required void Function(T?) onChanged}) {
    return DropdownButtonFormField<T>(
      value: value,
      decoration: InputDecoration(labelText: label),
      isExpanded: true,
      items: [
        DropdownMenuItem<T>(value: null, child: Text('-- None --', style: TextStyle(color: Colors.grey.shade500))),
        ...items.map((item) => DropdownMenuItem<T>(value: item, child: Text(itemLabel(item), overflow: TextOverflow.ellipsis))),
      ],
      onChanged: onChanged,
    );
  }
}
