import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../store/settings.dart';
import '../widgets/common.dart';
import 'book_detail_page.dart';

/// 发现页：选书源 → 分类 Tab → 封面网格（分页加载）。
class ExplorePage extends StatefulWidget {
  const ExplorePage({super.key});

  @override
  State<ExplorePage> createState() => ExplorePageState();
}

class ExplorePageState extends State<ExplorePage> {
  List<BookSource> _sources = [];
  BookSource? _source;
  List<ExploreKind> _kinds = [];
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    reload();
  }

  Future<void> reload() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final list = (await Api.instance.sources(type: 'comic')).where((s) => s.enabled).toList();
      final saved = AppSettings.instance.exploreSourceId;
      final src = list.isEmpty ? null : list.firstWhere((s) => s.id == saved, orElse: () => list.first);
      final kinds = src == null ? <ExploreKind>[] : await Api.instance.exploreKinds(src.id);
      setState(() {
        _sources = list;
        _source = src;
        _kinds = kinds;
      });
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pickSource() async {
    final picked = await showModalBottomSheet<BookSource>(
      context: context,
      builder: (ctx) => ListView(
        shrinkWrap: true,
        children: _sources
            .map((s) => ListTile(
                  title: Text(s.name),
                  subtitle: Text(s.sourceUrl),
                  trailing: s.id == _source?.id ? const Icon(Icons.check) : null,
                  onTap: () => Navigator.pop(ctx, s),
                ))
            .toList(),
      ),
    );
    if (picked == null || picked.id == _source?.id) return;
    await AppSettings.instance.setExploreSourceId(picked.id);
    reload();
  }

  @override
  Widget build(BuildContext context) {
    final title = GestureDetector(
      onTap: _sources.length > 1 ? _pickSource : null,
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text(_source?.name ?? '发现'),
        if (_sources.length > 1) const Icon(Icons.arrow_drop_down),
      ]),
    );
    if (_loading) {
      return Scaffold(appBar: AppBar(title: title), body: const Center(child: CircularProgressIndicator()));
    }
    if (_error != null) {
      return Scaffold(appBar: AppBar(title: title), body: ErrorView(message: _error!, onRetry: reload));
    }
    if (_source == null) {
      return Scaffold(appBar: AppBar(title: title), body: const ErrorView(message: '没有可用的漫画书源，去「书源」页导入吧'));
    }
    if (_kinds.isEmpty) {
      return Scaffold(appBar: AppBar(title: title), body: const ErrorView(message: '这个书源没有配置发现页'));
    }
    return DefaultTabController(
      key: ValueKey(_source!.id),
      length: _kinds.length,
      child: Scaffold(
        appBar: AppBar(
          title: title,
          bottom: TabBar(isScrollable: true, tabAlignment: TabAlignment.start, tabs: [for (final k in _kinds) Tab(text: k.title)]),
        ),
        body: TabBarView(children: [for (final k in _kinds) _KindGrid(sourceId: _source!.id, kind: k)]),
      ),
    );
  }
}

class _KindGrid extends StatefulWidget {
  final int sourceId;
  final ExploreKind kind;

  const _KindGrid({required this.sourceId, required this.kind});

  @override
  State<_KindGrid> createState() => _KindGridState();
}

class _KindGridState extends State<_KindGrid> with AutomaticKeepAliveClientMixin {
  final List<BookItem> _books = [];
  int _page = 0;
  bool _hasMore = true;
  bool _loading = false;
  String? _error;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (_loading || !_hasMore) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final p = await Api.instance.exploreBooks(widget.sourceId, widget.kind.url, _page + 1);
      final seen = _books.map((b) => b.bookUrl).toSet();
      setState(() {
        _page++;
        _books.addAll(p.items.where((b) => !seen.contains(b.bookUrl)));
        _hasMore = p.hasMore;
      });
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _refresh() async {
    setState(() {
      _books.clear();
      _page = 0;
      _hasMore = true;
    });
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    if (_books.isEmpty && _loading) return const Center(child: CircularProgressIndicator());
    if (_books.isEmpty && _error != null) return ErrorView(message: _error!, onRetry: _refresh);
    if (_books.isEmpty) return ErrorView(message: '这里什么都没有', onRetry: _refresh);
    return RefreshIndicator(
      onRefresh: _refresh,
      child: BookGrid(
        books: _books,
        sourceId: widget.sourceId,
        loadingMore: _loading,
        onLoadMore: _error == null ? _load : null,
        onTap: (b) => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => BookDetailPage(sourceId: widget.sourceId, item: b)),
        ),
      ),
    );
  }
}
