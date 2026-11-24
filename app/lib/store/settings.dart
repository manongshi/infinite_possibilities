import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 本地设置 + 阅读进度（都存 SharedPreferences，以后有书架表了再迁到后端）。
class AppSettings extends ChangeNotifier {
  AppSettings._(this._prefs);

  static late AppSettings instance;

  // Android 模拟器访问宿主机用 10.0.2.2；真机改成电脑的局域网 IP
  static const defaultServer = 'http://10.0.2.2:8090';

  final SharedPreferences _prefs;

  static Future<void> init() async {
    instance = AppSettings._(await SharedPreferences.getInstance());
  }

  String get serverUrl => _prefs.getString('server_url') ?? defaultServer;

  Future<void> setServerUrl(String v) async {
    var s = v.trim();
    while (s.endsWith('/')) {
      s = s.substring(0, s.length - 1);
    }
    await _prefs.setString('server_url', s);
    notifyListeners();
  }

  int? get exploreSourceId => _prefs.getInt('explore_source_id');

  Future<void> setExploreSourceId(int id) => _prefs.setInt('explore_source_id', id);

  /// 阅读进度：key = sourceId|bookUrl
  ReadProgress? progressOf(int sourceId, String bookUrl) {
    final raw = _prefs.getString('progress:$sourceId|$bookUrl');
    if (raw == null) return null;
    return ReadProgress.fromJson(jsonDecode(raw));
  }

  Future<void> saveProgress(int sourceId, String bookUrl, ReadProgress p) =>
      _prefs.setString('progress:$sourceId|$bookUrl', jsonEncode(p.toJson()));
}

class ReadProgress {
  final int chapterIndex;
  final String chapterTitle;
  final int page;

  ReadProgress({required this.chapterIndex, required this.chapterTitle, required this.page});

  factory ReadProgress.fromJson(Map<String, dynamic> j) => ReadProgress(
        chapterIndex: j['c'] ?? 0,
        chapterTitle: j['t'] ?? '',
        page: j['p'] ?? 0,
      );

  Map<String, dynamic> toJson() => {'c': chapterIndex, 't': chapterTitle, 'p': page};
}
