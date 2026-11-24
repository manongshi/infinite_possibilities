import 'package:flutter_test/flutter_test.dart';
import 'package:infinite_reader/api/models.dart';

void main() {
  test('BookItem.fromJson', () {
    final b = BookItem.fromJson({'name': '鬼灭之刃', 'book_url': 'https://x/1/', 'cover_url': 'https://x/c.jpg'});
    expect(b.name, '鬼灭之刃');
    expect(b.author, '');
  });
}
