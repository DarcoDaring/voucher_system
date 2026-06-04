import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import '../../models/models.dart';
import '../../services/api_service.dart';

class RepairCreateScreen extends StatefulWidget {
  const RepairCreateScreen({super.key});
  @override
  State<RepairCreateScreen> createState() => _RepairCreateScreenState();
}

class _RepairCreateScreenState extends State<RepairCreateScreen> {
  static const _teal = Color(0xFF00838F);
  final _notesCtrl = TextEditingController();
  bool _loadingVehicles = true;
  bool _saving = false;
  String? _error;
  List<Vehicle> _vehicles = [];
  Vehicle? _selectedVehicle;

  // Item rows
  final List<_ItemRow> _items = [];

  @override
  void initState() {
    super.initState();
    _loadVehicles();
    _addItem();
  }

  Future<void> _loadVehicles() async {
    try {
      final v = await ApiService.instance.getVehicles();
      if (mounted) setState(() { _vehicles = v; _loadingVehicles = false; });
    } catch (_) {
      if (mounted) setState(() => _loadingVehicles = false);
    }
  }

  void _addItem() => setState(() => _items.add(_ItemRow()));

  void _removeItem(int i) => setState(() => _items.removeAt(i));

  double get _totalAmount => _items.fold(0, (sum, item) => sum + (double.tryParse(item.amountCtrl.text) ?? 0));

  Future<void> _pickFile(int index) async {
    final choice = await _showPickerDialog();
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
    setState(() { _items[index].filePath = path; });
  }

  Future<String?> _showPickerDialog() => showModalBottomSheet<String>(
    context: context,
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
    builder: (_) => Column(mainAxisSize: MainAxisSize.min, children: [
      const SizedBox(height: 12),
      Container(width: 40, height: 4, decoration: BoxDecoration(color: Colors.grey.shade300, borderRadius: BorderRadius.circular(2))),
      const SizedBox(height: 12),
      const Text('Attach File', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
      const SizedBox(height: 8),
      ListTile(leading: const Icon(Icons.camera_alt, color: _teal), title: const Text('Camera'), onTap: () => Navigator.pop(context, 'camera')),
      ListTile(leading: const Icon(Icons.photo_library, color: _teal), title: const Text('Gallery'), onTap: () => Navigator.pop(context, 'gallery')),
      ListTile(leading: const Icon(Icons.attach_file, color: _teal), title: const Text('Browse File'), onTap: () => Navigator.pop(context, 'file')),
      const SizedBox(height: 16),
    ]),
  );

  Future<void> _save() async {
    if (_items.isEmpty) { _showSnack('Add at least one repair item', isError: true); return; }
    for (int i = 0; i < _items.length; i++) {
      if (_items[i].nameCtrl.text.trim().isEmpty) {
        _showSnack('Item ${i + 1} name is required', isError: true); return;
      }
    }
    setState(() { _saving = true; _error = null; });
    try {
      final fields = <String, String>{
        'notes': _notesCtrl.text.trim(),
        if (_selectedVehicle != null) 'vehicle_id': _selectedVehicle!.id.toString(),
      };
      final files = <String, String>{};
      for (int i = 0; i < _items.length; i++) {
        fields['item_name_$i'] = _items[i].nameCtrl.text.trim();
        fields['item_description_$i'] = _items[i].descCtrl.text.trim();
        fields['item_amount_$i'] = _items[i].amountCtrl.text.trim().isEmpty ? '0' : _items[i].amountCtrl.text.trim();
        if (_items[i].filePath != null) files['item_attachment_$i'] = _items[i].filePath!;
      }
      await ApiService.instance.createRepair(fields, files);
      if (!mounted) return;
      Navigator.of(context).pop(true);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Repair created!'), backgroundColor: Color(0xFF4CAF50)),
      );
    } on ApiException catch (e) {
      setState(() { _error = e.message; _saving = false; });
    } catch (_) {
      setState(() { _error = 'Failed to create repair'; _saving = false; });
    }
  }

