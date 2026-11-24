import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart' show ScrollCacheExtent;
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../store/settings.dart';
import '../widgets/common.dart';

enum ReadMode { pageLtr, pageRtl, scroll }

extension on ReadMode {
  String get label => switch (this) {
        ReadMode.pageLtr => '翻页（左→右）',
        ReadMode.pageRtl => '翻页（右→左，日漫）',
        ReadMode.scroll => '条漫（上下滚动）',
      };
}

/// 漫画阅读器：支持翻页 / 条漫两种模式，点击中间呼出菜单，自动记录进度。
class ReaderPage extends StatefulWidget {
  final int sourceId;
  final String bookUrl;
  final String bookName;
  final List<Chapter> chapters;
  final int startIndex;
  final int startPage;

  const ReaderPage({
    super.key,
    required this.sourceId,
    required this.bookUrl,
    required this.bookName,
    required this.chapters,
    required this.startIndex,
    this.startPage = 0,
  });

  @override
  State<ReaderPage> createState() => _ReaderPageState();
}

class _ReaderPageState extends State<ReaderPage> {
  late int _index = widget.startIndex;
  List<ImageRef> _images = [];
  bool _loading = true;
  String? _error;
  bool _showUi = false;
  int _page = 0;
  ReadMode _mode = ReadMode.pageLtr;
  PageController? _pageCtrl;
  final ScrollController _scrollCtrl = ScrollController();

  Chapter get _chapter => widget.chapters[_index];

  @override
  void initState() {
    super.initState();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    SharedPreferences.getInstance().then((p) {
      final m = p.getInt('read_mode');
      if (m != null && m < ReadMode.values.length) setState(() => _mode = ReadMode.values[m]);
    });
    _scrollCtrl.addListener(_onScroll);
    _loadChapter(_index, page: widget.startPage);
  }

  @override
  void dispose() {
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    _pageCtrl?.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadChapter(int index, {int page = 0}) async {
    setState(() {
      _index = index;
      _loading = true;
      _error = null;
      _images = [];
    });
    try {
      final next = index + 1 < widget.chapters.length ? widget.chapters[index + 1].url : '';
      final c = await Api.instance.content(widget.sourceId, widget.chapters[index].url, nextUrl: next);
      if (!mounted || _index != index) return;
      final start = page.clamp(0, c.images.isEmpty ? 0 : c.images.length - 1);
      _pageCtrl?.dispose();
      _pageCtrl = PageController(initialPage: start);
      setState(() {
        _images = c.images;
        _page = start;
        if (c.images.isEmpty) _error = c.text.isNotEmpty ? '本章没有图片（返回的是文字内容）' : '本章没有解析到图片';
      });
      if (_scrollCtrl.hasClients) _scrollCtrl.jumpTo(0);
      _saveProgress();
      _precache(start);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _img(int i) => Api.instance.imageUrl(_images[i].url, sourceId: widget.sourceId, headers: _images[i].headers);

  void _precache(int from) {
    for (var i = from + 1; i <= from + 3 && i < _images.length; i++) {
      precacheImage(CachedNetworkImageProvider(_img(i)), context);
    }
  }

  void _saveProgress() {
    AppSettings.instance.saveProgress(
      widget.sourceId,
      widget.bookUrl,
      ReadProgress(chapterIndex: _index, chapterTitle: _chapter.title, page: _page),
    );
  }

  void _onPageChanged(int p) {
    if (p >= _images.length) return; // 章末页
    setState(() => _page = p);
    _saveProgress();
    _precache(p);
  }

  void _onScroll() {
    if (_mode != ReadMode.scroll || _images.isEmpty || !_scrollCtrl.hasClients) return;
    final m = _scrollCtrl.position;
    if (m.maxScrollExtent <= 0) return;
    final p = ((m.pixels / m.maxScrollExtent) * (_images.length - 1)).round().clamp(0, _images.length - 1);
    if (p != _page) {
      _page = p;
      _saveProgress();
      setState(() {});
    }
  }

  void _prevChapter() {
    if (_index > 0) _loadChapter(_index - 1);
  }

  void _nextChapter() {
    if (_index + 1 < widget.chapters.length) {
      _loadChapter(_index + 1);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已经是最后一章了')));
    }
  }

  void _turn(int delta) {
    final ctrl = _pageCtrl;
    if (ctrl == null || !ctrl.hasClients) return;
    final target = _page + delta;
    if (target < 0) {
      _prevChapter();
    } else if (target > _images.length) {
      _nextChapter();
    } else {
      ctrl.animateToPage(target, duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
    }
  }

  void _onTapUp(TapUpDetails d) {
    final w = MediaQuery.of(context).size.width;
    final x = d.globalPosition.dx;
    if (_mode == ReadMode.scroll || (x > w / 3 && x < w * 2 / 3)) {
      setState(() => _showUi = !_showUi);
      return;
    }
    final leftSide = x <= w / 3;
    // 右→左模式下左侧是下一页
    final forward = _mode == ReadMode.pageRtl ? leftSide : !leftSide;
    _turn(forward ? 1 : -1);
  }

  Future<void> _chooseMode() async {
    final m = await showModalBottomSheet<ReadMode>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          for (final m in ReadMode.values)
            ListTile(
              title: Text(m.label),
              trailing: m == _mode ? const Icon(Icons.check) : null,
              onTap: () => Navigator.pop(ctx, m),
            ),
        ]),
      ),
    );
    if (m == null || m == _mode) return;
    (await SharedPreferences.getInstance()).setInt('read_mode', m.index);
    _pageCtrl?.dispose();
    _pageCtrl = PageController(initialPage: _page);
    setState(() => _mode = m);
  }

