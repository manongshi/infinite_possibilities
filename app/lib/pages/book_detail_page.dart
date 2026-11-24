import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../store/settings.dart';
import '../widgets/common.dart';
import 'reader_page.dart';

class BookDetailPage extends StatefulWidget {
  final int sourceId;
  final BookItem item;

  const BookDetailPage({super.key, required this.sourceId, required this.item});

  @override
  State<BookDetailPage> createState() => _BookDetailPageState();
}

class _BookDetailPageState extends State<BookDetailPage> {
  BookInfo? _info;
  List<Chapter> _chapters = [];
  String? _error;
  bool _loading = true;
  bool _desc = false;
  bool _introOpen = false;
  ReadProgress? _progress;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final info = await Api.instance.bookInfo(widget.sourceId, widget.item.bookUrl);
      final chs = await Api.instance.chapters(widget.sourceId, info.tocUrl);
      setState(() {
        _info = info;
        _chapters = chs;
        _progress = AppSettings.instance.progressOf(widget.sourceId, widget.item.bookUrl);
      });
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _open(int index, {int page = 0}) async {
    final info = _info!;
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ReaderPage(
          sourceId: widget.sourceId,
          bookUrl: widget.item.bookUrl,
          bookName: info.name.isNotEmpty ? info.name : widget.item.name,
          chapters: _chapters,
          startIndex: index,
          startPage: page,
        ),
      ),
    );
    setState(() => _progress = AppSettings.instance.progressOf(widget.sourceId, widget.item.bookUrl));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.item.name)),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? ErrorView(message: _error!, onRetry: _load)
              : _content(),
      bottomNavigationBar: _info == null || _chapters.isEmpty
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                child: FilledButton(
                  onPressed: () {
                    final p = _progress;
                    if (p != null && p.chapterIndex < _chapters.length) {
                      _open(p.chapterIndex, page: p.page);
                    } else {
                      _open(0);
                    }
                  },
                  child: Text(_progress == null ? '开始阅读' : '继续阅读 · ${_progress!.chapterTitle}'),
                ),
              ),
            ),
    );
  }

  Widget _content() {
    final info = _info!;
    final theme = Theme.of(context);
    final list = _desc ? _chapters.reversed.toList() : _chapters;
    return CustomScrollView(slivers: [
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            CoverImage(
              url: info.coverUrl.isNotEmpty ? info.coverUrl : widget.item.coverUrl,
              sourceId: widget.sourceId,
              width: 110,
              height: 150,
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(info.name.isNotEmpty ? info.name : widget.item.name, style: theme.textTheme.titleLarge),
                const SizedBox(height: 8),
                if (info.author.isNotEmpty) Text('作者：${info.author}'),
                if (info.kind.isNotEmpty) Text('类型：${info.kind}'),
                if (info.lastChapter.isNotEmpty) Text('最新：${info.lastChapter}'),
                Text('共 ${_chapters.length} 章', style: TextStyle(color: theme.hintColor)),
              ]),
            ),
          ]),
        ),
      ),
      if (info.intro.isNotEmpty)
        SliverToBoxAdapter(
          child: InkWell(
            onTap: () => setState(() => _introOpen = !_introOpen),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                info.intro,
                maxLines: _introOpen ? null : 3,
                overflow: _introOpen ? null : TextOverflow.ellipsis,
                style: TextStyle(color: theme.hintColor),
              ),
            ),
          ),
        ),
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 8, 4),
          child: Row(children: [
            Text('目录', style: theme.textTheme.titleMedium),
            const Spacer(),
            TextButton.icon(
              onPressed: () => setState(() => _desc = !_desc),
              icon: Icon(_desc ? Icons.arrow_downward : Icons.arrow_upward, size: 16),
              label: Text(_desc ? '倒序' : '正序'),
            ),
          ]),
        ),
      ),
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        sliver: SliverGrid(
          gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
            maxCrossAxisExtent: 120,
            mainAxisExtent: 40,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
          ),
          delegate: SliverChildBuilderDelegate((ctx, i) {
            final c = list[i];
            final current = _progress?.chapterIndex == c.index;
            return OutlinedButton(
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                foregroundColor: current ? theme.colorScheme.primary : null,
                side: current ? BorderSide(color: theme.colorScheme.primary) : null,
              ),
              onPressed: () => _open(c.index),
              child: Text(c.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12)),
            );
          }, childCount: list.length),
        ),
      ),
    ]);
  }
}