  void _showSnack(String msg, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: isError ? Colors.red : _teal),
    );
  }

  @override
  void dispose() {
    _notesCtrl.dispose();
    for (final item in _items) item.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4F8),
      appBar: AppBar(title: const Text('New Repair'), backgroundColor: _teal, foregroundColor: Colors.white),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          if (_error != null) _errorBanner(),
          // Vehicle & notes
          Card(
            margin: const EdgeInsets.only(bottom: 12),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('General', style: TextStyle(fontWeight: FontWeight.bold, color: _teal, fontSize: 15)),
                const SizedBox(height: 14),
                _loadingVehicles
                    ? const LinearProgressIndicator()
                    : DropdownButtonFormField<Vehicle>(
                        value: _selectedVehicle,
                        decoration: const InputDecoration(labelText: 'Vehicle (optional)'),
                        isExpanded: true,
                        items: [
                          const DropdownMenuItem<Vehicle>(value: null, child: Text('-- None --')),
                          ..._vehicles.map((v) => DropdownMenuItem<Vehicle>(value: v, child: Text('${v.name} (${v.registrationNumber})'))),
                        ],
                        onChanged: (v) => setState(() => _selectedVehicle = v),
                      ),
                const SizedBox(height: 12),
                TextField(
                  controller: _notesCtrl,
                  maxLines: 2,
                  decoration: const InputDecoration(labelText: 'Notes (optional)'),
                ),
              ]),
            ),
          ),
          // Total display
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(gradient: const LinearGradient(colors: [Color(0xFF00838F), Color(0xFF006064)]), borderRadius: BorderRadius.circular(14)),
            child: Row(children: [
              const Text('Total Amount', style: TextStyle(color: Colors.white70, fontSize: 14)),
              const Spacer(),
              Text('₹${_totalAmount.toStringAsFixed(2)}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 20)),
            ]),
          ),
          // Items
          Card(
            margin: const EdgeInsets.only(bottom: 12),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  const Text('Repair Items', style: TextStyle(fontWeight: FontWeight.bold, color: _teal, fontSize: 15)),
                  const Spacer(),
                  TextButton.icon(icon: const Icon(Icons.add), label: const Text('Add Item'), onPressed: _addItem),
                ]),
                const Divider(height: 12),
                ..._items.asMap().entries.map((e) => _itemCard(e.key, e.value)),
              ]),
            ),
          ),
          const SizedBox(height: 80),
        ]),
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: _saving ? Colors.grey : _teal,
        foregroundColor: Colors.white,
        onPressed: _saving ? null : _save,
        icon: _saving
            ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
            : const Icon(Icons.save),
        label: const Text('Create Repair'),
      ),
    );
  }

  Widget _itemCard(int i, _ItemRow item) => Container(
    margin: const EdgeInsets.only(bottom: 12),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(color: Colors.grey.shade50, borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.grey.shade200)),
    child: Column(children: [
      Row(children: [
        Text('Item ${i + 1}', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.grey.shade700)),
        const Spacer(),
        if (_items.length > 1)
          IconButton(icon: const Icon(Icons.remove_circle_outline, color: Colors.red, size: 20), onPressed: () => _removeItem(i)),
      ]),
      TextField(
        controller: item.nameCtrl,
        decoration: const InputDecoration(labelText: 'Item Name *', isDense: true),
        textCapitalization: TextCapitalization.words,
      ),
      const SizedBox(height: 8),
      TextField(
        controller: item.descCtrl,
        decoration: const InputDecoration(labelText: 'Description', isDense: true),
      ),
      const SizedBox(height: 8),
      TextField(
        controller: item.amountCtrl,
        keyboardType: TextInputType.number,
        decoration: const InputDecoration(labelText: 'Amount', isDense: true, prefixText: '₹ '),
        onTap: () => item.amountCtrl.selection = TextSelection(
            baseOffset: 0, extentOffset: item.amountCtrl.text.length),
        onChanged: (_) => setState(() {}),
      ),
      const SizedBox(height: 8),
      GestureDetector(
        onTap: () => _pickFile(i),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(color: _teal.withOpacity(0.06), borderRadius: BorderRadius.circular(8), border: Border.all(color: _teal.withOpacity(0.2))),
          child: Row(children: [
            const Icon(Icons.attach_file, size: 15, color: _teal),
            const SizedBox(width: 6),
            Expanded(child: Text(item.filePath?.split('/').last ?? 'Attach photo/bill (optional)',
                style: TextStyle(fontSize: 12, color: item.filePath != null ? _teal : Colors.grey.shade500), overflow: TextOverflow.ellipsis)),
            if (item.filePath != null) const Icon(Icons.check_circle, size: 14, color: Color(0xFF4CAF50)),
          ]),
        ),
      ),
    ]),
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

class _ItemRow {
  final nameCtrl = TextEditingController();
  final descCtrl = TextEditingController();
  final amountCtrl = TextEditingController(text: '0');
  String? filePath;

  void dispose() {
    nameCtrl.dispose();
    descCtrl.dispose();
    amountCtrl.dispose();
  }
}
