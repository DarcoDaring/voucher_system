import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../models/models.dart';
import '../../services/api_service.dart';
import 'repair_create_screen.dart';

class RepairDetailScreen extends StatefulWidget {
  final int repairId;
  const RepairDetailScreen({super.key, required this.repairId});
  @override
  State<RepairDetailScreen> createState() => _RepairDetailScreenState();
}

class _RepairDetailScreenState extends State<RepairDetailScreen> {
  static const _teal = Color(0xFF00838F);
  RepairRecord? _repair;
  bool _loading = true;
  bool _actionLoading = false;
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
      final r = await ApiService.instance.getRepairDetail(widget.repairId);
      if (mounted) setState(() { _repair = r; _loading = false; });
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _loading = false; });
    }
  }

  Future<void> _submitToBank() async {
    final choice = await _showPickerDialog(title: 'Attach Bank Document (required)');
    if (choice == null) return;
    String? path;
    if (choice == 'camera') {
      final picked = await ImagePicker().pickImage(source: ImageSource.camera, imageQuality: 80);
      path = picked?.path;
    } else if (choice == 'gallery') {
      final picked = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 80);
      path = picked?.path;
    } else if (choice == 'file') {
      final result = await FilePicker.platform.pickFiles(type: FileType.any);
      path = result?.files.single.path;
    }

    // Bank document is mandatory — block submission without it
    if (path == null) {
      _showSnack('A bank document is required to submit for approval.', isError: true);
      return;
    }

    setState(() => _actionLoading = true);
    try {
      await ApiService.instance.submitRepairToBank(widget.repairId, path);
      if (!mounted) return;
      _showSnack('Submitted to bank!');
      _load();
    } on ApiException catch (e) {
      if (mounted) _showSnack(e.message, isError: true);
    } finally {
      if (mounted) setState(() => _actionLoading = false);
    }
  }

  Future<void> _approve() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Approve Repair'),
        content: Text('Approve repair ${_repair!.repairNumber}?\nTotal: ₹${_repair!.totalAmount}'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF4CAF50)),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Approve'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _actionLoading = true);
    try {
      await ApiService.instance.approveRepair(widget.repairId);
      if (!mounted) return;
      _showSnack('Repair approved!');
      _load();
    } on ApiException catch (e) {
      if (mounted) _showSnack(e.message, isError: true);
    } finally {
      if (mounted) setState(() => _actionLoading = false);
    }
  }

  Future<void> _delete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Delete Repair'),
        content: const Text('This cannot be undone. Continue?'),
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
      await ApiService.instance.deleteRepair(widget.repairId);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (mounted) _showSnack(e.message, isError: true);
      setState(() => _actionLoading = false);
    }
  }

  Future<String?> _showPickerDialog({required String title}) => showModalBottomSheet<String>(
    context: context,
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
    builder: (_) => Column(mainAxisSize: MainAxisSize.min, children: [
      const SizedBox(height: 12),
      Container(width: 40, height: 4, decoration: BoxDecoration(color: Colors.grey.shade300, borderRadius: BorderRadius.circular(2))),
      const SizedBox(height: 12),
      Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
      const SizedBox(height: 8),
      ListTile(leading: const Icon(Icons.camera_alt, color: _teal), title: const Text('Camera'), onTap: () => Navigator.pop(context, 'camera')),
      ListTile(leading: const Icon(Icons.photo_library, color: _teal), title: const Text('Gallery'), onTap: () => Navigator.pop(context, 'gallery')),
      ListTile(leading: const Icon(Icons.attach_file, color: _teal), title: const Text('Browse File'), onTap: () => Navigator.pop(context, 'file')),
      const SizedBox(height: 16),
    ]),
  );

  void _showSnack(String msg, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: isError ? Colors.red : _teal),
    );
  }

  @override
  Widget build(BuildContext context) {
    final perms = ApiService.instance.permissions;
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4F8),
      appBar: AppBar(
        title: Text(_repair?.repairNumber ?? 'Repair Detail'),
        backgroundColor: _teal,
        foregroundColor: Colors.white,
        actions: [
          if (_repair != null && _repair!.status != 'APPROVED' && perms?.canEdit == true)
            IconButton(
              icon: const Icon(Icons.edit_outlined),
              onPressed: _actionLoading
                  ? null
                  : () async {
                      final changed = await Navigator.of(context).push<bool>(
                        MaterialPageRoute(builder: (_) => RepairCreateScreen(existing: _repair)),
                      );
                      if (changed == true) _load();
                    },
            ),
          if (_repair != null && _repair!.status != 'APPROVED' && perms?.canDelete == true)
            IconButton(icon: const Icon(Icons.delete_outline), onPressed: _actionLoading ? null : _delete),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: _teal))
          : _error != null
              ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Icon(Icons.error_outline, size: 56, color: Colors.red.shade300),
                  const SizedBox(height: 16), Text(_error!),
                  const SizedBox(height: 20), ElevatedButton(onPressed: _load, child: const Text('Retry')),
                ]))
              : _buildBody(),
    );
  }

  Widget _buildBody() {
    final r = _repair!;
    final perms = ApiService.instance.permissions;
    final isApproved = r.status == 'APPROVED';
    final isSubmitted = r.status == 'SUBMITTED';
    final bankApproved = r.bankStatus == 'APPROVED';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(children: [
        // Status banner
        _statusBanner(r),
        const SizedBox(height: 16),
        // General info
        _infoCard('Repair Details', [
          _row('Repair No.', r.repairNumber),
          _row('Vehicle', r.vehicle ?? 'Not specified'),
          _row('Total Amount', '₹${r.totalAmount}', highlight: true),
          _row('Created', r.createdAt),
          if (r.notes.isNotEmpty) _row('Notes', r.notes),
        ]),
        // Bank info
        if (r.bankStatus != null) _infoCard('Bank Status', [
          _row('Status', r.bankStatus == 'APPROVED' ? 'Approved' : 'Pending Approval'),
          if (r.approvedBy != null) _row('Approved By', r.approvedBy!),
          if (r.approvedAt != null) _row('Approved At', r.approvedAt!),
          if (r.bankDocUrl != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: GestureDetector(
                onTap: () => launchUrl(Uri.parse(r.bankDocUrl!)),
                child: Row(children: [
                  const Icon(Icons.attach_file, size: 15, color: _teal),
                  const SizedBox(width: 6),
                  const Text('View Bank Document', style: TextStyle(color: _teal, decoration: TextDecoration.underline, fontSize: 13)),
                ]),
              ),
            ),
        ]),
        // Items
        Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Items (${r.items.length})', style: const TextStyle(fontWeight: FontWeight.bold, color: _teal, fontSize: 14)),
              const Divider(height: 16),
              ...r.items.map((item) => _itemTile(item)),
            ]),
          ),
        ),
        // Actions
        if (_actionLoading)
          const Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator(color: _teal))
        else if (!isApproved) ...[
          if (!isSubmitted && perms?.canEdit == true)
            SizedBox(width: double.infinity, child: ElevatedButton.icon(
              icon: const Icon(Icons.account_balance),
              label: const Text('Submit to Bank'),
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFFF9800)),
              onPressed: _submitToBank,
            )),
          const SizedBox(height: 8),
          if (isSubmitted && r.bankStatus == 'PENDING_APPROVAL' && perms?.isApprover == true && !bankApproved)
            SizedBox(width: double.infinity, child: ElevatedButton.icon(
              icon: const Icon(Icons.check_circle),
              label: const Text('Approve Bank Settlement'),
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF4CAF50)),
              onPressed: _approve,
            )),
        ],
        const SizedBox(height: 32),
      ]),
    );
  }

  Widget _statusBanner(RepairRecord r) {
    final statusColor = _statusColor(r.status);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: statusColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: statusColor.withOpacity(0.3)),
      ),
      child: Row(children: [
        Icon(_statusIcon(r.status), color: statusColor, size: 32),
        const SizedBox(width: 12),
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(r.statusLabel, style: TextStyle(color: statusColor, fontWeight: FontWeight.bold, fontSize: 16)),
          Text('${r.items.length} items · ₹${r.totalAmount}', style: TextStyle(color: statusColor.withValues(alpha: 0.7), fontSize: 13)),
        ]),
      ]),
    );
  }

  Widget _itemTile(RepairItem item) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: Colors.grey.shade50, borderRadius: BorderRadius.circular(10), border: Border.all(color: Colors.grey.shade200)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(item.name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14))),
          Text('₹${item.amount}', style: const TextStyle(fontWeight: FontWeight.bold, color: _teal, fontSize: 14)),
        ]),
        if (item.description.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(item.description, style: TextStyle(color: Colors.grey.shade600, fontSize: 12)),
        ],
        if (item.attachmentUrl != null) ...[
          const SizedBox(height: 6),
          GestureDetector(
            onTap: () => launchUrl(Uri.parse(item.attachmentUrl!)),
            child: Row(children: [
              const Icon(Icons.attach_file, size: 14, color: _teal),
              const SizedBox(width: 4),
              Expanded(child: Text(
                item.attachmentName ?? 'View attachment',
                style: const TextStyle(color: _teal, fontSize: 12, decoration: TextDecoration.underline),
                overflow: TextOverflow.ellipsis,
              )),
            ]),
          ),
        ],
      ]),
    ),
  );

  Widget _infoCard(String title, List<Widget> rows) => Card(
    margin: const EdgeInsets.only(bottom: 12),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold, color: _teal, fontSize: 14)),
        const Divider(height: 16),
        ...rows,
      ]),
    ),
  );

  Widget _row(String label, String value, {bool highlight = false}) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SizedBox(width: 110, child: Text(label, style: TextStyle(color: Colors.grey.shade600, fontSize: 13))),
      Expanded(child: Text(value, style: TextStyle(
        fontSize: 13,
        fontWeight: highlight ? FontWeight.bold : FontWeight.normal,
        color: highlight ? _teal : const Color(0xFF1A2E3B),
      ))),
    ]),
  );

  Color _statusColor(String s) {
    switch (s) {
      case 'DRAFT': return const Color(0xFF2196F3);
      case 'SUBMITTED': return const Color(0xFFFF9800);
      case 'APPROVED': return const Color(0xFF4CAF50);
      default: return Colors.grey;
    }
  }

  IconData _statusIcon(String s) {
    switch (s) {
      case 'DRAFT': return Icons.edit_note;
      case 'SUBMITTED': return Icons.pending_actions;
      case 'APPROVED': return Icons.verified;
      default: return Icons.build;
    }
  }
}
