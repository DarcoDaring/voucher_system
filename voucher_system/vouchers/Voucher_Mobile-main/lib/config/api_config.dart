// lib/config/api_config.dart
 
class ApiConfig {
  // ── Change this to your server URL ───────────────────────────
  // Local development:   'http://10.0.2.2:8000'  (Android emulator)
  //                      'http://127.0.0.1:8000'  (iOS simulator)
  // Production AWS:      'https://your-domain.com'
  static const String baseUrl = 'https://voucher.thenorthpark.com';
 
  // Mobile API endpoints
  static const String loginEndpoint         = '$baseUrl/api/mobile/login/';
  static const String voucherListEndpoint   = '$baseUrl/api/mobile/vouchers/';
  static String voucherDetailEndpoint(int id) => '$baseUrl/api/mobile/vouchers/$id/';
  static String voucherActionEndpoint(int id) => '$baseUrl/api/mobile/vouchers/$id/action/';
}