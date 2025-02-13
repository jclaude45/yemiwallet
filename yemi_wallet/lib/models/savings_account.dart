import 'package:intl/intl.dart';

class SavingsAccount {
  final int id;
  final String name;
  final double percentage;
  double currentAmount;
  final double? targetAmount;
  final DateTime? targetDate;
  final int userId;
  bool isActive;
  bool isArchived;
  final DateTime createdAt;
  final DateTime updatedAt;

  SavingsAccount({
    required this.id,
    required this.name,
    required this.percentage,
    required this.currentAmount,
    this.targetAmount,
    this.targetDate,
    required this.userId,
    this.isActive = true,
    this.isArchived = false,
    required this.createdAt,
    required this.updatedAt,
  });

  double get progress {
    if (targetAmount == null || targetAmount! <= 0) return 0;
    return (currentAmount / targetAmount! * 100).clamp(0, 100);
  }

  int? get daysRemaining {
    if (targetDate == null) return null;
    return targetDate!.difference(DateTime.now()).inDays;
  }

  double? get dailySavingNeeded {
    if (targetAmount == null || targetDate == null || daysRemaining == null || daysRemaining! <= 0) {
      return null;
    }
    final remaining = targetAmount! - currentAmount;
    if (remaining <= 0) return 0;
    return remaining / daysRemaining!;
  }

  factory SavingsAccount.fromJson(Map<String, dynamic> json) {
    return SavingsAccount(
      id: json['id'],
      name: json['name'],
      percentage: json['percentage'].toDouble(),
      currentAmount: json['current_amount'].toDouble(),
      targetAmount: json['target_amount']?.toDouble(),
      targetDate: json['target_date'] != null 
          ? DateFormat('yyyy-MM-dd').parse(json['target_date'])
          : null,
      userId: json['user_id'],
      isActive: json['is_active'] == 1,
      isArchived: json['is_archived'] == 1,
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'percentage': percentage,
      'current_amount': currentAmount,
      'target_amount': targetAmount,
      'target_date': targetDate?.toIso8601String(),
      'user_id': userId,
      'is_active': isActive ? 1 : 0,
      'is_archived': isArchived ? 1 : 0,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }
}
