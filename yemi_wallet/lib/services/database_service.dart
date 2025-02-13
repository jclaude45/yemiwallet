import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';
import '../models/user.dart';
import '../models/savings_account.dart';
import '../models/transaction.dart';

class DatabaseService {
  static final DatabaseService _instance = DatabaseService._internal();
  static Database? _database;

  factory DatabaseService() => _instance;

  DatabaseService._internal();

  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDatabase();
    return _database!;
  }

  Future<Database> _initDatabase() async {
    Directory documentsDirectory = await getApplicationDocumentsDirectory();
    String path = join(documentsDirectory.path, 'yemi_wallet.db');

    return await openDatabase(
      path,
      version: 1,
      onCreate: _createTables,
    );
  }

  Future<void> _createTables(Database db, int version) async {
    await db.execute('''
      CREATE TABLE user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        phone_country TEXT NOT NULL,
        currency TEXT DEFAULT 'EUR'
      )
    ''');

    await db.execute('''
      CREATE TABLE savings_account (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        percentage REAL NOT NULL,
        current_amount REAL DEFAULT 0.0,
        target_amount REAL,
        target_date TEXT,
        user_id INTEGER NOT NULL,
        is_active INTEGER DEFAULT 1,
        is_archived INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES user (id)
      )
    ''');

    await db.execute('''
      CREATE TABLE transaction (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_type TEXT NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        transaction_date TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        category TEXT,
        savings_account_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES user (id),
        FOREIGN KEY (savings_account_id) REFERENCES savings_account (id)
      )
    ''');
  }

  // User operations
  Future<User?> getUser(int id) async {
    final db = await database;
    final List<Map<String, dynamic>> maps = await db.query(
      'user',
      where: 'id = ?',
      whereArgs: [id],
    );

    if (maps.isEmpty) return null;
    return User.fromJson(maps.first);
  }

  Future<User?> getUserByUsername(String username) async {
    final db = await database;
    final List<Map<String, dynamic>> maps = await db.query(
      'user',
      where: 'username = ?',
      whereArgs: [username],
    );

    if (maps.isEmpty) return null;
    return User.fromJson(maps.first);
  }

  // Savings Account operations
  Future<List<SavingsAccount>> getSavingsAccounts(int userId) async {
    final db = await database;
    final List<Map<String, dynamic>> maps = await db.query(
      'savings_account',
      where: 'user_id = ?',
      whereArgs: [userId],
      orderBy: 'created_at DESC',
    );

    return List.generate(maps.length, (i) => SavingsAccount.fromJson(maps[i]));
  }

  Future<int> createSavingsAccount(SavingsAccount account) async {
    final db = await database;
    return await db.insert('savings_account', account.toJson());
  }

  // Transaction operations
  Future<List<Transaction>> getTransactions(int userId) async {
    final db = await database;
    final List<Map<String, dynamic>> maps = await db.query(
      'transaction',
      where: 'user_id = ?',
      whereArgs: [userId],
      orderBy: 'transaction_date DESC',
    );

    return List.generate(maps.length, (i) => Transaction.fromJson(maps[i]));
  }

  Future<int> createTransaction(Transaction transaction) async {
    final db = await database;
    return await db.insert('transaction', transaction.toJson());
  }
}
