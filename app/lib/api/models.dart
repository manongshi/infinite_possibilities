// 与后端 /api 返回结构一一对应的数据模型。

class BookSource {
  final int id;
  final String sourceUrl;
  final String name;
  final String groupName;
  final String sourceType;
  final String format;
  final bool enabled;
  final String remark;

  BookSource({
    required this.id,
    required this.sourceUrl,
    required this.name,
    required this.groupName,
    required this.sourceType,
    required this.format,
    required this.enabled,
    required this.remark,
  });

  factory BookSource.fromJson(Map<String, dynamic> j) => BookSource(
        id: j['id'] as int,
        sourceUrl: j['source_url'] ?? '',
        name: j['name'] ?? '',
        groupName: j['group_name'] ?? '',
        sourceType: j['source_type'] ?? '',
        format: j['format'] ?? '',
        enabled: j['enabled'] ?? true,
        remark: j['remark'] ?? '',
      );
}

class ExploreKind {
  final String title;
  final String url;
  final String group;

  ExploreKind({required this.title, required this.url, required this.group});

  factory ExploreKind.fromJson(Map<String, dynamic> j) =>
      ExploreKind(title: j['title'] ?? '', url: j['url'] ?? '', group: j['group'] ?? '');
}

class BookItem {
  final String name;
  final String bookUrl;
  final String author;
  final String coverUrl;
  final String kind;
  final String intro;
  final String lastChapter;

  BookItem({
    required this.name,
    required this.bookUrl,
    this.author = '',
    this.coverUrl = '',
    this.kind = '',
    this.intro = '',
    this.lastChapter = '',
  });

  factory BookItem.fromJson(Map<String, dynamic> j) => BookItem(
        name: j['name'] ?? '',
        bookUrl: j['book_url'] ?? '',
        author: j['author'] ?? '',
        coverUrl: j['cover_url'] ?? '',
        kind: j['kind'] ?? '',
        intro: j['intro'] ?? '',
        lastChapter: j['last_chapter'] ?? '',
      );
}

class BookPage {
  final List<BookItem> items;
  final bool hasMore;

  BookPage(this.items, this.hasMore);
}

class SearchGroup {
  final int sourceId;
  final String sourceName;
  final List<BookItem> items;
  final String? error;

  SearchGroup({required this.sourceId, required this.sourceName, required this.items, this.error});

  factory SearchGroup.fromJson(Map<String, dynamic> j) => SearchGroup(
        sourceId: j['source_id'] as int,
        sourceName: j['source_name'] ?? '',
        items: (j['items'] as List).map((e) => BookItem.fromJson(e)).toList(),
        error: j['error'] as String?,
      );
}

class BookInfo {
  final String name;
  final String bookUrl;
  final String tocUrl;
  final String author;
  final String coverUrl;
  final String kind;
  final String intro;
  final String lastChapter;
  final String updateTime;

  BookInfo({
    required this.name,
    required this.bookUrl,
    required this.tocUrl,
    this.author = '',
    this.coverUrl = '',
    this.kind = '',
    this.intro = '',
    this.lastChapter = '',
    this.updateTime = '',
  });

  factory BookInfo.fromJson(Map<String, dynamic> j) => BookInfo(
        name: j['name'] ?? '',
        bookUrl: j['book_url'] ?? '',
        tocUrl: j['toc_url'] ?? '',
        author: j['author'] ?? '',
        coverUrl: j['cover_url'] ?? '',
        kind: j['kind'] ?? '',
        intro: j['intro'] ?? '',
        lastChapter: j['last_chapter'] ?? '',
        updateTime: j['update_time'] ?? '',
      );
}

class Chapter {
  final int index;
  final String title;
  final String url;

  Chapter({required this.index, required this.title, required this.url});

  factory Chapter.fromJson(Map<String, dynamic> j) =>
      Chapter(index: j['index'] as int, title: j['title'] ?? '', url: j['url'] ?? '');
}

class ImageRef {
  final String url;
  final Map<String, String> headers;

  ImageRef({required this.url, required this.headers});

  factory ImageRef.fromJson(Map<String, dynamic> j) => ImageRef(
        url: j['url'] ?? '',
        headers: (j['headers'] as Map? ?? {}).map((k, v) => MapEntry('$k', '$v')),
      );
}

class ChapterContent {
  final List<ImageRef> images;
  final String text;

  ChapterContent({required this.images, required this.text});

  factory ChapterContent.fromJson(Map<String, dynamic> j) => ChapterContent(
        images: (j['images'] as List).map((e) => ImageRef.fromJson(e)).toList(),
        text: j['text'] ?? '',
      );
}
