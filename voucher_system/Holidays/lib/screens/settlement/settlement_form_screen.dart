import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import '../../models/models.dart';
import '../../services/api_service.dart';

class SettlementFormScreen extends StatefulWidget {
  final HolidayBooking booking;
  const SettlementFormScreen({super.key, required this.booking});
  @override
  State<SettlementFormScreen> createState() => _SettlementFormScreenState();
}

class _SettlementFormScreenState extends State<SettlementFormScreen> {
  static const _teal = Color(0xFF00838F);
  static const _coral = Color(0xFFFF6B35);

  TripSettlement? _settlement;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  final _extraRent = TextEditingController();
  final _commPct = TextEditingController();
  final _battaPct = TextEditingController();
  final _diesel = TextEditingController();
  final _cleaning = TextEditingController();
  final _grease = TextEditingController();

  // Computed display values
  double _commAmt = 0, _netRent = 0, _battaAmt = 0, _netBalance = 0, _adjustedTotal = 0;

  // File paths for uploads
  String? _dieselBillPath;
  String? _greaseBillPath;

  // Custom charges
  final List<CustomCharge> _customCharges = [];
  final List<String?> _customFilePaths = [];

  @override
  void initState() {
    super.initState();
    _load();
    for (final c in [_extraRent, _commPct, _battaPct, _diesel, _cleaning, _grease]) {
      c.addListener(_recalculate);
    }
  }

