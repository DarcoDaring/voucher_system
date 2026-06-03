// lib/models/models.dart

class Company {
  final int id;
  final String name;
  final String? logoUrl;
  final String role;
  final String? designation;

  Company({
    required this.id,
    required this.name,
    this.logoUrl,
    required this.role,
    this.designation,
  });

  factory Company.fromJson(Map<String, dynamic> j) => Company(
        id: j['id'],
        name: j['name'],
        logoUrl: j['logo_url'],
        role: j['role'],
        designation: j['designation'],
      );
}

class AuthUser {
  final String token;
  final String username;
  final String fullName;
  final bool isSuperuser;
  final List<Company> companies;

  AuthUser({
    required this.token,
    required this.username,
    required this.fullName,
    required this.isSuperuser,
    required this.companies,
  });

  factory AuthUser.fromJson(Map<String, dynamic> j) => AuthUser(
        token: j['token'],
        username: j['username'],
        fullName: j['full_name'] ?? j['username'],
        isSuperuser: j['is_superuser'] ?? false,
        companies: (j['companies'] as List)
            .map((c) => Company.fromJson(c))
            .toList(),
      );
}

class VoucherSummary {
  final int id;
  final String voucherNumber;
  final String voucherDate;
  final String paymentType;
  final String payToDisplay;
  final String status;
  final String totalAmount;
  final String createdBy;
  final String createdAt;
  final bool canApprove;
  final String? waitingForUsername;
  final int approvedCount;
  final int requiredApproversCount;

  VoucherSummary({
    required this.id,
    required this.voucherNumber,
    required this.voucherDate,
    required this.paymentType,
    required this.payToDisplay,
    required this.status,
    required this.totalAmount,
    required this.createdBy,
    required this.createdAt,
    required this.canApprove,
    this.waitingForUsername,
    required this.approvedCount,
    required this.requiredApproversCount,
  });

  factory VoucherSummary.fromJson(Map<String, dynamic> j) => VoucherSummary(
        id: j['id'],
        voucherNumber: j['voucher_number'],
        voucherDate: j['voucher_date'],
        paymentType: j['payment_type'],
        payToDisplay: j['pay_to_display'],
        status: j['status'],
        totalAmount: j['total_amount'],
        createdBy: j['created_by'],
        createdAt: j['created_at'],
        canApprove: j['can_approve'] ?? false,
        waitingForUsername: j['waiting_for_username'],
        approvedCount: j['approved_count'] ?? 0,
        requiredApproversCount: j['required_approvers_count'] ?? 0,
      );
}

class Attachment {
  final int id;
  final String? url;
  final String filename;

  Attachment({required this.id, this.url, required this.filename});

  factory Attachment.fromJson(Map<String, dynamic> j) => Attachment(
        id: j['id'],
        url: j['url'],
        filename: j['filename'] ?? '',
      );

  bool get isPdf => filename.toLowerCase().endsWith('.pdf');
  bool get isImage =>
      filename.toLowerCase().endsWith('.jpg') ||
      filename.toLowerCase().endsWith('.jpeg') ||
      filename.toLowerCase().endsWith('.png');
}

class Particular {
  final int id;
  final String description;
  final String amount;
  final List<Attachment> attachments;

  Particular({
    required this.id,
    required this.description,
    required this.amount,
    required this.attachments,
  });

  factory Particular.fromJson(Map<String, dynamic> j) => Particular(
        id: j['id'],
        description: j['description'],
        amount: j['amount'],
        attachments: (j['attachments'] as List)
            .map((a) => Attachment.fromJson(a))
            .toList(),
      );
}

class ApprovalRecord {
  final String approver;
  final String status;
  final String? approvedAt;
  final String? rejectionReason;

  ApprovalRecord({
    required this.approver,
    required this.status,
    this.approvedAt,
    this.rejectionReason,
  });

  factory ApprovalRecord.fromJson(Map<String, dynamic> j) => ApprovalRecord(
        approver: j['approver'],
        status: j['status'],
        approvedAt: j['approved_at'],
        rejectionReason: j['rejection_reason'],
      );
}

class VoucherDetail {
  final int id;
  final String voucherNumber;
  final String voucherDate;
  final String paymentType;
  final String payToDisplay;
  final String? chequeNumber;
  final String? chequeDate;
  final String? accountDetails;
  final String status;
  final String totalAmount;
  final String createdBy;
  final String createdAt;
  final List<Particular> particulars;
  final List<Attachment> mainAttachments;
  final List<Attachment> chequeAttachments;
  final List<ApprovalRecord> approvals;
  final List<String> requiredApprovers;
  final bool canApprove;
  final String? waitingFor;
  final String? userApprovalStatus;

  VoucherDetail({
    required this.id,
    required this.voucherNumber,
    required this.voucherDate,
    required this.paymentType,
    required this.payToDisplay,
    this.chequeNumber,
    this.chequeDate,
    this.accountDetails,
    required this.status,
    required this.totalAmount,
    required this.createdBy,
    required this.createdAt,
    required this.particulars,
    required this.mainAttachments,
    required this.chequeAttachments,
    required this.approvals,
    required this.requiredApprovers,
    required this.canApprove,
    this.waitingFor,
    this.userApprovalStatus,
  });

  factory VoucherDetail.fromJson(Map<String, dynamic> j) => VoucherDetail(
        id: j['id'],
        voucherNumber: j['voucher_number'],
        voucherDate: j['voucher_date'],
        paymentType: j['payment_type'],
        payToDisplay: j['pay_to_display'],
        chequeNumber: j['cheque_number'],
        chequeDate: j['cheque_date'],
        accountDetails: j['account_details'],
        status: j['status'],
        totalAmount: j['total_amount'],
        createdBy: j['created_by'],
        createdAt: j['created_at'],
        particulars: (j['particulars'] as List)
            .map((p) => Particular.fromJson(p))
            .toList(),
        mainAttachments: (j['main_attachments'] as List)
            .map((a) => Attachment.fromJson(a))
            .toList(),
        chequeAttachments: (j['cheque_attachments'] as List)
            .map((a) => Attachment.fromJson(a))
            .toList(),
        approvals: (j['approvals'] as List)
            .map((a) => ApprovalRecord.fromJson(a))
            .toList(),
        requiredApprovers: List<String>.from(j['required_approvers'] ?? []),
        canApprove: j['can_approve'] ?? false,
        waitingFor: j['waiting_for'],
        userApprovalStatus: j['user_approval_status'],
      );
}