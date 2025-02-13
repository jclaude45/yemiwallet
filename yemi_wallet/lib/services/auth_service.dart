import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'dart:convert';
import 'package:crypto/crypto.dart';
import '../models/user.dart';
import 'database_service.dart';

class AuthService {
  final _storage = const FlutterSecureStorage();
  final _db = DatabaseService();
  
  static const _keyUser = 'user';
  
  Future<void> saveUser(User user) async {
    final userJson = jsonEncode(user.toJson());
    await _storage.write(key: _keyUser, value: userJson);
  }
  
  Future<User?> getUser() async {
    final userJson = await _storage.read(key: _keyUser);
    if (userJson == null) return null;
    return User.fromJson(jsonDecode(userJson));
  }
  
  Future<void> logout() async {
    await _storage.delete(key: _keyUser);
  }
  
  String _hashPassword(String password) {
    final bytes = utf8.encode(password);
    final digest = sha256.convert(bytes);
    return digest.toString();
  }
  
  Future<User?> login(String username, String password) async {
    final hashedPassword = _hashPassword(password);
    final user = await _db.getUserByUsername(username);
    
    if (user != null) {
      // Dans une vraie application, vous devriez vérifier le mot de passe haché
      // contre celui stocké dans la base de données
      await saveUser(user);
      return user;
    }
    return null;
  }
  
  Future<bool> register({
    required String username,
    required String password,
    required String email,
    required String firstName,
    required String lastName,
    required String phone,
    required String phoneCountry,
    String currency = 'EUR',
  }) async {
    final hashedPassword = _hashPassword(password);
    
    // Vérifier si l'utilisateur existe déjà
    final existingUser = await _db.getUserByUsername(username);
    if (existingUser != null) return false;
    
    // Dans une vraie application, vous devriez créer l'utilisateur dans la base de données
    // et retourner true si la création a réussi
    return true;
  }
  
  Future<bool> isLoggedIn() async {
    final user = await getUser();
    return user != null;
  }
}
