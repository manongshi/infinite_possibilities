import 'dart:convert';

import 'package:dio/dio.dart';

import '../store/settings.dart';
import 'models.dart';

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}

/// 后端 FastAPI 的薄封装。所有网络请求都走这里。
class Api {
  Api._();
  static final Api instance = Api._();

  final Dio _dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 60),
  ));

  String get base => AppSettings.instance.serverUrl;

  Future<dynamic> _get(String path, [Map<String, dynamic>? q]) async {
    try {
      final r = await _dio.get('$base$path', queryParameters: q);
      return r.data;
    } on DioException catch (e) {
      throw ApiException(_msg(e));
    }
  }

  Future<dynamic> _send(String method, String path, {Object? data}) async {
    try {
      final r = await _dio.request('$base$path', data: data, options: Options(method: method));
      return r.data;
    } on DioException catch (e) {
      throw ApiException(_msg(e));
    }
  }

  String _msg(DioException e) {
    final d = e.response?.data;
    if (d is Map && d['detail'] != null) return '${d['detail']}';
    if (e.type == DioExceptionType.connectionError || e.type == DioExceptionType.connectionTimeout) {
      return '连不上服务器 $base，请到「设置」检查地址';
    }
    return e.message ?? '网络错误';
  }

  /// 图片统一走后端代理，带上书源需要的 Referer/UA。
  String imageUrl(String url, {int? sourceId, Map<String, String>? headers}) {
    final q = <String, String>{'url': url};
    if (sourceId != null) q['source_id'] = '$sourceId';
    if (headers != null && headers.isNotEmpty) q['headers'] = jsonEncode(headers);
    return Uri.parse('$base/api/image').replace(queryParameters: q).toString();
  }

  // ---------------- 书源

  Future<List<BookSource>> sources({String? type}) async {
    final d = await _get('/api/sources', {'type': ?type});
    return (d as List).map((e) => BookSource.fromJson(e)).toList();
  }

  Future<String> importSources(String jsonText) async {
    final Object payload;
    try {
      payload = jsonDecode(jsonText);
    } catch (e) {
      throw ApiException('不是合法的 JSON');
    }
    return _importResult(await _send('POST', '/api/sources', data: payload));
  }

  Future<String> importSourcesFromUrl(String url) async =>
      _importResult(await _send('POST', '/api/sources/import-url', data: {'url': url}));

  String _importResult(dynamic d) {
    final errs = (d['errors'] as List).cast<String>();
    return '新增 ${d['created']}，更新 ${d['updated']}${errs.isEmpty ? '' : '，失败 ${errs.length}：${errs.join('；')}'}';
  }

  Future<void> setSourceEnabled(int id, bool enabled) =>
      _send('PATCH', '/api/sources/$id/enabled', data: {'enabled': enabled});

  Future<void> deleteSource(int id) => _send('DELETE', '/api/sources/$id');

  Future<String> sourceJson(int id) async {
    final d = await _get('/api/sources/$id/json');
    return const JsonEncoder.withIndent('  ').convert(d);
  }

  Future<void> updateSource(int id, String jsonText) async {
    final Object payload;
    try {
      payload = jsonDecode(jsonText);
    } catch (e) {
      throw ApiException('不是合法的 JSON');
    }
    await _send('PUT', '/api/sources/$id', data: payload);
  }

  // ---------------- 漫画

  Future<List<ExploreKind>> exploreKinds(int sourceId) async {
    final d = await _get('/api/sources/$sourceId/explore');
    return (d as List).map((e) => ExploreKind.fromJson(e)).toList();
  }

  Future<BookPage> exploreBooks(int sourceId, String url, int page) async {
    final d = await _get('/api/sources/$sourceId/explore/books', {'url': url, 'page': page});
    return BookPage((d['items'] as List).map((e) => BookItem.fromJson(e)).toList(), d['has_more'] == true);
  }

  Future<List<SearchGroup>> search(String keyword, {int? sourceId}) async {
    final d = await _get('/api/search', {'keyword': keyword, 'type': 'comic', 'source_id': ?sourceId});
    return (d['results'] as List).map((e) => SearchGroup.fromJson(e)).toList();
  }

  Future<BookInfo> bookInfo(int sourceId, String url) async =>
      BookInfo.fromJson(await _get('/api/sources/$sourceId/book', {'url': url}));

  Future<List<Chapter>> chapters(int sourceId, String tocUrl) async {
    final d = await _get('/api/sources/$sourceId/chapters', {'url': tocUrl});
    return (d as List).map((e) => Chapter.fromJson(e)).toList();
  }

  Future<ChapterContent> content(int sourceId, String url, {String nextUrl = ''}) async =>
      ChapterContent.fromJson(await _get('/api/sources/$sourceId/content', {'url': url, 'next_url': nextUrl}));
}
