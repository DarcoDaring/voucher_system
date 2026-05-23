// lib/services/api_service.dart

import 'dart:convert';
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
  static ApiService? _instance;
  static ApiService get instance => _instance ??= ApiService._();
  ApiService._();

  String? _token;
  AuthUser? _currentUser;
  Company? _activeCompany;

  // ── Persistence keys ──────────────────────────────────────────
  static const _keyToken      = 'auth_token';
  static const _keyUsername   = 'username';
  static const _keyFullName   = 'full_name';
  static const _keySuperuser  = 'is_superuser';
  static const _keyLastActive     = 'last_active';
  static const _keySavedUsername  = 'saved_username';
  static const _keySavedPassword  = 'saved_password';

  static const _sessionTimeout = Duration(minutes: 30);

  AuthUser? get currentUser => _currentUser;
  Company? get activeCompany => _activeCompany;
  bool get isLoggedIn => _token != null;

  void setActiveCompany(Company c) => _activeCompany = c;

  // ── Session expiry ────────────────────────────────────────────
  Future<void> _updateLastActive() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyLastActive, DateTime.now().millisecondsSinceEpoch);
  }

  Future<bool> isSessionExpired() async {
    final prefs = await SharedPreferences.getInstance();
    final lastActive = prefs.getInt(_keyLastActive);
    if (lastActive == null) return true;
    final elapsed = DateTime.now().millisecondsSinceEpoch - lastActive;
    return elapsed > _sessionTimeout.inMilliseconds;
  }

  // ── Load saved session ────────────────────────────────────────
  Future<bool> tryRestoreSession() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(_keyToken);
    if (_token == null) return false;

    if (await isSessionExpired()) {
      await logout();
      return false;
    }

    final username   = prefs.getString(_keyUsername) ?? '';
    final fullName   = prefs.getString(_keyFullName) ?? username;
    final superuser  = prefs.getBool(_keySuperuser) ?? false;

    // Rebuild a minimal AuthUser (companies loaded fresh on login)
    _currentUser = AuthUser(
      token: _token!,
      username: username,
      fullName: fullName,
      isSuperuser: superuser,
      companies: [],
    );
    return true;
  }

  // ── AUTH ──────────────────────────────────────────────────────
  Future<AuthUser> login(String username, String password) async {
    final res = await http.post(
      Uri.parse(ApiConfig.loginEndpoint),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );

    final body = jsonDecode(res.body);

    if (res.statusCode != 200) {
      throw ApiException(body['error'] ?? 'Login failed', statusCode: res.statusCode);
    }

    final user = AuthUser.fromJson(body);
    _token = user.token;
    _currentUser = user;

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyToken, user.token);
    await prefs.setString(_keyUsername, user.username);
    await prefs.setString(_keyFullName, user.fullName);
    await prefs.setBool(_keySuperuser, user.isSuperuser);
    await _updateLastActive();

    return user;
  }

  Future<void> logout() async {
    _token = null;
    _currentUser = null;
    _activeCompany = null;
    final prefs = await SharedPreferences.getInstance();
    // Remove only session keys — preserve saved credentials
    await prefs.remove(_keyToken);
    await prefs.remove(_keyUsername);
    await prefs.remove(_keyFullName);
    await prefs.remove(_keySuperuser);
    await prefs.remove(_keyLastActive);
  }

  // ── Saved credentials (Remember Me) ──────────────────────────
  Future<void> saveCredentials(String username, String password) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keySavedUsername, username);
    await prefs.setString(_keySavedPassword, password);
  }

  Future<({String username, String password})?> loadSavedCredentials() async {
    final prefs = await SharedPreferences.getInstance();
    final username = prefs.getString(_keySavedUsername);
    final password = prefs.getString(_keySavedPassword);
    if (username == null || password == null) return null;
    return (username: username, password: password);
  }

  Future<void> clearSavedCredentials() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keySavedUsername);
    await prefs.remove(_keySavedPassword);
  }

  // ── Helpers ───────────────────────────────────────────────────
  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Authorization': 'Token $_token',
      };

  Future<dynamic> _get(String url) async {
    final res = await http.get(Uri.parse(url), headers: _headers);
    final result = _handleResponse(res);
    await _updateLastActive();
    return result;
  }

  Future<dynamic> _post(String url, Map<String, dynamic> body) async {
    final res = await http.post(
      Uri.parse(url),
      headers: _headers,
      body: jsonEncode(body),
    );
    final result = _handleResponse(res);
    await _updateLastActive();
    return result;
  }

  dynamic _handleResponse(http.Response res) {
    final body = jsonDecode(utf8.decode(res.bodyBytes));
    if (res.statusCode >= 200 && res.statusCode < 300) return body;
    final msg = body['error'] ?? body['detail'] ?? 'Request failed';
    throw ApiException(msg, statusCode: res.statusCode);
  }

  // ── VOUCHERS ──────────────────────────────────────────────────
  Future<List<VoucherSummary>> getVouchers({String? status}) async {
    final companyId = _activeCompany!.id;
    var url = '${ApiConfig.voucherListEndpoint}?company_id=$companyId';
    if (status != null && status.isNotEmpty) url += '&status=$status';

    final data = await _get(url);
    return (data['vouchers'] as List)
        .map((v) => VoucherSummary.fromJson(v))
        .toList();
  }

  Future<VoucherDetail> getVoucherDetail(int voucherId) async {
    final companyId = _activeCompany!.id;
    final url =
        '${ApiConfig.voucherDetailEndpoint(voucherId)}?company_id=$companyId';
    final data = await _get(url);
    return VoucherDetail.fromJson(data);
  }

  Future<Map<String, dynamic>> approveVoucher(
    int voucherId, {
    required String action,
    String rejectionReason = '',
  }) async {
    final companyId = _activeCompany!.id;
    final body = {
      'company_id': companyId,
      'action': action,
      if (action == 'REJECTED') 'rejection_reason': rejectionReason,
    };
    return await _post(ApiConfig.voucherActionEndpoint(voucherId), body);
  }
}