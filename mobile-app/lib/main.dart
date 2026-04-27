import 'package:flutter/material.dart';

void main() {
  runApp(const CustomerApp());
}

class CustomerApp extends StatelessWidget {
  const CustomerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Customer App',
      theme: ThemeData(useMaterial3: true),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Customer App Starter')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: const [
          FeatureCard(title: 'Authentication', subtitle: 'OTP, registration, login'),
          FeatureCard(title: 'Catalog', subtitle: 'Products, variants, filters'),
          FeatureCard(title: 'Cart', subtitle: 'Session/local persistence'),
          FeatureCard(title: 'Orders', subtitle: 'History, reorder, tracking'),
          FeatureCard(title: 'Profile', subtitle: 'Address and account settings'),
        ],
      ),
    );
  }
}

class FeatureCard extends StatelessWidget {
  final String title;
  final String subtitle;

  const FeatureCard({super.key, required this.title, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(title: Text(title), subtitle: Text(subtitle)),
    );
  }
}
