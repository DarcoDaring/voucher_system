import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../models/models.dart';
import '../../services/api_service.dart';

class BankListScreen extends StatefulWidget {
  final bool embedded;
  const BankListScreen({super.key, this.embedded = false});
  @override
  State<BankListScreen> createState() => _BankListScreenState();
}

class _BankListScreenState extends State<BankListScreen> {
  static const _teal = Color(0xFF00838F);
  List<BankEntry> _entries = [];
  bool _loading = true;
  String? _error;
  final Set<int> _actionLoading = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await ApiService.instance.getBankList();
      if (mounted) setState(() { _entries = data; _loading = false; });
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _loading = false; });
    }
  }

  Future<void> _upload(BankEntry entry) async {
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
    if (path == null || !mounted) return;

    setState(() => _actionLoading.add(entry.settlementId));
    try {
      await ApiService.instance.uploadBankDocument(entry.settlementId, path);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Document uploaded!'), backgroundColor: Color(0xFF4CAF50)),
      );
      _load();
    } on ApiException catch (e) {
      if (mounted) _showSnack(e.message, isError: true);
    } finally {
      if (mounted) setState(() => _actionLoading.remove(entry.settlementId));
    }
  }

  Future<void> _approve(BankEntry entry) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Approve Settlement'),
        content: Text('Approve bank settlement for ${entry.bookingNumber}?\nNet balance: ₹${entry.netBalance}'),
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
    if (confirmed != true || !mounted) return;

    final bankId = entry.bank?.id;
    if (bankId == null) return;

    setState(() => _actionLoading.add(entry.settlementId));
    try {
      await ApiService.instance.approveBank(bankId);
      if (!mounted) return;
      _showSnack('Settlement approved!');
      _load();
    } on ApiException catch (e) {
      if (mounted) _showSnack(e.message, isError: true);
    } finally {
      if (mounted) setState(() => _actionLoading.remove(entry.settlementId));
    }
  }

  Future<String?> _showPickerDialog() => showModalBottomSheet<String>(
    context: context,
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
    builder: (_) => Column(mainAxisSize: MainAxisSize.min, children: [
      const SizedBox(height: 12),
      Container(width: 40, height: 4, decoration: BoxDecoration(color: Colors.grey.shade300, borderRadius: BorderRadius.circular(2))),
      const SizedBox(height: 12),
      const Text('Upload Bank Document', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
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
    final body = RefreshIndicator(
      onRefresh: _load,
      color: _teal,
      child: _loading
          ? const Center(child: CircularProgressIndicator(color: _teal))
          : _error != null
              ? ListView(children: [const SizedBox(height: 100), Center(child: Column(children: [
                  Icon(Icons.error_outline, size: 48, color: Colors.red.shade300),
                  const SizedBox(height: 12), Text(_error!),
                  const SizedBox(height: 16), ElevatedButton(onPressed: _load, child: const Text('Retry')),
                ]))])
              : _entries.isEmpty
                  ? ListView(children: [const SizedBox(height: 100), Center(child: Column(children: [
                      Icon(Icons.account_balance_outlined, size: 64, color: Colors.grey.shade300),
                      const SizedBox(height: 16),
                      const Text('No bank entries yet', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                      Text('Settled trips appear here for bank approval', style: TextStyle(color: Colors.grey.shade500, fontSize: 13)),
                    ]))])
                  : ListView.separated(
                      padding: const EdgeInsets.all(16),
                      itemCount: _entries.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (_, i) => _BankCard(
                        entry: _entries[i],
                        isLoading: _actionLoading.contains(_entries[i].settlementId),
                        canApprove: perms?.isApprover ?? false,
                        onUpload: () => _upload(_entries[i]),
                        onApprove: () => _approve(_entries[i]),
                      ),
                    ),
    );

    if (widget.embedded) return body;
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4F8),
      appBar: AppBar(title: const Text('Bank'), backgroundColor: _teal, foregroundColor: Colors.white,
          actions: [IconButton(icon: const Icon(Icons.refresh), onPressed: _load)]),
      body: body,
    );
  }
}

class _BankCard extends StatelessWidget {
  final BankEntry entry;
  final bool isLoading;
  final bool canApprove;
  final VoidCallback onUpload;
  final VoidCallback onApprove;
  const _BankCard({required this.entry, required this.isLoading, required this.canApprove, required this.onUpload, required this.onApprove});

  @override
  Widget build(BuildContext context) {
    final bank = entry.bank;
    final isApproved = bank?.status == 'APPROVED';
    final isPending = bank?.status == 'PENDING_APPROVAL';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Expanded(child: Text(entry.bookingNumber, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15))),
              _statusChip(isApproved, isPending, bank == null),
            ]),
            const SizedBox(height: 8),
            Row(children: [
              const Icon(Icons.person_outline, size: 15, color: Colors.grey),
              const SizedBox(width: 6),
              Text(entry.bookedBy, style: const TextStyle(fontSize: 13)),
            ]),
            const SizedBox(height: 4),
            if (entry.vehicle != '—') Row(children: [
              const Icon(Icons.directions_car_outlined, size: 15, color: Colors.grey),
              const SizedBox(width: 6),
              Text(entry.vehicle, style: const TextStyle(fontSize: 13)),
            ]),
            const Divider(height: 16),
            Row(children: [
              const Text('Net Balance', style: TextStyle(color: Colors.grey, fontSize: 13)),
              const Spacer(),
              Text('₹${entry.netBalance}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Color(0xFF00838F))),
            ]),
            if (isApproved && bank != null) ...[
              const SizedBox(height: 6),
              Row(children: [
                const Icon(Icons.check_circle, size: 14, color: Color(0xFF4CAF50)),
                const SizedBox(width: 4),
                Text('Approved by ${bank.approvedBy ?? "—"} · ${bank.approvedAt ?? ""}',
                    style: const TextStyle(color: Color(0xFF4CAF50), fontSize: 11)),
              ]),
            ],
            if (bank?.documentUrl != null) ...[
              const SizedBox(height: 8),
              GestureDetector(
                onTap: () => launchUrl(Uri.parse(bank!.documentUrl!)),
                child: Row(children: [
                  const Icon(Icons.attach_file, size: 14, color: Color(0xFF00838F)),
                  const SizedBox(width: 4),
                  Text(bank!.documentName ?? 'View Document', style: const TextStyle(color: Color(0xFF00838F), fontSize: 12, decoration: TextDecoration.underline)),
                ]),
              ),
            ],
            if (!isApproved) ...[
              const SizedBox(height: 12),
              if (isLoading)
                const Center(child: SizedBox(height: 24, width: 24, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF00838F))))
              else Row(children: [
                Expanded(child: OutlinedButton.icon(
                  icon: const Icon(Icons.upload_file, size: 16),
                  label: Text(bank == null ? 'Upload Doc' : 'Replace Doc', style: const TextStyle(fontSize: 13)),
                  style: OutlinedButton.styleFrom(foregroundColor: const Color(0xFF00838F), side: const BorderSide(color: Color(0xFF00838F))),
                  onPressed: onUpload,
                )),
                if (isPending && canApprove) ...[
                  const SizedBox(width: 8),
                  Expanded(child: ElevatedButton.icon(
                    icon: const Icon(Icons.check, size: 16),
                    label: const Text('Approve', style: TextStyle(fontSize: 13)),
                    style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF4CAF50)),
                    onPressed: onApprove,
                  )),
                ],
              ]),
            ],
          ],
        ),
      ),
    );
  }

  Widget _statusChip(bool approved, bool pending, bool noDoc) {
    Color color; String label; IconData icon;
    if (approved) { color = const Color(0xFF4CAF50); label = 'Approved'; icon = Icons.check_circle; }
    else if (pending) { color = const Color(0xFFFF9800); label = 'Pending Approval'; icon = Icons.hourglass_empty; }
    else { color = Colors.grey; label = 'No Document'; icon = Icons.upload_file; }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(20)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 12, color: color),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600)),
      ]),
    );
  }
}
