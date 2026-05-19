import 'package:flutter/foundation.dart';

class AuthSession {
  const AuthSession({required this.accessToken, required this.user});

  final String accessToken;
  final Map<String, dynamic> user;

  String get displayName => '${user['display_name'] ?? user['email'] ?? 'User'}';
  String get email => '${user['email'] ?? ''}';
  List<String> get roles => (user['roles'] as List<dynamic>? ?? <dynamic>[]).map((role) => '$role').toList();
  bool get isAdmin => roles.contains('Admin');
}

class AuthController extends ChangeNotifier {
  AuthController._();

  static final AuthController instance = AuthController._();

  AuthSession? _session;

  AuthSession? get session => _session;
  String? get accessToken => _session?.accessToken;
  Map<String, dynamic>? get user => _session?.user;
  bool get isAuthenticated => _session != null;
  bool get isAdmin => _session?.isAdmin ?? false;

  void setSession({required String accessToken, required Map<String, dynamic> user}) {
    _session = AuthSession(accessToken: accessToken, user: user);
    notifyListeners();
  }

  void updateUser(Map<String, dynamic> user) {
    final token = accessToken;
    if (token == null) return;
    _session = AuthSession(accessToken: token, user: user);
    notifyListeners();
  }

  void signOut() {
    _session = null;
    notifyListeners();
  }
}
