import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../models/savings_account.dart';
import '../services/database_service.dart';

class SavingsScreen extends StatefulWidget {
  const SavingsScreen({super.key});

  @override
  State<SavingsScreen> createState() => _SavingsScreenState();
}

class _SavingsScreenState extends State<SavingsScreen> {
  final _db = DatabaseService();
  List<SavingsAccount> _accounts = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadAccounts();
  }

  Future<void> _loadAccounts() async {
    setState(() => _loading = true);
    try {
      // TODO: Remplacer par l'ID de l'utilisateur connecté
      final accounts = await _db.getSavingsAccounts(1);
      setState(() {
        _accounts = accounts;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Erreur lors du chargement des comptes d\'épargne'),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_accounts.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text(
              'Aucun compte d\'épargne',
              style: TextStyle(fontSize: 18),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                // TODO: Ouvrir le formulaire d'ajout de compte d'épargne
              },
              child: const Text('Créer un compte d\'épargne'),
            ),
          ],
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Progression globale',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  height: 200,
                  child: PieChart(
                    PieChartData(
                      sections: _accounts
                          .map(
                            (account) => PieChartSectionData(
                              color: Colors.blue,
                              value: account.currentAmount,
                              title:
                                  '${(account.progress).toStringAsFixed(1)}%',
                              radius: 100,
                              titleStyle: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          )
                          .toList(),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        ...List.generate(
          _accounts.length,
          (index) {
            final account = _accounts[index];
            return Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                title: Text(account.name),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    LinearProgressIndicator(
                      value: account.progress / 100,
                      backgroundColor: Colors.grey[200],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${account.currentAmount.toStringAsFixed(2)} € / ${account.targetAmount?.toStringAsFixed(2) ?? "∞"} €',
                    ),
                    if (account.targetDate != null)
                      Text(
                        'Objectif : ${account.targetDate.toString().split(' ')[0]}',
                      ),
                  ],
                ),
                trailing: PopupMenuButton(
                  itemBuilder: (context) => [
                    const PopupMenuItem(
                      value: 'edit',
                      child: Text('Modifier'),
                    ),
                    const PopupMenuItem(
                      value: 'archive',
                      child: Text('Archiver'),
                    ),
                  ],
                  onSelected: (value) {
                    // TODO: Implémenter les actions
                  },
                ),
              ),
            );
          },
        ),
      ],
    );
  }
}
