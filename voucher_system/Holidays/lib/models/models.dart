class Company {
  final int id;
  final String name;
  final String? logoUrl;
  final String role;
  final String? designation;
  final bool enableHolidays;

  const Company({
    required this.id,
    required this.name,
    this.logoUrl,
    required this.role,
    this.designation,
    this.enableHolidays = false,
  });

  factory Company.fromJson(Map<String, dynamic> j) => Company(
        id: j['id'],
        name: j['name'],
        logoUrl: j['logo_url'],
        role: j['role'] ?? '',
        designation: j['designation'],
        enableHolidays: j['enable_holidays'] ?? false,
      );
}

class AuthUser {
  final String token;
  final String username;
  final String fullName;
  final bool isSuperuser;
  final List<Company> companies;

  const AuthUser({
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
        companies: (j['companies'] as List).map((c) => Company.fromJson(c)).toList(),
      );
}

class HolidayPermissions {
  final bool canCreate;
  final bool canEdit;
  final bool canDelete;
  final bool canViewList;
  final bool canViewDetail;
  final bool isApprover;

  const HolidayPermissions({
    required this.canCreate,
    required this.canEdit,
    required this.canDelete,
    required this.canViewList,
    required this.canViewDetail,
    required this.isApprover,
  });

  factory HolidayPermissions.fromJson(Map<String, dynamic> j) => HolidayPermissions(
        canCreate: j['can_create_holiday'] ?? false,
        canEdit: j['can_edit_holiday'] ?? false,
        canDelete: j['can_delete_holiday'] ?? false,
        canViewList: j['can_view_holiday_list'] ?? true,
        canViewDetail: j['can_view_holiday_detail'] ?? true,
        isApprover: j['is_approver'] ?? false,
      );

  factory HolidayPermissions.defaultAll() => const HolidayPermissions(
        canCreate: true, canEdit: true, canDelete: true,
        canViewList: true, canViewDetail: true, isApprover: true,
      );
}

class DashboardStats {
  final int enquiryCount;
  final int upcomingCount;
  final int completedCount;
  final int settlementPending;
  final int bankPending;
  final int repairActive;

  const DashboardStats({
    required this.enquiryCount,
    required this.upcomingCount,
    required this.completedCount,
    required this.settlementPending,
    required this.bankPending,
    required this.repairActive,
  });

  factory DashboardStats.fromJson(Map<String, dynamic> j) => DashboardStats(
        enquiryCount: j['enquiry_count'] ?? 0,
        upcomingCount: j['upcoming_count'] ?? 0,
        completedCount: j['completed_count'] ?? 0,
        settlementPending: j['settlement_pending'] ?? 0,
        bankPending: j['bank_pending'] ?? 0,
        repairActive: j['repair_active'] ?? 0,
      );
}

class HolidayBooking {
  final int id;
  final String bookingNumber;
  final String tripDate;
  final String? returnDate;
  final String? returnTime;
  final String? departureTime;
  final String bookedBy;
  final String contactNumber;
  final String? secondContactNumber;
  final String departureLocation;
  final String destination;
  final String? purposeOfBooking;
  final int noOfPassengers;
  final String? bookedVehicle;
  final int? bookedVehicleId;
  final String bookedVehicleBatta;
  final String acType;
  final String? paymentTypeLabel;
  final String totalRent;
  final String serviceCharge;
  final String advanceAmount;
  final String totalAmount;
  final String balanceAmount;
  final int? maxKm;
  final String? extraKmCharge;
  final String? specialInstructions;
  final String status;
  final bool hasSettlement;
  final int? settlementId;
  final bool isBankApproved;
  final String? createdBy;
  final String? createdAt;

  const HolidayBooking({
    required this.id,
    required this.bookingNumber,
    required this.tripDate,
    this.returnDate,
    this.returnTime,
    this.departureTime,
    required this.bookedBy,
    required this.contactNumber,
    this.secondContactNumber,
    required this.departureLocation,
    required this.destination,
    this.purposeOfBooking,
    required this.noOfPassengers,
    this.bookedVehicle,
    this.bookedVehicleId,
    this.bookedVehicleBatta = '0',
    required this.acType,
    this.paymentTypeLabel,
    required this.totalRent,
    required this.serviceCharge,
    required this.advanceAmount,
    required this.totalAmount,
    required this.balanceAmount,
    this.maxKm,
    this.extraKmCharge,
    this.specialInstructions,
    required this.status,
    this.hasSettlement = false,
    this.settlementId,
    this.isBankApproved = false,
    this.createdBy,
    this.createdAt,
  });

