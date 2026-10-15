// Small, dependency-free Markdown renderer for the chat panel.
//
// Mattermost-style subset: headings, paragraphs with hard line breaks, bold,
// italic, strikethrough, inline code, fenced code blocks, links, bare URLs,
// block quotes, bullet and numbered lists, tables and horizontal rules.
//
// Every character that is not markup is HTML-escaped before it reaches the
// output, and a link's destination is kept only if it is http(s) or mailto.
// Chat content comes from the agent and from other people's messages, so the
// renderer never trusts its input.
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.IterMarkdown = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  function safeHref(raw) {
    const url = String(raw || '').trim().replace(/[\u0000-\u001f\u007f]/g, '');
    if (/^https?:\/\/[^\s]+$/i.test(url) || /^mailto:[^\s]+$/i.test(url)) return url;
    return null;
  }

  // -- inline ---------------------------------------------------------------

  // Protect code spans first so no other inline rule sees their contents.
  function renderInline(text) {
    const codeSpans = [];
    let withCodeHidden = text.replace(/(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)/g, (_m, _ticks, code) => {
      codeSpans.push('<code>' + escapeHtml(code.trim()) + '</code>');
      return '\u0000' + (codeSpans.length - 1) + '\u0000';
    });

    const links = [];
    // [text](url)
    withCodeHidden = withCodeHidden.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, (_m, label, href) => {
      const safe = safeHref(href);
      const inner = renderInlineNoLinks(label);
      links.push(safe
        ? '<a href="' + escapeHtml(safe) + '" rel="noopener noreferrer">' + inner + '</a>'
        : inner + ' (' + escapeHtml(href) + ')');
      return '\u0001' + (links.length - 1) + '\u0001';
    });
    // bare URLs
    withCodeHidden = withCodeHidden.replace(/(^|[\s(])((?:https?:\/\/)[^\s<>()]+[^\s<>().,;:!?'"])/g, (_m, lead, url) => {
      links.push('<a href="' + escapeHtml(url) + '" rel="noopener noreferrer">' + escapeHtml(url) + '</a>');
      return lead + '\u0001' + (links.length - 1) + '\u0001';
    });

    let html = renderInlineNoLinks(withCodeHidden);
    html = html.replace(/\u0001(\d+)\u0001/g, (_m, i) => links[Number(i)]);
    html = html.replace(/\u0000(\d+)\u0000/g, (_m, i) => codeSpans[Number(i)]);
    return html;
  }

  function renderInlineNoLinks(text) {
    let html = escapeHtml(text);
    // Placeholders survive escaping because \u0000/\u0001 are not escaped.
    html = html.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/(^|[^\w])__([^_\n]+?)__(?!\w)/g, '$1<strong>$2</strong>');
    html = html.replace(/(^|[^*\w])\*([^*\n]+?)\*(?!\w)/g, '$1<em>$2</em>');
    html = html.replace(/(^|[^\w])_([^_\n]+?)_(?!\w)/g, '$1<em>$2</em>');
    html = html.replace(/~~([^~\n]+?)~~/g, '<del>$1</del>');
    return html;
  }

  // -- blocks ---------------------------------------------------------------

  const FENCE = /^\s{0,3}(```|~~~)\s*([\w+-]*)\s*$/;
  const HEADING = /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/;
  const HR = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/;
  const QUOTE = /^\s{0,3}>\s?(.*)$/;
  const BULLET = /^(\s*)[-*+]\s+(.*)$/;
  const NUMBERED = /^(\s*)(\d{1,9})[.)]\s+(.*)$/;
  const TABLE_ROW = /^\s*\|.*\|\s*$/;
  const TABLE_SEP = /^\s*\|?(\s*:?-{1,}:?\s*\|)+\s*:?-{1,}:?\s*\|?\s*$/;

  function splitRow(line) {
    const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '');
    return trimmed.split(/(?<!\\)\|/).map((cell) => cell.replace(/\\\|/g, '|').trim());
  }

  function render(source) {
    const lines = String(source == null ? '' : source).replace(/\r\n?/g, '\n').split('\n');
    const out = [];
    let i = 0;

    function paragraph(buffer) {
      if (!buffer.length) return;
      out.push('<p>' + buffer.map(renderInline).join('<br>') + '</p>');
      buffer.length = 0;
    }

    const para = [];
    while (i < lines.length) {
      const line = lines[i];

      const fence = line.match(FENCE);
      if (fence) {
        paragraph(para);
        const marker = fence[1];
        const language = fence[2];
        const code = [];
        i += 1;
        while (i < lines.length && !(lines[i].trim() === marker)) { code.push(lines[i]); i += 1; }
        i += 1; // closing fence (or end of input)
        out.push('<pre><code' + (language ? ' class="lang-' + escapeHtml(language) + '"' : '') + '>'
          + escapeHtml(code.join('\n')) + '</code></pre>');
        continue;
      }

      if (!line.trim()) { paragraph(para); i += 1; continue; }

      const heading = line.match(HEADING);
      if (heading) {
        paragraph(para);
        const level = heading[1].length;
        out.push('<h' + level + '>' + renderInline(heading[2]) + '</h' + level + '>');
        i += 1; continue;
      }

      if (HR.test(line)) { paragraph(para); out.push('<hr>'); i += 1; continue; }

      if (QUOTE.test(line)) {
        paragraph(para);
        const inner = [];
        while (i < lines.length && QUOTE.test(lines[i])) { inner.push(lines[i].match(QUOTE)[1]); i += 1; }
        out.push('<blockquote>' + render(inner.join('\n')) + '</blockquote>');
        continue;
      }

      if (BULLET.test(line) || NUMBERED.test(line)) {
        paragraph(para);
        i = renderList(lines, i, out);
        continue;
      }

      if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_SEP.test(lines[i + 1])) {
        paragraph(para);
        const header = splitRow(line);
        i += 2;
        const rows = [];
        while (i < lines.length && TABLE_ROW.test(lines[i])) { rows.push(splitRow(lines[i])); i += 1; }
        out.push('<table><thead><tr>' + header.map((c) => '<th>' + renderInline(c) + '</th>').join('')
          + '</tr></thead><tbody>' + rows.map((r) => '<tr>' + header.map((_h, k) => '<td>' + renderInline(r[k] || '') + '</td>').join('') + '</tr>').join('')
          + '</tbody></table>');
        continue;
      }

      para.push(line);
      i += 1;
    }
    paragraph(para);
    return out.join('\n');
  }

  // Lists: one level of nesting by indentation; a list item continues on
  // following lines that are indented at least as far as its text.
  function renderList(lines, start, out) {
    let i = start;
    const first = lines[i].match(BULLET) || lines[i].match(NUMBERED);
    const ordered = !!lines[i].match(NUMBERED);
    const baseIndent = first[1].length;
    const items = [];
    while (i < lines.length) {
      const bullet = lines[i].match(BULLET);
      const numbered = lines[i].match(NUMBERED);
      const match = ordered ? numbered : bullet;
      const other = ordered ? bullet : numbered;
      if (match && match[1].length === baseIndent) {
        items.push({ text: [match[match.length - 1]], children: [] });
        i += 1;
        continue;
      }
      const deeper = (bullet || numbered) && (bullet || numbered)[1].length > baseIndent;
      if (deeper && items.length) {
        const nested = [];
        i = renderList(lines, i, nested);
        items[items.length - 1].children.push(nested.join(''));
        continue;
      }
      if (other && other[1].length === baseIndent) break; // a different list type starts
      if (lines[i].trim() && /^\s+/.test(lines[i]) && items.length && !bullet && !numbered) {
        items[items.length - 1].text.push(lines[i].trim());
        i += 1;
        continue;
      }
      break;
    }
    const tag = ordered ? 'ol' : 'ul';
    const startAttr = ordered && first[2] && Number(first[2]) !== 1 ? ' start="' + Number(first[2]) + '"' : '';
    out.push('<' + tag + startAttr + '>' + items.map((item) => '<li>' + item.text.map(renderInline).join('<br>') + item.children.join('') + '</li>').join('') + '</' + tag + '>');
    return i;
  }

  return { render, renderInline, escapeHtml, safeHref };
}));
