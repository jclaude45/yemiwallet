class Transaction {
  final int id;
  final String type;
  final String description;
  final double amount;
  final DateTime date;
  final int userId;
  final String? category;
  final int? savingsAccountId;

  Transaction({
    required this.id,
    required this.type,
    required this.description,
    required this.amount,
    required this.date,
    required this.userId,
    this.category,
    this.savingsAccountId,
  });

  bool get isIncome => type == 'income';
  bool get isExpense => type == 'expense';

  factory Transaction.fromJson(Map<String, dynamic> json) {
    return Transaction(
      id: json['id'],
      type: json['transaction_type'],
      description: json['description'],
      amount: json['amount'].toDouble(),
      date: DateTime.parse(json['transaction_date']),
      userId: json['user_id'],
      category: json['category'],
      savingsAccountId: json['savings_account_id'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'transaction_type': type,
      'description': description,
      'amount': amount,
      'transaction_date': date.toIso8601String(),
      'user_id': userId,
      'category': category,
      'savings_account_id': savingsAccountId,
    };
  }
}
