class ApiConfig {
  // For Android emulator testing. Change to your domain for production.
  static const String baseUrl = 'https://voucher.thenorthpark.com'; 

  // Auth
  static const String loginEndpoint = '$baseUrl/api/mobile/login/';

  // Holidays
  static const String holidayListEndpoint = '$baseUrl/api/mobile/holidays/';
  static const String holidayCreateEndpoint = '$baseUrl/api/mobile/holidays/create/';
  static const String holidayCompletedEndpoint = '$baseUrl/api/mobile/holidays/completed/';
  static const String holidayPermissionsEndpoint = '$baseUrl/api/mobile/holidays/permissions/';
  static const String holidayStatsEndpoint = '$baseUrl/api/mobile/holidays/stats/';
  static String holidayDetailEndpoint(int id) => '$baseUrl/api/mobile/holidays/$id/';
  static String holidayConfirmEndpoint(int id) => '$baseUrl/api/mobile/holidays/$id/confirm/';
  static String holidayUpdateEndpoint(int id) => '$baseUrl/api/mobile/holidays/$id/update/';
  static String holidayDeleteEndpoint(int id) => '$baseUrl/api/mobile/holidays/$id/delete/';
  static String settlementGetEndpoint(int bookingId) => '$baseUrl/api/mobile/holidays/$bookingId/settlement/';
  static String settlementSaveEndpoint(int bookingId) => '$baseUrl/api/mobile/holidays/$bookingId/settlement/save/';

  // Bank
  static const String bankListEndpoint = '$baseUrl/api/mobile/holidays/bank/';
  static String bankUploadEndpoint(int settlementId) => '$baseUrl/api/mobile/holidays/bank/$settlementId/upload/';
  static String bankApproveEndpoint(int bankId) => '$baseUrl/api/mobile/holidays/bank/$bankId/approve/';

  // Master data
  static const String vehicleListEndpoint = '$baseUrl/api/mobile/vehicles/';
  static const String paymentTypeListEndpoint = '$baseUrl/api/mobile/payment-types/';

  // Repair
  static const String repairListEndpoint = '$baseUrl/api/mobile/repairs/';
  static const String repairCreateEndpoint = '$baseUrl/api/mobile/repairs/create/';
  static String repairDetailEndpoint(int id) => '$baseUrl/api/mobile/repairs/$id/';
  static String repairSubmitBankEndpoint(int id) => '$baseUrl/api/mobile/repairs/$id/submit-to-bank/';
  static String repairBankApproveEndpoint(int id) => '$baseUrl/api/mobile/repairs/$id/bank/approve/';
  static String repairDeleteEndpoint(int id) => '$baseUrl/api/mobile/repairs/$id/delete/';
  static String repairUpdateEndpoint(int id) => '$baseUrl/api/mobile/repairs/$id/update/';
}
