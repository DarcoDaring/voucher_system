// lib/screens/voucher_detail_screen.dart

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import 'voucher_list_screen.dart' show StatusBadge;

class VoucherDetailScreen extends StatefulWidget {
  final int voucherId;
  const VoucherDetailScreen({super.key, required this.voucherId});

  @override
  State<VoucherDetailScreen> createState() => _VoucherDetailScreenState();
}

class _VoucherDetailScreenState extends State<VoucherDetailScreen> {
  VoucherDetail? _voucher;
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
      final v = await ApiService.instance.getVoucherDetail(widget.voucherId);
      if (mounted) setState(() { _voucher = v; _loading = false; });
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _loading = false; });
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Could not load voucher. Check your connection.';
          _loading = false;
        });
      }
    }
  }

  // ── Approval actions ─────────────────────────────────────────

  Future<void> _handleApprove() async {
    final confirm = await _confirmDialog(
      title: 'Approve Voucher',
      message: 'Are you sure you want to approve ${_voucher!.voucherNumber}?',
      confirmLabel: 'Approve',
      confirmColor: Colors.green,
    );
    if (confirm != true) return;
    await _submitAction('APPROVED');
  }

  Future<void> _handleReject() async {
    final reason = await _rejectReasonDialog();
    if (reason == null) return; // cancelled
    await _submitAction('REJECTED', rejectionReason: reason);
  }

  Future<void> _submitAction(String action, {String rejectionReason = ''}) async {
    setState(() => _actionLoading = true);
    try {
      await ApiService.instance.approveVoucher(
        widget.voucherId,
        action: action,
        rejectionReason: rejectionReason,
      );
      await _load(); // refresh detail
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Voucher ${action.toLowerCase()} successfully!',
            ),
            backgroundColor:
                action == 'APPROVED' ? Colors.green : Colors.red,
          ),
        );
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _actionLoading = false);
    }
  }

  // ── Dialogs ───────────────────────────────────────────────────

  Future<bool?> _confirmDialog({
    required String title,
    required String message,
    required String confirmLabel,
    required Color confirmColor,
  }) =>
      showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
          title: Text(title),
          content: Text(message),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: confirmColor),
              onPressed: () => Navigator.pop(context, true),
              child: Text(confirmLabel),
            ),
          ],
        ),
      );

  Future<String?> _rejectReasonDialog() async {
    final ctrl = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Reject Voucher'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Please provide a rejection reason:'),
            const SizedBox(height: 12),
            TextField(
              controller: ctrl,
              maxLines: 3,
              decoration: const InputDecoration(
                hintText: 'Enter reason...',
                border: OutlineInputBorder(),
              ),
              autofocus: true,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, null),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () {
              if (ctrl.text.trim().isEmpty) return;
              Navigator.pop(context, ctrl.text.trim());
            },
            child: const Text('Reject'),
          ),
        ],
      ),
    );
    ctrl.dispose();
    return result;
  }

  // ── Attachment opener ─────────────────────────────────────────

  Future<void> _openAttachment(Attachment att) async {
    if (att.url == null) return;
    final uri = Uri.parse(att.url!);
    try {
      final launched = await launchUrl(
        uri,
        mode: LaunchMode.inAppBrowserView, // works reliably on both Android & iOS
      );
      if (!launched && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open attachment')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error opening attachment: $e')),
        );
      }
    }
  }

  // ── Build ─────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_voucher?.voucherNumber ?? 'Voucher Detail'),
        actions: [
          if (!_loading)
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _load,
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.error_outline,
                          size: 56, color: Colors.red.shade300),
                      const SizedBox(height: 12),
                      Text(_error!),
                      const SizedBox(height: 16),
                      ElevatedButton.icon(
                        onPressed: _load,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : _buildContent(),
    );
  }

  Widget _buildContent() {
    final v = _voucher!;

    // Show actions only when still pending AND user hasn't acted yet
    final showActions = v.canApprove &&
        v.status == 'PENDING' &&
        v.userApprovalStatus == null;

    return Stack(
      children: [
        SingleChildScrollView(
          padding: EdgeInsets.fromLTRB(
            16, 16, 16,
            showActions ? 100 : 16,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Header card ──────────────────────────────────
              _sectionCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            v.voucherNumber,
                            style: const TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        StatusBadge(status: v.status),
                      ],
                    ),
                    const SizedBox(height: 12),
                    _row('Pay To', v.payToDisplay),
                    _row('Date', v.voucherDate),
                    _row('Payment', v.paymentType),
                    _row('Amount', '₹ ${v.totalAmount}',
                        valueStyle: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF667EEA),
                        )),
                    _row('Created By', v.createdBy),
                    _row('Created At', v.createdAt),
                    if (v.paymentType == 'CHEQUE') ...[
                      const Divider(height: 20),
                      if (v.chequeNumber != null)
                        _row('Cheque No', v.chequeNumber!),
                      if (v.chequeDate != null)
                        _row('Cheque Date', v.chequeDate!),
                      if (v.accountDetails != null)
                        _row('Account', v.accountDetails!),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 14),

              // ── Particulars ──────────────────────────────────
              _sectionTitle('Particulars'),
              ...v.particulars.map((p) => _particularTile(p)),
              const SizedBox(height: 14),

              // ── Main attachments ─────────────────────────────
              if (v.mainAttachments.isNotEmpty) ...[
                _sectionTitle('Main Attachments'),
                _sectionCard(
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: v.mainAttachments
                        .map((a) => _attachmentChip(a))
                        .toList(),
                  ),
                ),
                const SizedBox(height: 14),
              ],

              // ── Cheque attachments ───────────────────────────
              if (v.chequeAttachments.isNotEmpty) ...[
                _sectionTitle('Cheque Attachments'),
                _sectionCard(
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: v.chequeAttachments
                        .map((a) => _attachmentChip(a))
                        .toList(),
                  ),
                ),
                const SizedBox(height: 14),
              ],

              // ── Approval status ──────────────────────────────
              _sectionTitle('Approval Status'),
              _approvalSection(v),
              const SizedBox(height: 16),
            ],
          ),
        ),

        // ── Floating action buttons (bottom) ─────────────────
        if (showActions)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: _actionBar(v),
          ),

        // Loading overlay during action
        if (_actionLoading)
          Container(
            color: Colors.black26,
            child: const Center(child: CircularProgressIndicator()),
          ),
      ],
    );
  }

  // ── Sections ──────────────────────────────────────────────────

  Widget _sectionCard({required Widget child}) => Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: child,
        ),
      );

  Widget _sectionTitle(String title) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(
          title,
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            fontSize: 14,
            color: Colors.black54,
            letterSpacing: 0.5,
          ),
        ),
      );

  Widget _row(String label, String value, {TextStyle? valueStyle}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 100,
              child: Text(
                label,
                style: const TextStyle(color: Colors.grey, fontSize: 13),
              ),
            ),
            Expanded(
              child: Text(
                value,
                style: valueStyle ??
                    const TextStyle(
                      fontWeight: FontWeight.w500,
                      fontSize: 13,
                    ),
              ),
            ),
          ],
        ),
      );

  Widget _particularTile(Particular p) => Card(
        margin: const EdgeInsets.only(bottom: 8),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      p.description,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                      ),
                    ),
                  ),
                  Text(
                    '₹ ${p.amount}',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF667EEA),
                    ),
                  ),
                ],
              ),
              if (p.attachments.isNotEmpty) ...[
                const SizedBox(height: 8),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: p.attachments
                      .map((a) => _attachmentChip(a, small: true))
                      .toList(),
                ),
              ],
            ],
          ),
        ),
      );

  Widget _attachmentChip(Attachment att, {bool small = false}) => ActionChip(
        avatar: Icon(
          att.isPdf
              ? Icons.picture_as_pdf_outlined
              : att.isImage
                  ? Icons.image_outlined
                  : Icons.attach_file_outlined,
          size: 16,
          color: att.isPdf ? Colors.red : const Color(0xFF667EEA),
        ),
        label: Text(
          att.filename.length > 20
              ? '${att.filename.substring(0, 18)}…'
              : att.filename,
          style: TextStyle(fontSize: small ? 11 : 12),
        ),
        onPressed: () => _openAttachment(att),
        backgroundColor: Colors.grey.shade100,
        side: BorderSide(color: Colors.grey.shade300),
      );

  Widget _approvalSection(VoucherDetail v) {
    return _sectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Required approvers progress
          Row(
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: v.requiredApprovers.isEmpty
                        ? 1.0
                        : v.approvals
                                .where((a) => a.status == 'APPROVED')
                                .length /
                            v.requiredApprovers.length,
                    minHeight: 6,
                    backgroundColor: Colors.grey.shade200,
                    color: const Color(0xFF667EEA),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                '${v.approvals.where((a) => a.status == 'APPROVED').length}/${v.requiredApprovers.length}',
                style: const TextStyle(fontSize: 12, color: Colors.grey),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Waiting for info
          if (v.status == 'PENDING' && v.waitingFor != null)
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.orange.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.orange.shade200),
              ),
              child: Row(
                children: [
                  Icon(Icons.hourglass_empty,
                      size: 16, color: Colors.orange.shade700),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Waiting for ${v.waitingFor} to approve first',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.orange.shade800,
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // User's own approval status
          if (v.userApprovalStatus != null) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: v.userApprovalStatus == 'APPROVED'
                    ? Colors.green.shade50
                    : Colors.red.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: v.userApprovalStatus == 'APPROVED'
                      ? Colors.green.shade200
                      : Colors.red.shade200,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    v.userApprovalStatus == 'APPROVED'
                        ? Icons.check_circle_outline
                        : Icons.cancel_outlined,
                    size: 16,
                    color: v.userApprovalStatus == 'APPROVED'
                        ? Colors.green.shade700
                        : Colors.red.shade700,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'You have ${v.userApprovalStatus!.toLowerCase()} this voucher',
                    style: TextStyle(
                      fontSize: 12,
                      color: v.userApprovalStatus == 'APPROVED'
                          ? Colors.green.shade800
                          : Colors.red.shade800,
                    ),
                  ),
                ],
              ),
            ),
          ],

          // Individual approval records
          if (v.approvals.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Divider(),
            const SizedBox(height: 8),
            ...v.approvals.map((a) => _approvalRow(a)),
          ],
        ],
      ),
    );
  }

  Widget _approvalRow(ApprovalRecord a) {
    final isApproved = a.status == 'APPROVED';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            isApproved ? Icons.check_circle : Icons.cancel,
            color: isApproved ? Colors.green : Colors.red,
            size: 18,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      a.approver,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(
                        color:
                            isApproved ? Colors.green.shade50 : Colors.red.shade50,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        a.status,
                        style: TextStyle(
                          fontSize: 10,
                          color: isApproved
                              ? Colors.green.shade700
                              : Colors.red.shade700,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
                if (a.approvedAt != null)
                  Text(
                    a.approvedAt!,
                    style:
                        const TextStyle(fontSize: 11, color: Colors.grey),
                  ),
                if (a.rejectionReason != null &&
                    a.rejectionReason!.isNotEmpty) ...[
                  const SizedBox(height: 3),
                  Text(
                    'Reason: ${a.rejectionReason}',
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.red.shade600,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _actionBar(VoucherDetail v) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 10,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            // Reject
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _actionLoading ? null : _handleReject,
                icon: const Icon(Icons.close, size: 18),
                label: const Text('Reject'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.red,
                  side: const BorderSide(color: Colors.red),
                  padding: const EdgeInsets.symmetric(vertical: 13),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            // Approve
            Expanded(
              flex: 2,
              child: ElevatedButton.icon(
                onPressed: _actionLoading ? null : _handleApprove,
                icon: const Icon(Icons.check, size: 18),
                label: const Text('Approve'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green,
                  padding: const EdgeInsets.symmetric(vertical: 13),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}