  factory HolidayBooking.fromJson(Map<String, dynamic> j) => HolidayBooking(
        id: j['id'],
        bookingNumber: j['booking_number'] ?? '',
        tripDate: j['trip_date'] ?? '',
        returnDate: j['return_date'],
        returnTime: j['return_time'],
        departureTime: j['departure_time'],
        bookedBy: j['booked_by'] ?? '',
        contactNumber: j['contact_number'] ?? '',
        secondContactNumber: j['second_contact_number'],
        departureLocation: j['departure_location'] ?? '',
        destination: j['destination'] ?? '',
        purposeOfBooking: j['purpose_of_booking'],
        noOfPassengers: j['no_of_passengers'] ?? 1,
        bookedVehicle: j['booked_vehicle'],
        bookedVehicleId: j['booked_vehicle_id'],
        bookedVehicleBatta: j['booked_vehicle_batta'] ?? '0',
        acType: j['ac_type'] ?? 'NON_AC',
        paymentTypeLabel: j['payment_type_label'],
        totalRent: j['total_rent'] ?? '0',
        serviceCharge: j['service_charge'] ?? '0',
        advanceAmount: j['advance_amount'] ?? '0',
        totalAmount: j['total_amount'] ?? '0',
        balanceAmount: j['balance_amount'] ?? '0',
        maxKm: j['max_km'],
        extraKmCharge: j['extra_km_charge'],
        specialInstructions: j['special_instructions'],
        status: j['status'] ?? 'PENDING',
        hasSettlement: j['has_settlement'] ?? false,
        settlementId: j['settlement_id'],
        isBankApproved: j['is_bank_approved'] ?? false,
        createdBy: j['created_by'],
        createdAt: j['created_at'],
      );

  String get statusLabel {
    switch (status) {
      case 'PENDING': return 'Enquiry';
      case 'CONFIRMED': return 'Confirmed';
      case 'COMPLETED': return 'Completed';
      case 'CANCELLED': return 'Cancelled';
      default: return status;
    }
  }
}

class Vehicle {
  final int id;
  final String name;
  final String registrationNumber;
  final String battaPercentage;

  const Vehicle({
    required this.id,
    required this.name,
    required this.registrationNumber,
    required this.battaPercentage,
  });

  factory Vehicle.fromJson(Map<String, dynamic> j) => Vehicle(
        id: j['id'],
        name: j['name'],
        registrationNumber: j['registration_number'],
        battaPercentage: j['batta_percentage'] ?? '0',
      );
}

class PaymentTypeModel {
  final int id;
  final String name;
  const PaymentTypeModel({required this.id, required this.name});
  factory PaymentTypeModel.fromJson(Map<String, dynamic> j) =>
      PaymentTypeModel(id: j['id'], name: j['name']);
}

class CustomCharge {
  final int? id;
  String name;
  String amount;
  String? attachmentUrl;
  String? attachmentName;
  String? localFilePath;

  CustomCharge({
    this.id,
    this.name = '',
    this.amount = '',
    this.attachmentUrl,
    this.attachmentName,
    this.localFilePath,
  });

  factory CustomCharge.fromJson(Map<String, dynamic> j) => CustomCharge(
        id: j['id'],
        name: j['name'] ?? '',
        amount: j['amount'] ?? '0',
        attachmentUrl: j['attachment_url'],
        attachmentName: j['attachment_name'],
      );
}

class TripSettlement {
  final int? settlementId;
  final bool exists;
  final bool bankIsApproved;
  final int? bankId;
  final String? bankStatus;
  final String? bankDocUrl;
  final String commissionPercentage;
  final String commissionAmount;
  final String netRent;
  final String battaPercentage;
  final String battaAmount;
  final String dieselCharge;
  final String? dieselBillUrl;
  final String? dieselBillName;
  final String cleaningCharge;
  final String greaseCharge;
  final String? greaseBillUrl;
  final String? greaseBillName;
  final String netBalance;
  final List<CustomCharge> customCharges;

  const TripSettlement({
    this.settlementId,
    required this.exists,
    required this.bankIsApproved,
    this.bankId,
    this.bankStatus,
    this.bankDocUrl,
    required this.commissionPercentage,
    required this.commissionAmount,
    required this.netRent,
    required this.battaPercentage,
    required this.battaAmount,
    required this.dieselCharge,
    this.dieselBillUrl,
    this.dieselBillName,
    required this.cleaningCharge,
    required this.greaseCharge,
    this.greaseBillUrl,
    this.greaseBillName,
    required this.netBalance,
    required this.customCharges,
  });

  factory TripSettlement.fromJson(Map<String, dynamic> j) => TripSettlement(
        settlementId: j['settlement_id'],
        exists: j['exists'] ?? false,
        bankIsApproved: j['bank_is_approved'] ?? false,
        bankId: j['bank_id'],
        bankStatus: j['bank_status'],
        bankDocUrl: j['bank_doc_url'],
        commissionPercentage: j['commission_percentage'] ?? '0',
        commissionAmount: j['commission_amount'] ?? '0',
        netRent: j['net_rent'] ?? '0',
        battaPercentage: j['batta_percentage'] ?? '0',
        battaAmount: j['batta_amount'] ?? '0',
        dieselCharge: j['diesel_charge'] ?? '0',
        dieselBillUrl: j['diesel_bill_url'],
        dieselBillName: j['diesel_bill_name'],
        cleaningCharge: j['cleaning_charge'] ?? '0',
        greaseCharge: j['grease_charge'] ?? '0',
        greaseBillUrl: j['grease_bill_url'],
        greaseBillName: j['grease_bill_name'],
        netBalance: j['net_balance'] ?? '0',
        customCharges: j['custom_charges'] != null
            ? (j['custom_charges'] as List).map((c) => CustomCharge.fromJson(c)).toList()
            : [],
      );

