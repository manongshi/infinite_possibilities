import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';

class CoverImage extends StatelessWidget {
  final String url;
  final int sourceId;
  final double? width;
  final double? height;

  const CoverImage({super.key, required this.url, required this.sourceId, this.width, this.height});

  @override
  Widget build(BuildContext context) {
    final placeholder = Container(
      width: width,
      height: height,
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: const Icon(Icons.image_outlined, color: Colors.grey),
    );
    if (url.isEmpty) return placeholder;
    return ClipRRect(
      borderRadius: BorderRadius.circular(6),
      child: CachedNetworkImage(
        imageUrl: Api.instance.imageUrl(url, sourceId: sourceId),
        width: width,
        height: height,
        fit: BoxFit.cover,
        placeholder: (_, _) => placeholder,
        errorWidget: (_, _, _) => placeholder,
      ),
    );
  }
}

class ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;

  const ErrorView({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.error_outline, size: 40, color: Colors.redAccent),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: 12),
              FilledButton.tonal(onPressed: onRetry, child: const Text('重试')),
            ],
          ]),
        ),
      );
}

/// 封面网格；滚到底部时调用 onLoadMore。
class BookGrid extends StatelessWidget {
  final List<BookItem> books;
  final int sourceId;
  final bool loadingMore;
  final VoidCallback? onLoadMore;
  final void Function(BookItem) onTap;

  const BookGrid({
    super.key,
    required this.books,
    required this.sourceId,
    required this.onTap,
    this.loadingMore = false,
    this.onLoadMore,
  });

  @override
  Widget build(BuildContext context) {
    return NotificationListener<ScrollNotification>(
      onNotification: (n) {
        if (onLoadMore != null && n.metrics.pixels > n.metrics.maxScrollExtent - 400) onLoadMore!();
        return false;
      },
      child: CustomScrollView(slivers: [
        SliverPadding(
          padding: const EdgeInsets.all(10),
          sliver: SliverGrid(
            gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
              maxCrossAxisExtent: 130,
              childAspectRatio: 0.52,
              crossAxisSpacing: 10,
              mainAxisSpacing: 10,
            ),
            delegate: SliverChildBuilderDelegate(
              (ctx, i) => BookCard(book: books[i], sourceId: sourceId, onTap: () => onTap(books[i])),
              childCount: books.length,
            ),
          ),
        ),
        if (loadingMore)
          const SliverToBoxAdapter(
            child: Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator())),
          ),
      ]),
    );
  }
}

class BookCard extends StatelessWidget {
  final BookItem book;
  final int sourceId;
  final VoidCallback onTap;

  const BookCard({super.key, required this.book, required this.sourceId, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        AspectRatio(aspectRatio: 0.72, child: CoverImage(url: book.coverUrl, sourceId: sourceId)),
        const SizedBox(height: 4),
        Text(book.name, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)),
        if (book.author.isNotEmpty || book.lastChapter.isNotEmpty)
          Text(
            book.lastChapter.isNotEmpty ? book.lastChapter : book.author,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 11, color: Theme.of(context).hintColor),
          ),
      ]),
    );
  }
}
