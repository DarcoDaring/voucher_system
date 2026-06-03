import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config/api_config.dart';
import '../models/models.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  ApiException(this.message, {this.statusCode});
  @override
  String toString() => message;
}

class ApiService {
  ApiService._();
  static ApiService? _instance;
  static ApiService get instance => _instance ??= ApiService._();

  String? _token;
  AuthUser? _currentUser;
  Company? _activeCompany;
  HolidayPermissions? _permissions;
  DateTime? _lastActive;

  static const _keyToken = 'h_auth_token';
  static const _keyUsername = 'h_username';
  static const _keyFullName = 'h_full_name';
  static const _keySuperuser = 'h_is_superuser';
  static const _keyCompanyId = 'h_active_company_id';
  static const _keyCompanyName = 'h_active_company_name';
  static const _keySavedUser = 'h_saved_username';
  static const _keySavedPass = 'h_saved_password';
  static const _keyLastActive = 'h_last_active';
  static const _sessionTimeoutMinutes = 30;

  bool get isLoggedIn => _token != null;
  AuthUser? get currentUser => _currentUser;
  Company? get activeCompany => _activeCompany;
  HolidayPermissions? get permissions => _permissions;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Authorization': 'Token $_token',
      };

  Map<String, String> get _authHeader => {'Authorization': 'Token $_token'};

  void _updateLastActive() {
    _lastActive = DateTime.now();
    SharedPreferences.getInstance().then(
      (p) => p.setString(_keyLastActive, _lastActive!.toIso8601String()),
    );
  }

  bool isSessionExpired() {
    if (_lastActive == null) return true;
    return DateTime.now().difference(_lastActive!).inMinutes >= _sessionTimeoutMinutes;
  }

  Future<bool> tryRestoreSession() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(_keyToken);
    if (token == null) return false;

    final lastActiveStr = prefs.getString(_keyLastActive);
    if (lastActiveStr != null) {
      final lastActive = DateTime.tryParse(lastActiveStr);
      if (lastActive != null &&
          DateTime.now().difference(lastActive).inMinutes >= _sessionTimeoutMinutes) {
        await logout();
        return false;
      }
      _lastActive = lastActive;
    }

    _token = token;
    final companyId = prefs.getInt(_keyCompanyId);
    final companyName = prefs.getString(_keyCompanyName) ?? '';
    if (companyId != null) {
      _activeCompany = Company(id: companyId, name: companyName, role: '');
    }
    return true;
  }

  Future<AuthUser> login(String username, String password) async {
    final response = await http.post(
      Uri.parse(ApiConfig.loginEndpoint),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    if (response.statusCode != 200) {
      throw ApiException(data['error'] ?? 'Login failed', statusCode: response.statusCode);
    }
    final user = AuthUser.fromJson(data);
    _token = user.token;
    _currentUser = user;
    _updateLastActive();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyToken, user.token);
    await prefs.setString(_keyUsername, user.username);
    await prefs.setString(_keyFullName, user.fullName);
    await prefs.setBool(_keySuperuser, user.isSuperuser);

    return user;
  }

  Future<void> logout() async {
    _token = null;
    _currentUser = null;
    _activeCompany = null;
    _permissions = null;
    _lastActive = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyToken);
    await prefs.remove(_keyCompanyId);
    await prefs.remove(_keyCompanyName);
    await prefs.remove(_keyLastActive);
  }

  Future<void> setActiveCompany(Company company) async {
    _activeCompany = company;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyCompanyId, company.id);
    await prefs.setString(_keyCompanyName, company.name);
    _permissions = null;
  }

  Future<void> saveCredentials(String username, String password) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keySavedUser, username);
    await prefs.setString(_keySavedPass, password);
  }

  Future<Map<String, String>?> loadSavedCredentials() async {
    final prefs = await SharedPreferences.getInstance();
    final u = prefs.getString(_keySavedUser);
    final p = prefs.getString(_keySavedPass);
    if (u != null && p != null) return {'username': u, 'password': p};
    return null;
  }

  String _companyParam() => '?company_id=${_activeCompany!.id}';

  String _extractError(Map<String, dynamic> data) =>
      data['error'] ?? data['detail'] ?? 'Unknown error';

  Future<Map<String, dynamic>> _get(String url) async {
    _updateLastActive();
    try {
      final response = await http.get(Uri.parse(url), headers: _headers);
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      if (response.statusCode >= 400) {
        throw ApiException(_extractError(data), statusCode: response.statusCode);
      }
      return data;
    } on SocketException {
      throw ApiException('No internet connection. Check server is running.');
    }
  }

  Future<Map<String, dynamic>> _post(String url, Map<String, dynamic> body) async {
    _updateLastActive();
    try {
      final response = await http.post(
        Uri.parse(url),
        headers: _headers,
        body: jsonEncode(body),
      );
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      if (response.statusCode >= 400) {
        throw ApiException(_extractError(data), statusCode: response.statusCode);
      }
      return data;
    } on SocketException {
      throw ApiException('No internet connection. Check server is running.');
    }
  }

  Future<Map<String, dynamic>> _delete(String url) async {
    _updateLastActive();
    try {
      final response = await http.delete(Uri.parse(url), headers: _headers);
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      if (response.statusCode >= 400) {
        throw ApiException(_extractError(data), statusCode: response.statusCode);
      }
      return data;
    } on SocketException {
      throw ApiException('No internet connection. Check server is running.');
    }
  }

  Future<Map<String, dynamic>> _multipart(
    String method,
    String url,
    Map<String, String> fields,
    Map<String, String> filePaths,
  ) async {
    _updateLastActive();
    try {
      final request = http.MultipartRequest(method, Uri.parse(url));
      request.headers.addAll(_authHeader);
      request.fields.addAll(fields);
      for (final entry in filePaths.entries) {
        if (entry.value.isNotEmpty) {
          request.files.add(await http.MultipartFile.fromPath(entry.key, entry.value));
        }
      }
      final streamed = await request.send();
      final body = await streamed.stream.bytesToString();
      final data = jsonDecode(body) as Map<String, dynamic>;
      if (streamed.statusCode >= 400) {
        throw ApiException(_extractError(data), statusCode: streamed.statusCode);
      }
      return data;
    } on SocketException {
      throw ApiException('No internet connection. Check server is running.');
    }
  }

  // ────────────────────────────────────────────────────────────────
  // PERMISSIONS & STATS
  // ────────────────────────────────────────────────────────────────

  Future<HolidayPermissions> getPermissions() async {
    final data = await _get(
      '${ApiConfig.holidayPermissionsEndpoint}${_companyParam()}',
    );
    _permissions = HolidayPermissions.fromJson(data);
    return _permissions!;
  }

  Future<DashboardStats> getStats() async {
    final data = await _get('${ApiConfig.holidayStatsEndpoint}${_companyParam()}');
    return DashboardStats.fromJson(data);
  }

  // ────────────────────────────────────────────────────────────────
  // HOLIDAY BOOKINGS
  // ────────────────────────────────────────────────────────────────

  Future<List<HolidayBooking>> getHolidays({String? status}) async {
    var url = '${ApiConfig.holidayListEndpoint}${_companyParam()}';
    if (status != null) url += '&status=$status';
    final data = await _get(url);
    return (data['bookings'] as List).map((b) => HolidayBooking.fromJson(b)).toList();
  }

  Future<HolidayBooking> getHolidayDetail(int id) async {
    final data = await _get(
      '${ApiConfig.holidayDetailEndpoint(id)}${_companyParam()}',
    );
    return HolidayBooking.fromJson(data);
  }

  Future<Map<String, dynamic>> createHoliday(Map<String, String> fields) async {
    fields['company_id'] = _activeCompany!.id.toString();
    return await _post(ApiConfig.holidayCreateEndpoint, fields.map((k, v) => MapEntry(k, v)));
  }

  Future<Map<String, dynamic>> confirmHoliday(int id) async {
    return await _post(ApiConfig.holidayConfirmEndpoint(id), {
      'company_id': _activeCompany!.id,
    });
  }

  Future<Map<String, dynamic>> updateHoliday(int id, Map<String, dynamic> fields) async {
    fields['company_id'] = _activeCompany!.id;
    return await _post(ApiConfig.holidayUpdateEndpoint(id), fields);
  }

  Future<Map<String, dynamic>> deleteHoliday(int id) async {
    return await _delete(
      '${ApiConfig.holidayDeleteEndpoint(id)}${_companyParam()}',
    );
  }

  // ────────────────────────────────────────────────────────────────
  // MASTER DATA
  // ────────────────────────────────────────────────────────────────

  Future<List<Vehicle>> getVehicles() async {
    final data = await _get('${ApiConfig.vehicleListEndpoint}${_companyParam()}');
    return (data['vehicles'] as List).map((v) => Vehicle.fromJson(v)).toList();
  }

  Future<List<PaymentTypeModel>> getPaymentTypes() async {
    final data = await _get('${ApiConfig.paymentTypeListEndpoint}${_companyParam()}');
    return (data['payment_types'] as List).map((p) => PaymentTypeModel.fromJson(p)).toList();
  }

  // ────────────────────────────────────────────────────────────────
  // TRIP SETTLEMENT
  // ────────────────────────────────────────────────────────────────

  Future<List<HolidayBooking>> getCompletedHolidays() async {
    final data = await _get('${ApiConfig.holidayCompletedEndpoint}${_companyParam()}');
    return (data['bookings'] as List).map((b) => HolidayBooking.fromJson(b)).toList();
  }

  Future<TripSettlement> getSettlement(int bookingId) async {
    final data = await _get(
      '${ApiConfig.settlementGetEndpoint(bookingId)}${_companyParam()}',
    );
    return TripSettlement.fromJson(data);
  }

  Future<Map<String, dynamic>> saveSettlement(
    int bookingId,
    Map<String, String> fields,
    Map<String, String> filePaths,
  ) async {
    fields['company_id'] = _activeCompany!.id.toString();
    return await _multipart('POST', ApiConfig.settlementSaveEndpoint(bookingId), fields, filePaths);
  }

  // ────────────────────────────────────────────────────────────────
  // BANK
  // ────────────────────────────────────────────────────────────────

  Future<List<BankEntry>> getBankList() async {
    final data = await _get('${ApiConfig.bankListEndpoint}${_companyParam()}');
    return (data['entries'] as List).map((e) => BankEntry.fromJson(e)).toList();
  }

  Future<Map<String, dynamic>> uploadBankDocument(int settlementId, String filePath) async {
    return await _multipart(
      'POST',
      ApiConfig.bankUploadEndpoint(settlementId),
      {'company_id': _activeCompany!.id.toString()},
      {'bank_document': filePath},
    );
  }

  Future<Map<String, dynamic>> approveBank(int bankId) async {
    return await _post(ApiConfig.bankApproveEndpoint(bankId), {
      'company_id': _activeCompany!.id,
    });
  }

  // ────────────────────────────────────────────────────────────────
  // REPAIRS
  // ────────────────────────────────────────────────────────────────

  Future<List<RepairRecord>> getRepairs() async {
    final data = await _get('${ApiConfig.repairListEndpoint}${_companyParam()}');
    return (data['repairs'] as List).map((r) => RepairRecord.fromJson(r)).toList();
  }

  Future<RepairRecord> getRepairDetail(int id) async {
    final data = await _get('${ApiConfig.repairDetailEndpoint(id)}${_companyParam()}');
    return RepairRecord.fromJson(data);
  }

  Future<Map<String, dynamic>> createRepair(
    Map<String, String> fields,
    Map<String, String> filePaths,
  ) async {
    fields['company_id'] = _activeCompany!.id.toString();
    return await _multipart('POST', ApiConfig.repairCreateEndpoint, fields, filePaths);
  }

  Future<Map<String, dynamic>> submitRepairToBank(int id, String? filePath) async {
    return await _multipart(
      'POST',
      ApiConfig.repairSubmitBankEndpoint(id),
      {'company_id': _activeCompany!.id.toString()},
      filePath != null ? {'bank_document': filePath} : {},
    );
  }

  Future<Map<String, dynamic>> approveRepair(int id) async {
    return await _post(ApiConfig.repairBankApproveEndpoint(id), {
      'company_id': _activeCompany!.id,
    });
  }

  Future<Map<String, dynamic>> deleteRepair(int id) async {
    return await _delete('${ApiConfig.repairDeleteEndpoint(id)}${_companyParam()}');
  }
}
