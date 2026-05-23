// lib/main.dart

import 'package:flutter/material.dart';
import 'services/api_service.dart';
import 'screens/login_screen.dart';
import 'screens/company_select_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const VoucherApp());
}

class VoucherApp extends StatelessWidget {
  const VoucherApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
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
    // Small delay for splash feel
    await Future.delayed(const Duration(milliseconds: 600));

    if (!mounted) return;

    final restored = await ApiService.instance.tryRestoreSession();

    if (!mounted) return;

    if (restored) {
      // Need company selection again (companies not persisted)
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