  Future<void> _chooseChapter() async {
    final i = await showModalBottomSheet<int>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => SizedBox(
        height: MediaQuery.of(ctx).size.height * 0.7,
        child: ListView.builder(
          controller: ScrollController(initialScrollOffset: (_index * 48.0 - 200).clamp(0, double.infinity)),
          itemExtent: 48,
          itemCount: widget.chapters.length,
          itemBuilder: (_, i) => ListTile(
            title: Text(widget.chapters[i].title, maxLines: 1),
            selected: i == _index,
            onTap: () => Navigator.pop(ctx, i),
          ),
        ),
      ),
    );
    if (i != null && i != _index) _loadChapter(i);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(children: [
        Positioned.fill(child: GestureDetector(onTapUp: _onTapUp, child: _reader())),
        if (_showUi) _topBar(),
        if (_showUi) _bottomBar(),
        if (!_showUi && _images.isNotEmpty)
          Positioned(
            right: 8,
            bottom: 8,
            child: Text(
              '${_chapter.title}  ${_page + 1}/${_images.length}',
              style: const TextStyle(color: Colors.white70, fontSize: 11, shadows: [Shadow(blurRadius: 2)]),
            ),
          ),
      ]),
    );
  }

  Widget _reader() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Theme(
        data: ThemeData.dark(),
        child: ErrorView(message: '${_chapter.title}\n$_error', onRetry: () => _loadChapter(_index, page: _page)),
      );
    }
    if (_mode == ReadMode.scroll) {
      return ListView.builder(
        controller: _scrollCtrl,
        itemCount: _images.length + 1,
        scrollCacheExtent: const ScrollCacheExtent.pixels(2000),
        itemBuilder: (ctx, i) => i == _images.length ? _chapterEnd() : _image(i, BoxFit.fitWidth),
      );
    }
    return PageView.builder(
      controller: _pageCtrl,
      reverse: _mode == ReadMode.pageRtl,
      itemCount: _images.length + 1,
      onPageChanged: _onPageChanged,
      itemBuilder: (ctx, i) => i == _images.length
          ? _chapterEnd()
          : InteractiveViewer(maxScale: 4, child: Center(child: _image(i, BoxFit.contain))),
    );
  }

  Widget _image(int i, BoxFit fit) {
    final w = MediaQuery.of(context).size.width;
    return CachedNetworkImage(
      imageUrl: _img(i),
      fit: fit,
      width: w,
      placeholder: (_, _) => SizedBox(
        height: w * 1.4,
        child: Center(child: Text('${i + 1}', style: const TextStyle(color: Colors.white38, fontSize: 28))),
      ),
      errorWidget: (_, _, _) => SizedBox(
        height: w * 1.4,
        child: const Center(child: Icon(Icons.broken_image_outlined, color: Colors.white38, size: 40)),
      ),
    );
  }

  Widget _chapterEnd() {
    final hasNext = _index + 1 < widget.chapters.length;
    return SizedBox(
      height: 320,
      child: Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text('${_chapter.title} 完', style: const TextStyle(color: Colors.white70)),
          const SizedBox(height: 16),
          if (hasNext)
            FilledButton(onPressed: _nextChapter, child: Text('下一章：${widget.chapters[_index + 1].title}'))
          else
            const Text('已经是最后一章了', style: TextStyle(color: Colors.white38)),
        ]),
      ),
    );
  }

  Widget _topBar() => Positioned(
        top: 0,
        left: 0,
        right: 0,
        child: Material(
          color: Colors.black87,
          child: SafeArea(
            bottom: false,
            child: ListTile(
              leading: IconButton(
                icon: const Icon(Icons.arrow_back, color: Colors.white),
                onPressed: () => Navigator.pop(context),
              ),
              title: Text(widget.bookName, style: const TextStyle(color: Colors.white), maxLines: 1),
              subtitle: Text(_chapter.title, style: const TextStyle(color: Colors.white70), maxLines: 1),
            ),
          ),
        ),
      );

  Widget _bottomBar() => Positioned(
        left: 0,
        right: 0,
        bottom: 0,
        child: Material(
          color: Colors.black87,
          child: SafeArea(
            top: false,
            child: Theme(
              data: ThemeData.dark(),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                if (_images.length > 1 && _mode != ReadMode.scroll)
                  Slider(
                    value: _page.toDouble().clamp(0, (_images.length - 1).toDouble()),
                    max: (_images.length - 1).toDouble(),
                    divisions: _images.length - 1,
                    label: '${_page + 1}',
                    onChanged: (v) => _pageCtrl?.jumpToPage(v.round()),
                  ),
                Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: [
                  TextButton.icon(onPressed: _index > 0 ? _prevChapter : null, icon: const Icon(Icons.skip_previous), label: const Text('上一章')),
                  IconButton(onPressed: _chooseChapter, icon: const Icon(Icons.list), tooltip: '目录'),
                  IconButton(onPressed: _chooseMode, icon: const Icon(Icons.chrome_reader_mode_outlined), tooltip: '阅读模式'),
                  TextButton.icon(
                    onPressed: _index + 1 < widget.chapters.length ? _nextChapter : null,
                    icon: const Icon(Icons.skip_next),
                    label: const Text('下一章'),
                  ),
                ]),
              ]),
            ),
          ),
        ),
      );
}
