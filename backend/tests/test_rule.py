from app.engine.rule import Analyzer, split_header

HTML = """
<html><body>
<div class="main-bar"><h1>航海王学园</h1></div>
<ul id="detail">
  <li><a href="/comic/1/"><img data-src="//cf.x.com/1.jpg"/><h3><b>海贼</b>王</h3></a></li>
  <li><a href="/comic/2/"><img data-src="//cf.x.com/2.jpg"/><h3>CROWS</h3></a></li>
</ul>
<div class="chapter-list"><ul>
  <li><a href="/c/3.html"><b>第3话</b></a></li>
  <li><a href="/c/2.html"><b>第2话</b></a></li>
  <li><a href="/c/1.html"><b>第1话</b></a></li>
</ul></div>
<a href="/author/9/">作者甲</a>
</body></html>
"""


def an():
    return Analyzer(HTML, base_url="https://m.example.com/comic/1/")


def test_css_list_and_fields():
    a = an()
    items = a.get_elements("[id=detail] li")
    assert len(items) == 2
    assert a.get_string("h3@text", content=items[0]) == "海贼王"
    assert a.get_string("img@data-src", content=items[0], is_url=True) == "https://cf.x.com/1.jpg"
    assert a.get_string("a@href", content=items[1], is_url=True) == "https://m.example.com/comic/2/"


def test_reverse_and_single_attr():
    a = an()
    chs = a.get_elements("-.chapter-list li a")
    assert [a.get_string("b@text", content=c) for c in chs] == ["第1话", "第2话", "第3话"]
    assert a.get_string("href", content=chs[0], is_url=True) == "https://m.example.com/c/1.html"


def test_jsoup_default_syntax_and_index():
    a = an()
    assert a.get_string("class.main-bar@tag.h1@text") == "航海王学园"
    assert a.get_string("id.detail@tag.li.-1@tag.h3@text") == "CROWS"
    assert a.get_strings("class.chapter-list@tag.li!0@tag.b@text") == ["第2话", "第1话"]
    assert a.get_strings("class.chapter-list@tag.li[0:1]@tag.b@text") == ["第3话", "第2话"]
    assert a.get_string("a[href^='/author/']@text") == "作者甲"


def test_regex_replace_and_or():
    a = an()
    assert a.get_string(".main-bar h1@text##学园") == "航海王"
    assert a.get_string(".nope@text||.main-bar h1@text") == "航海王学园"


def test_js_and_header():
    rule, h = split_header('@js:result.length@Header:{"Referer":"https://x/"}')
    assert h == {"Referer": "https://x/"}
    a = Analyzer("abcd")
    assert a.get_value(rule) == 4
    assert a.get_value(".main-bar h1@text@js:result + '!'", content=HTML) == "航海王学园!"


def test_json():
    a = Analyzer('{"data":{"list":[{"name":"A","id":1},{"name":"B","id":2}]}}', base_url="https://a.com/")
    items = a.get_elements("$.data.list")
    assert len(items) == 2
    assert a.get_string("$.name", content=items[1]) == "B"
    assert a.get_string("/book/{{$.id}}.html", content=items[0], is_url=True) == "https://a.com/book/1.html"
