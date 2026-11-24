import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../widgets/common.dart';
import 'book_detail_page.dart';

/// 搜索：后端并发搜所有启用的漫画源，按书源分组展示。
class SearchPage extends StatefulWidget {
  const SearchPage({super.key});

  @override
  State<SearchPage> createState() => _SearchPageState();
}

class _SearchPageState extends State<SearchPage> {
  final _ctrl = TextEditingController();
  List<SearchGroup>? _groups;
  bool _loading = false;
  String? _error;

  Future<void> _search() async {
    final kw = _ctrl.text.trim();
    if (kw.isEmpty) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final g = await Api.instance.search(kw);
      setState(() => _groups = g);
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
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
      appBar: AppBar(
        title: TextField(
          controller: _ctrl,
          textInputAction: TextInputAction.search,
          onSubmitted: (_) => _search(),
          decoration: const InputDecoration(hintText: '搜索漫画', border: InputBorder.none),
        ),
        actions: [IconButton(onPressed: _search, icon: const Icon(Icons.search))],
      ),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return ErrorView(message: _error!, onRetry: _search);
    final groups = _groups;
    if (groups == null) return const Center(child: Text('输入关键词开始搜索'));
    final total = groups.fold<int>(0, (s, g) => s + g.items.length);
    if (total == 0) {
      final errs = groups.where((g) => g.error != null).map((g) => '${g.sourceName}: ${g.error}').join('\n');
      return ErrorView(message: errs.isEmpty ? '没有搜到结果' : errs);
    }
    return ListView(children: [
      for (final g in groups) ...[
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Text(
            '${g.sourceName}（${g.items.length}）${g.error != null ? '  出错：${g.error}' : ''}',
            style: Theme.of(context).textTheme.titleSmall,
          ),
        ),
        for (final b in g.items)
          ListTile(
            leading: SizedBox(width: 48, height: 64, child: CoverImage(url: b.coverUrl, sourceId: g.sourceId)),
            title: Text(b.name),
            subtitle: Text(
              [b.author, b.lastChapter].where((s) => s.isNotEmpty).join(' · '),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => BookDetailPage(sourceId: g.sourceId, item: b)),
            ),
          ),
      ],
    ]);
  }
}