  @override
  void dispose() {
    for (final c in [_extraRent, _commPct, _battaPct, _diesel, _cleaning, _grease]) {
      c.removeListener(_recalculate);
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final s = await ApiService.instance.getSettlement(widget.booking.id);
      if (!mounted) return;
      setState(() {
        _settlement = s;
        _loading = false;
        if (s.exists) {
          _extraRent.text = s.extraRent;
          _commPct.text = s.commissionPercentage;
          _battaPct.text = s.battaPercentage;
          _diesel.text = s.dieselCharge;
          _cleaning.text = s.cleaningCharge;
          _grease.text = s.greaseCharge;
          _customCharges.addAll(s.customCharges);
          _customFilePaths.addAll(List.filled(s.customCharges.length, null));
        } else {
          _battaPct.text = widget.booking.bookedVehicleBatta;
          _commPct.text = '0';
          _diesel.text = '0';
          _cleaning.text = '0';
          _grease.text = '0';
        }
        _recalculate();
      });
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _loading = false; });
    }
  }

  void _recalculate() {
    final total = double.tryParse(widget.booking.totalAmount) ?? 0;
    final extraRent = double.tryParse(_extraRent.text) ?? 0;
    final adjustedTotal = total + extraRent;
    final commPct = double.tryParse(_commPct.text) ?? 0;
    final battaPct = double.tryParse(_battaPct.text) ?? 0;
    final diesel = double.tryParse(_diesel.text) ?? 0;
    final cleaning = double.tryParse(_cleaning.text) ?? 0;
    final grease = double.tryParse(_grease.text) ?? 0;
    final customTotal = _customCharges.fold(0.0, (sum, c) => sum + (double.tryParse(c.amount) ?? 0));

    final commAmt = (adjustedTotal * commPct / 100);
    final battaAmt = (adjustedTotal * battaPct / 100);
    final netRent = adjustedTotal - commAmt - battaAmt;
    final netBalance = netRent - diesel - cleaning - grease - customTotal;

    if (mounted) setState(() {
      _adjustedTotal = adjustedTotal;
      _commAmt = commAmt;
      _netRent = netRent;
      _battaAmt = battaAmt;
      _netBalance = netBalance;
    });
  }

  Future<void> _pickFile(bool isDiesel) async {
    final choice = await _showFilePickerDialog();
    if (choice == null) return;
    String? path;
    if (choice == 'camera') {
      final picked = await ImagePicker().pickImage(source: ImageSource.camera, imageQuality: 80);
      path = picked?.path;
    } else if (choice == 'gallery') {
      final picked = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 80);
      path = picked?.path;
    } else {
      final result = await FilePicker.platform.pickFiles(type: FileType.any);
      path = result?.files.single.path;
    }
    if (path == null) return;
    setState(() { if (isDiesel) _dieselBillPath = path; else _greaseBillPath = path; });
  }

  Future<void> _pickCustomFile(int index) async {
    final choice = await _showFilePickerDialog();
    if (choice == null) return;
    String? path;
    if (choice == 'camera') {
      final picked = await ImagePicker().pickImage(source: ImageSource.camera, imageQuality: 80);
      path = picked?.path;
    } else if (choice == 'gallery') {
      final picked = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 80);
      path = picked?.path;
    } else {
      final result = await FilePicker.platform.pickFiles(type: FileType.any);
      path = result?.files.single.path;
    }
    if (path == null) return;
    setState(() { _customFilePaths[index] = path; });
  }

  Future<String?> _showFilePickerDialog() => showModalBottomSheet<String>(
    context: context,
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
    builder: (_) => Column(mainAxisSize: MainAxisSize.min, children: [
      const SizedBox(height: 12),
      Container(width: 40, height: 4, decoration: BoxDecoration(color: Colors.grey.shade300, borderRadius: BorderRadius.circular(2))),
      const SizedBox(height: 16),
      const Text('Attach File', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
      const SizedBox(height: 8),
      ListTile(leading: const Icon(Icons.camera_alt, color: Color(0xFF00838F)), title: const Text('Camera'), onTap: () => Navigator.pop(context, 'camera')),
      ListTile(leading: const Icon(Icons.photo_library, color: Color(0xFF00838F)), title: const Text('Gallery'), onTap: () => Navigator.pop(context, 'gallery')),
      ListTile(leading: const Icon(Icons.attach_file, color: Color(0xFF00838F)), title: const Text('Browse File'), onTap: () => Navigator.pop(context, 'file')),
      const SizedBox(height: 16),
    ]),
  );

  void _addCustomCharge() {
    setState(() {
      _customCharges.add(CustomCharge(name: '', amount: '0'));
      _customFilePaths.add(null);
    });
  }

  void _removeCustomCharge(int i) {
    setState(() {
      _customCharges.removeAt(i);
      _customFilePaths.removeAt(i);
    });
    _recalculate();
  }

  Future<void> _save() async {
    setState(() { _saving = true; _error = null; });
    try {
      final fields = <String, String>{
        'extra_rent': _extraRent.text.isEmpty ? '0' : _extraRent.text,
        'commission_percentage': _commPct.text,
        'batta_percentage': _battaPct.text,
        'diesel_charge': _diesel.text,
        'cleaning_charge': _cleaning.text,
        'grease_charge': _grease.text,
        'custom_count': _customCharges.length.toString(),
      };
      for (int i = 0; i < _customCharges.length; i++) {
        fields['custom_name_$i'] = _customCharges[i].name;
        fields['custom_amount_$i'] = _customCharges[i].amount;
      }

      final files = <String, String>{};
      if (_dieselBillPath != null) files['diesel_bill'] = _dieselBillPath!;
      if (_greaseBillPath != null) files['grease_bill'] = _greaseBillPath!;
      for (int i = 0; i < _customFilePaths.length; i++) {
        if (_customFilePaths[i] != null) files['custom_file_$i'] = _customFilePaths[i]!;
      }

      await ApiService.instance.saveSettlement(widget.booking.id, fields, files);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Settlement saved!'), backgroundColor: Color(0xFF4CAF50)),
      );
      _load();
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _saving = false; });
    } catch (e) {
      if (mounted) setState(() { _error = 'Failed to save'; _saving = false; });
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4F8),
      appBar: AppBar(
        title: Text('Settlement · ${widget.booking.bookingNumber}'),
        backgroundColor: _teal,
        foregroundColor: Colors.white,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: _teal))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(children: [
                if (_error != null) _errorBanner(),
                // Booking summary
                _summaryCard(),
                // Net balance display
                _balanceCard(),
                // Extra Rent
                _card('Extra Rent', [
                  _extraRentField(),
                ]),
                // Commission
                _card('Commission', [
                  _calcRow('Commission %', _commPct, '₹${_commAmt.toStringAsFixed(2)}', 'commission_amount'),
                  _infoRow('Net Rent', '₹${_netRent.toStringAsFixed(2)}'),
                ]),
                // Batta
                _card('Driver Batta', [
                  _calcRow('Batta %', _battaPct, '₹${_battaAmt.toStringAsFixed(2)}', 'batta_amount'),
                ]),
                // Deductions
                _card('Deductions', [
                  _fileField('Diesel Charge', _diesel, _dieselBillPath, _settlement?.dieselBillName, () => _pickFile(true)),
                  _fileField('Cleaning Charge', _cleaning, null, null, null),
                  _fileField('Grease Charge', _grease, _greaseBillPath, _settlement?.greaseBillName, () => _pickFile(false)),
                ]),
                // Custom charges
                _customChargesCard(),
                const SizedBox(height: 80),
              ]),
            ),
      floatingActionButton: _settlement?.bankIsApproved == true
          ? null
          : FloatingActionButton.extended(
              backgroundColor: _saving ? Colors.grey : _teal,
              foregroundColor: Colors.white,
              onPressed: _saving ? null : _save,
              icon: _saving
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.save),
              label: const Text('Save Settlement'),
            ),
    );
  }

  Widget _summaryCard() => Card(
    margin: const EdgeInsets.only(bottom: 12),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Row(children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.booking.bookedBy, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
          Text('${widget.booking.departureLocation} → ${widget.booking.destination}', style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
          if (widget.booking.bookedVehicle != null)
            Text(widget.booking.bookedVehicle!, style: TextStyle(color: _teal, fontSize: 12)),
        ])),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text('₹${widget.booking.totalAmount}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: _teal)),
          Text('Total Amount', style: TextStyle(color: Colors.grey.shade500, fontSize: 11)),
        ]),
      ]),
    ),
  );

  Widget _balanceCard() => Container(
    margin: const EdgeInsets.only(bottom: 12),
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      gradient: LinearGradient(
        colors: _netBalance >= 0 ? [const Color(0xFF00838F), const Color(0xFF006064)] : [Colors.red.shade400, Colors.red.shade700],
        begin: Alignment.topLeft, end: Alignment.bottomRight,
      ),
      borderRadius: BorderRadius.circular(16),
    ),
    child: Row(children: [
      const Icon(Icons.account_balance_wallet, color: Colors.white, size: 36),
      const SizedBox(width: 16),
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Net Balance', style: TextStyle(color: Colors.white70, fontSize: 13)),
        Text('₹${_netBalance.toStringAsFixed(2)}', style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold)),
      ]),
      if (_settlement?.bankIsApproved == true) ...[
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(20)),
          child: const Text('Bank Approved', style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
        ),
      ],
    ]),
  );

  Widget _card(String title, List<Widget> children) => Card(
    margin: const EdgeInsets.only(bottom: 12),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: _teal)),
        const Divider(height: 16),
        ...children,
      ]),
    ),
  );

  Widget _extraRentField() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      TextFormField(
        controller: _extraRent,
        keyboardType: TextInputType.number,
        decoration: const InputDecoration(labelText: 'Extra Rent (₹)', prefixText: '₹ '),
        onTap: () => _extraRent.selection = TextSelection(baseOffset: 0, extentOffset: _extraRent.text.length),
      ),
      const SizedBox(height: 8),
      Row(children: [
        Text('Adjusted Total', style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
        const Spacer(),
        Text('₹${_adjustedTotal.toStringAsFixed(2)}',
            style: const TextStyle(fontWeight: FontWeight.bold, color: _teal, fontSize: 15)),
      ]),
    ],
  );

  Widget _calcRow(String label, TextEditingController ctrl, String computed, String key) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Row(children: [
      Expanded(child: TextFormField(
        controller: ctrl,
        keyboardType: TextInputType.number,
        decoration: InputDecoration(labelText: label, suffixText: '%'),
        onTap: () => ctrl.selection = TextSelection(baseOffset: 0, extentOffset: ctrl.text.length),
      )),
      const SizedBox(width: 12),
      Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
        Text('Amount', style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),
        Text(computed, style: const TextStyle(fontWeight: FontWeight.bold, color: _teal, fontSize: 15)),
      ]),
    ]),
  );

  Widget _infoRow(String label, String value) => Padding(
    padding: const EdgeInsets.only(bottom: 4),
    child: Row(children: [
      Text(label, style: TextStyle(color: Colors.grey.shade600)),
      const Spacer(),
      Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
    ]),
  );

  Widget _fileField(String label, TextEditingController ctrl, String? localPath, String? serverFileName, VoidCallback? onPick) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      TextFormField(
        controller: ctrl,
        keyboardType: TextInputType.number,
        decoration: InputDecoration(labelText: label, prefixText: '₹ '),
        onTap: () => ctrl.selection = TextSelection(baseOffset: 0, extentOffset: ctrl.text.length),
      ),
      if (onPick != null) ...[
        const SizedBox(height: 6),
        GestureDetector(
          onTap: onPick,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: _teal.withOpacity(0.08),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: _teal.withOpacity(0.3)),
            ),
            child: Row(children: [
              const Icon(Icons.attach_file, size: 16, color: _teal),
              const SizedBox(width: 6),
              Expanded(child: Text(
                localPath?.split('/').last ?? serverFileName ?? 'Attach bill (optional)',
                style: TextStyle(fontSize: 12, color: (localPath != null || serverFileName != null) ? _teal : Colors.grey.shade500),
                overflow: TextOverflow.ellipsis,
              )),
              if (localPath != null || serverFileName != null)
                const Icon(Icons.check_circle, size: 14, color: Color(0xFF4CAF50)),
            ]),
          ),
        ),
      ],
    ]),
  );

  Widget _customChargesCard() => Card(
    margin: const EdgeInsets.only(bottom: 12),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Text('Custom Charges', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: _teal)),
          const Spacer(),
          TextButton.icon(icon: const Icon(Icons.add, size: 18), label: const Text('Add'), onPressed: _addCustomCharge),
        ]),
        const Divider(height: 8),
        ..._customCharges.asMap().entries.map((entry) {
          final i = entry.key;
          final c = entry.value;
          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.grey.shade50,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.grey.shade200),
            ),
            child: Column(children: [
              Row(children: [
                Expanded(child: TextFormField(
                  initialValue: c.name,
                  decoration: const InputDecoration(labelText: 'Description', isDense: true),
                  onChanged: (v) { c.name = v; },
                )),
                const SizedBox(width: 8),
                SizedBox(width: 100, child: TextFormField(
                  initialValue: c.amount,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Amount', isDense: true, prefixText: '₹'),
                  onChanged: (v) { c.amount = v; _recalculate(); },
                )),
                IconButton(icon: const Icon(Icons.remove_circle_outline, color: Colors.red), onPressed: () => _removeCustomCharge(i)),
              ]),
              const SizedBox(height: 6),
              GestureDetector(
                onTap: () => _pickCustomFile(i),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(color: _teal.withOpacity(0.06), borderRadius: BorderRadius.circular(8), border: Border.all(color: _teal.withOpacity(0.2))),
                  child: Row(children: [
                    const Icon(Icons.attach_file, size: 14, color: _teal),
                    const SizedBox(width: 6),
                    Expanded(child: Text(
                      _customFilePaths[i]?.split('/').last ?? c.attachmentName ?? 'Attach receipt (optional)',
                      style: TextStyle(fontSize: 11, color: (_customFilePaths[i] != null || c.attachmentName != null) ? _teal : Colors.grey.shade500),
                      overflow: TextOverflow.ellipsis,
                    )),
                  ]),
                ),
              ),
            ]),
          );
        }),
        if (_customCharges.isEmpty)
          Center(child: Text('No custom charges added', style: TextStyle(color: Colors.grey.shade400, fontSize: 13))),
      ]),
    ),
  );

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
}
