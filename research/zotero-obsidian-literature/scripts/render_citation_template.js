// Render an obsidian-citation-plugin template from a bib entry, replicating
// what the plugin would produce inside Obsidian. Used when Hermes cannot
// drive the Obsidian GUI directly (the plugin is isDesktopOnly: true).
//
// Usage:
//   1. Prepare data.json with citekey1, entry1 (parsed bib), template string
//   2. node render_citation_template.js
//
// The Citations plugin's actual Handlebars helpers include zoteroSelectURI
// (and a few others). This script registers zoteroSelectURI; if you need
// more, copy from obsidian-citation-plugin main.js.

const fs = require('fs');
const Handlebars = require('handlebars');
const data = JSON.parse(fs.readFileSync('data.json', 'utf8'));

// Register the plugin's helper
Handlebars.registerHelper('zoteroSelectURI', function (options) {
  return `zotero://select/items/@${this.citekey}`;
});

function buildContext(ck, entry) {
  return {
    citekey: ck,
    title: entry.title || '',
    titleShort: (entry.title || '').replace(/[:?.!].*$/, '').substring(0, 50),
    year: entry.year || '',
    containerTitle: entry.journal || entry.booktitle || entry.publisher || '',
    DOI: entry.doi || '',
    URL: entry.url || '',
    abstract: entry.abstract || '',
    entry: { author: entry.author || [] },
  };
}

const template = Handlebars.compile(data.template);

['citekey1', 'citekey2'].forEach((k) => {
  if (!data[k]) return;
  const ck = data[k];
  const entryKey = k.replace('citekey', 'entry');
  if (!data[entryKey]) return;
  console.log(`===== ${ck} =====`);
  console.log(template(buildContext(ck, data[entryKey])));
});
