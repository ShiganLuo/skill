# Zotero SQLite schema (relevant tables)

`zotero.sqlite` is the main DB. Useful for: finding itemID by citekey, getting full metadata, listing attachments, etc.

**Warning**: The DB is locked while Zotero is running. Use `zotero.sqlite.bak` or `.1.bak` for read-only queries, or copy to `/tmp/zotero-readonly.sqlite` and open the copy.

## Tables (61 total, key subset)

| Table | Purpose |
|---|---|
| `items` | Core items: `itemID`, `itemTypeID`, `key` (8-char), `libraryID`, `dateAdded`, `dateModified` |
| `itemTypes` | Type definitions: `itemTypeID`, `typeName` (book, journalArticle, webpage, etc.) |
| `itemData` | Field values: `itemID`, `fieldID`, `valueID` |
| `itemDataValues` | Actual values: `valueID`, `value` (string) |
| `fields` | Field definitions: `fieldID`, `fieldName` (title, date, DOI, etc.) |
| `creators` | Authors/editors: `creatorID`, `firstName`, `lastName`, `fieldMode` (0=full, 1=initials) |
| `itemCreators` | Junction: `itemID`, `creatorID`, `creatorTypeID`, `orderIndex` |
| `itemAttachments` | PDF attachments: `itemID`, `parentItemID`, `linkMode`, `path` |
| `itemNotes` | Zotero notes: `itemID`, `parentItemID`, `note` (HTML) |
| `itemTags`, `tags` | Tags |
| `collections`, `collectionItems` | Folder structure |
| `settings` | Plugin settings |

## Better BibTeX data location

**IMPORTANT**: Newer Better BibTeX versions (post ~2024) do NOT create `betterbibtex_citekeys` table. citekeys are stored as JSON in the `syncedSettings` table or as `extra` field on items.

Don't try to query Better BibTeX tables — they may not exist. Always parse the `.bib` export for citekeys.

## Common queries

### Get all items with full metadata

```sql
SELECT i.key, i.itemTypeID, it.typeName, f.fieldName, v.value
FROM items i
JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
JOIN itemData d ON i.itemID = d.itemID
JOIN fields f ON d.fieldID = f.fieldID
JOIN itemDataValues v ON d.valueID = v.valueID
WHERE i.itemID IN (
    SELECT itemID FROM items
    WHERE itemTypeID != (SELECT itemTypeID FROM itemTypes WHERE typeName='attachment')
)
ORDER BY i.itemID, f.fieldName;
```

### Get creators for an item

```sql
SELECT c.lastName, c.firstName, ic.orderIndex
FROM creators c
JOIN itemCreators ic ON c.creatorID = ic.creatorID
WHERE ic.itemID = ?
ORDER BY ic.orderIndex;
```

### Get attachment path (PDF) for an item

```sql
SELECT path FROM itemAttachments WHERE parentItemID = ? AND linkMode = 1;
-- linkMode 1 = imported file (stored in Zotero/storage/)
-- linkMode 0 = linked file
-- linkMode 2 = web link
```

## Practical note

For most operations (mapping citekey <-> metadata, building bulk frontmatter), parsing `My Library.bib` is faster and doesn't risk corrupting the DB. Use SQLite only when:
- You need attachment paths (PDF locations)
- You need item creation/modification timestamps
- You need to write back to Zotero (e.g., add tags from script)
