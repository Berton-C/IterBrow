// Runs under plain node: node tests/node/markdown_test.js
const assert = require('assert');
const md = require('../../renderer/markdown.js');
const r = (s) => md.render(s);

// escaping: nothing from the input becomes markup by accident
assert.strictEqual(r('<script>alert(1)</script>'), '<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>');
assert.strictEqual(r('a & b < c'), '<p>a &amp; b &lt; c</p>');
assert.ok(!r('<img src=x onerror=alert(1)>').includes('<img'));

// inline
assert.strictEqual(r('**bold** and *it* and ~~gone~~ and `x<y`'),
  '<p><strong>bold</strong> and <em>it</em> and <del>gone</del> and <code>x&lt;y</code></p>');
assert.strictEqual(r('snake_case_word stays'), '<p>snake_case_word stays</p>');
assert.strictEqual(r('__strong__ _em_'), '<p><strong>strong</strong> <em>em</em></p>');
assert.strictEqual(r('`**not bold**`'), '<p><code>**not bold**</code></p>');

// links: only http(s)/mailto survive as hrefs; others become plain text
assert.strictEqual(r('[site](https://example.com/a?b=1)'),
  '<p><a href="https://example.com/a?b=1" rel="noopener noreferrer">site</a></p>');
assert.strictEqual(r('[x](javascript:alert(1))'), '<p>x (javascript:alert(1))</p>');
assert.strictEqual(r('[x](data:text/html,hi)'), '<p>x (data:text/html,hi)</p>');
assert.ok(!r('[x](https://e.com" onclick="alert(1))').includes('onclick="'));
assert.strictEqual(r('see https://example.com/path, ok'),
  '<p>see <a href="https://example.com/path" rel="noopener noreferrer">https://example.com/path</a>, ok</p>');
assert.strictEqual(r('mail [me](mailto:a@b.co)'), '<p>mail <a href="mailto:a@b.co" rel="noopener noreferrer">me</a></p>');

// line breaks inside a paragraph (Mattermost-style hard breaks), paragraphs on blank lines
assert.strictEqual(r('one\ntwo\n\nthree'), '<p>one<br>two</p>\n<p>three</p>');

// headings, rule, quote
assert.strictEqual(r('# Title\n## Sub'), '<h1>Title</h1>\n<h2>Sub</h2>');
assert.strictEqual(r('---'), '<hr>');
assert.strictEqual(r('> quoted\n> **line**'), '<blockquote><p>quoted<br><strong>line</strong></p></blockquote>');

// lists, nesting, numbering, continuation lines
assert.strictEqual(r('- a\n- b\n  - c\n- d'), '<ul><li>a</li><li>b<ul><li>c</li></ul></li><li>d</li></ul>');
assert.strictEqual(r('3. x\n4. y'), '<ol start="3"><li>x</li><li>y</li></ol>');
assert.strictEqual(r('1. first\n   continued'), '<ol><li>first<br>continued</li></ol>');
assert.strictEqual(r('- a\n\ntext'), '<ul><li>a</li></ul>\n<p>text</p>');

// fenced code keeps everything literal, including markdown and html
assert.strictEqual(r('```js\nconst a = "<b>";\n**x**\n```'),
  '<pre><code class="lang-js">const a = &quot;&lt;b&gt;&quot;;\n**x**</code></pre>');
assert.strictEqual(r('```\nunterminated'), '<pre><code>unterminated</code></pre>');
assert.ok(!r('```x" onload="y\ncode\n```').includes('onload="'));

// tables
assert.strictEqual(r('| a | b |\n|---|---|\n| 1 | **2** |'),
  '<table><thead><tr><th>a</th><th>b</th></tr></thead><tbody><tr><td>1</td><td><strong>2</strong></td></tr></tbody></table>');

// plain text passes through unchanged apart from the paragraph
assert.strictEqual(r('Hello, world.'), '<p>Hello, world.</p>');
assert.strictEqual(r(''), '');
assert.strictEqual(r(null), '');

// degenerate input must not hang (no catastrophic backtracking)
const t0 = Date.now();
r('*'.repeat(5000) + '_'.repeat(5000) + '`'.repeat(3000) + '[' .repeat(2000));
assert.ok(Date.now() - t0 < 2000, 'renderer too slow on hostile input');

console.log('markdown: all assertions passed');
