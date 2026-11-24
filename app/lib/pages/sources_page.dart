import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../widgets/common.dart';

/// 书源管理：列表、启停、查看/编辑 JSON、删除、导入（粘贴 JSON 或网络地址）。
class SourcesPage extends StatefulWidget {
  final VoidCallback? onChanged;

  const SourcesPage({super.key, this.onChanged});

  @override
  State<SourcesPage> createState() => _SourcesPageState();
}

class _SourcesPageState extends State<SourcesPage> {
  List<BookSource>? _sources;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final s = await Api.instance.sources();
      setState(() {
        _sources = s;
        _error = null;
      });
    } catch (e) {
      setState(() => _error = '$e');
    }
  }

  void _toast(String msg) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  Future<void> _run(Future<void> Function() fn, {String? ok}) async {
    try {
      await fn();
      if (ok != null) _toast(ok);
      await _load();
      widget.onChanged?.call();
    } catch (e) {
      _toast('$e');
    }
  }

  Future<void> _import() async {
    final ctrl = TextEditingController();
    final text = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('导入书源'),
        content: TextField(
          controller: ctrl,
          maxLines: 10,
          minLines: 4,
          decoration: const InputDecoration(
            hintText: '粘贴书源 JSON（单个对象或数组），或者一个 http(s) 书源地址',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () async {
              final d = await Clipboard.getData(Clipboard.kTextPlain);
              if (d?.text != null) ctrl.text = d!.text!;
            },
            child: const Text('从剪贴板粘贴'),
          ),
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          FilledButton(onPressed: () => Navigator.pop(ctx, ctrl.text), child: const Text('导入')),
        ],
      ),
    );
    final t = text?.trim() ?? '';
    if (t.isEmpty) return;
    try {
      final msg = t.startsWith('http')
          ? await Api.instance.importSourcesFromUrl(t)
          : await Api.instance.importSources(t);
      _toast(msg);
      await _load();
      widget.onChanged?.call();
    } catch (e) {
      _toast('$e');
    }
  }

  Future<void> _edit(BookSource s) async {
    final String json;
    try {
      json = await Api.instance.sourceJson(s.id);
    } catch (e) {
      _toast('$e');
      return;
    }
    if (!mounted) return;
    final ctrl = TextEditingController(text: json);
    final saved = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (ctx) => Scaffold(
          appBar: AppBar(title: Text(s.name), actions: [
            IconButton(
              icon: const Icon(Icons.copy),
              tooltip: '复制',
              onPressed: () => Clipboard.setData(ClipboardData(text: ctrl.text)),
            ),
            IconButton(
              icon: const Icon(Icons.save),
              tooltip: '保存',
              onPressed: () async {
                try {
                  await Api.instance.updateSource(s.id, ctrl.text);
                  if (ctx.mounted) Navigator.pop(ctx, true);
                } catch (e) {
                  if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('$e')));
                }
              },
            ),
          ]),
          body: Padding(
            padding: const EdgeInsets.all(8),
            child: TextField(
              controller: ctrl,
              maxLines: null,
              expands: true,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
              decoration: const InputDecoration(border: InputBorder.none),
            ),
          ),
        ),
      ),
    );
    if (saved == true) {
      _toast('已保存');
      await _load();
      widget.onChanged?.call();
    }
  }

  Future<void> _delete(BookSource s) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除书源'),
        content: Text('确定删除「${s.name}」？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('删除')),
        ],
      ),
    );
    if (ok == true) _run(() => Api.instance.deleteSource(s.id), ok: '已删除');
  }

  static const _typeLabel = {'comic': '漫画', 'text': '小说', 'audio': '音频', 'file': '文件'};

  @override
  Widget build(BuildContext context) {
    final list = _sources;
    return Scaffold(
      appBar: AppBar(title: const Text('书源'), actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh))]),
      floatingActionButton: FloatingActionButton(onPressed: _import, child: const Icon(Icons.add)),
      body: _error != null
          ? ErrorView(message: _error!, onRetry: _load)
          : list == null
              ? const Center(child: CircularProgressIndicator())
              : list.isEmpty
                  ? const Center(child: Text('还没有书源，点右下角导入'))
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.separated(
                        itemCount: list.length,
                        separatorBuilder: (_, _) => const Divider(height: 1),
                        itemBuilder: (ctx, i) {
                          final s = list[i];
                          return ListTile(
                            title: Text(s.name),
                            subtitle: Text(
                              '${_typeLabel[s.sourceType] ?? s.sourceType} · ${s.format == 'legacy' ? '旧版格式' : 'Legado'}'
                              '${s.groupName.isNotEmpty ? ' · ${s.groupName}' : ''}\n${s.sourceUrl}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            isThreeLine: true,
                            onTap: () => _edit(s),
                            onLongPress: () => _delete(s),
                            trailing: Switch(
                              value: s.enabled,
                              onChanged: (v) => _run(() => Api.instance.setSourceEnabled(s.id, v)),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
