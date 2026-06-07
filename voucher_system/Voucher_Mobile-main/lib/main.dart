// lib/main.dart

import 'package:flutter/material.dart';
import 'package:app_links/app_links.dart';
import 'services/api_service.dart';
import 'screens/login_screen.dart';
import 'screens/company_select_screen.dart';
import 'screens/voucher_detail_screen.dart';

/// Global navigator key — lets deep link handler navigate from outside the tree.
final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

/// Voucher ID waiting to be opened after company selection.
int? pendingVoucherId;

/// Parse voucher ID from deep link URI.
/// Expected format: voucher://detail/123
int? _parseVoucherId(Uri? uri) {
  if (uri == null) return null;
  if (uri.scheme != 'voucher') return null;
  if (uri.host != 'detail') return null;
  final segments = uri.pathSegments;
  if (segments.isEmpty) return null;
  return int.tryParse(segments.first);
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const VoucherApp());
}

class VoucherApp extends StatefulWidget {
  const VoucherApp({super.key});

  @override
  State<VoucherApp> createState() => _VoucherAppState();
}

class _VoucherAppState extends State<VoucherApp> {
  late final AppLinks _appLinks;

  @override
  void initState() {
    super.initState();
    _initDeepLinks();
  }

  Future<void> _initDeepLinks() async {
    _appLinks = AppLinks();

    // Cold start — app was launched by tapping the link
    final initialLink = await _appLinks.getInitialLink();
    final initialId = _parseVoucherId(initialLink);
    if (initialId != null) pendingVoucherId = initialId;

    // App already running — link tapped while app in foreground/background
    _appLinks.uriLinkStream.listen((Uri uri) {
      final id = _parseVoucherId(uri);
      if (id == null) return;
      final nav = navigatorKey.currentState;
      if (nav != null && ApiService.instance.currentUser != null) {
        nav.push(MaterialPageRoute(
          builder: (_) => VoucherDetailScreen(voucherId: id),
        ));
      } else {
        pendingVoucherId = id;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: navigatorKey,
      title: 'Voucher Approvals',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF667EEA),
          primary: const Color(0xFF667EEA),
        ),
        useMaterial3: true,
        fontFamily: 'Roboto',
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF667EEA),
          foregroundColor: Colors.white,
          elevation: 0,
          centerTitle: true,
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF667EEA),
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
            padding: const EdgeInsets.symmetric(vertical: 14),
          ),
        ),
        cardTheme: CardThemeData(
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          filled: true,
          fillColor: Colors.grey.shade50,
        ),
      ),
      home: const _SplashDecider(),
    );
  }
}

/// Checks for saved session and routes accordingly.
class _SplashDecider extends StatefulWidget {
  const _SplashDecider();

  @override
  State<_SplashDecider> createState() => _SplashDeciderState();
}

class _SplashDeciderState extends State<_SplashDecider> {
  @override
  void initState() {
    super.initState();
    _decide();
  }

  Future<void> _decide() async {
    await Future.delayed(const Duration(milliseconds: 600));
    if (!mounted) return;

    final restored = await ApiService.instance.tryRestoreSession();
    if (!mounted) return;

    if (restored) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => CompanySelectScreen(
            user: ApiService.instance.currentUser!,
          ),
        ),
      );
    } else {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const LoginScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF667EEA), Color(0xFF764BA2)],
          ),
        ),
        child: const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.receipt_long, size: 72, color: Colors.white),
              SizedBox(height: 16),
              Text(
                'Voucher App',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
