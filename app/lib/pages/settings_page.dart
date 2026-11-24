import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../store/settings.dart';

class SettingsPage extends StatefulWidget {
  final VoidCallback? onServerChanged;

  const SettingsPage({super.key, this.onServerChanged});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  late final _ctrl = TextEditingController(text: AppSettings.instance.serverUrl);
  String? _status;

  Future<void> _save() async {
    await AppSettings.instance.setServerUrl(_ctrl.text);
    setState(() => _status = '检测中…');
    try {
      await Api.instance.sources();
      setState(() => _status = '✅ 连接成功');
      widget.onServerChanged?.call();
    } catch (e) {
      setState(() => _status = '❌ $e');
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('设置')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(
          controller: _ctrl,
          keyboardType: TextInputType.url,
          decoration: const InputDecoration(
            labelText: '后端地址',
            helperText: '模拟器用 http://10.0.2.2:8090；真机填电脑的局域网 IP，如 http://192.168.1.10:8090',
            helperMaxLines: 2,
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton(onPressed: _save, child: const Text('保存并测试连接')),
        if (_status != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_status!)),
      ]),
    );
  }
}