  factory TripSettlement.empty() => const TripSettlement(
        exists: false, bankIsApproved: false,
        commissionPercentage: '0', commissionAmount: '0',
        netRent: '0', battaPercentage: '0', battaAmount: '0',
        dieselCharge: '0', cleaningCharge: '0', greaseCharge: '0',
        netBalance: '0', customCharges: [],
      );
}

class BankData {
  final int id;
  final String? documentUrl;
  final String? documentName;
  final String status;
  final String? approvedBy;
  final String? approvedAt;

  const BankData({
    required this.id,
    this.documentUrl,
    this.documentName,
    required this.status,
    this.approvedBy,
    this.approvedAt,
  });

  factory BankData.fromJson(Map<String, dynamic> j) => BankData(
        id: j['id'],
        documentUrl: j['document_url'],
        documentName: j['document_name'],
        status: j['status'] ?? '',
        approvedBy: j['approved_by'],
        approvedAt: j['approved_at'],
      );
}

class BankEntry {
  final int sl;
  final int settlementId;
  final int bookingId;
  final String bookingNumber;
  final String bookedBy;
  final String vehicle;
  final String netBalance;
  final BankData? bank;

  const BankEntry({
    required this.sl,
    required this.settlementId,
    required this.bookingId,
    required this.bookingNumber,
    required this.bookedBy,
    required this.vehicle,
    required this.netBalance,
    this.bank,
  });

  factory BankEntry.fromJson(Map<String, dynamic> j) => BankEntry(
        sl: j['sl'],
        settlementId: j['settlement_id'],
        bookingId: j['booking_id'],
        bookingNumber: j['booking_number'],
        bookedBy: j['booked_by'],
        vehicle: j['vehicle'] ?? '—',
        netBalance: j['net_balance'] ?? '0',
        bank: j['bank'] != null ? BankData.fromJson(j['bank']) : null,
      );
}

class RepairItem {
  final int? id;
  final String name;
  final String description;
  final String amount;
  final String? attachmentUrl;
  final String? attachmentName;
  String? localFilePath;

  RepairItem({
    this.id,
    required this.name,
    this.description = '',
    required this.amount,
    this.attachmentUrl,
    this.attachmentName,
    this.localFilePath,
  });

  factory RepairItem.fromJson(Map<String, dynamic> j) => RepairItem(
        id: j['id'],
        name: j['name'] ?? '',
        description: j['description'] ?? '',
        amount: j['amount'] ?? '0',
        attachmentUrl: j['attachment_url'],
        attachmentName: j['attachment_name'],
      );
}

class RepairRecord {
  final int id;
  final String repairNumber;
  final String? vehicle;
  final int? vehicleId;
  final String status;
  final String totalAmount;
  final String notes;
  final int? startingKm;
  final String? startingKmAttachmentUrl;
  final int? endingKm;
  final String? endingKmAttachmentUrl;
  final String createdAt;
  final int itemsCount;
  final String? bankStatus;
  final int? bankId;
  final String? bankDocUrl;
  final String? approvedBy;
  final String? approvedAt;
  final List<RepairItem> items;

  const RepairRecord({
    required this.id,
    required this.repairNumber,
    this.vehicle,
    this.vehicleId,
    required this.status,
    required this.totalAmount,
    required this.notes,
    this.startingKm,
    this.startingKmAttachmentUrl,
    this.endingKm,
    this.endingKmAttachmentUrl,
    required this.createdAt,
    required this.itemsCount,
    this.bankStatus,
    this.bankId,
    this.bankDocUrl,
    this.approvedBy,
    this.approvedAt,
    this.items = const [],
  });

  factory RepairRecord.fromJson(Map<String, dynamic> j) => RepairRecord(
        id: j['id'],
        repairNumber: j['repair_number'] ?? '',
        vehicle: j['vehicle'],
        vehicleId: j['vehicle_id'],
        status: j['status'] ?? 'DRAFT',
        totalAmount: j['total_amount'] ?? '0',
        notes: j['notes'] ?? '',
        startingKm: j['starting_km'],
        startingKmAttachmentUrl: j['starting_km_attachment_url'],
        endingKm: j['ending_km'],
        endingKmAttachmentUrl: j['ending_km_attachment_url'],
        createdAt: j['created_at'] ?? '',
        itemsCount: j['items_count'] ?? 0,
        bankStatus: j['bank_status'],
        bankId: j['bank_id'],
        bankDocUrl: j['bank_doc_url'],
        approvedBy: j['approved_by'],
        approvedAt: j['approved_at'],
        items: j['items'] != null
            ? (j['items'] as List).map((i) => RepairItem.fromJson(i)).toList()
            : [],
      );

  String get statusLabel {
    switch (status) {
      case 'DRAFT': return 'Draft';
      case 'SUBMITTED': return 'Submitted';
      case 'APPROVED': return 'Approved';
      default: return status;
    }
  }
}
