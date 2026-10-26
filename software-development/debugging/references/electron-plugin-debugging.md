# Third-Party Electron Plugin Debugging

Covers Obsidian, VS Code extensions, and similar Electron-based plugin systems where source code is accessible but you can't set breakpoints (no debug port exposed).

## When to use

- Obsidian/VS Code/Electron app shows an uncaught error with a file path
- A plugin is misbehaving and the error points to the plugin's code
- You need to fix a plugin bug without waiting for upstream

## Workflow

1. **Read the stack trace** — extract the function name, file path, and the path/operation that failed.
2. **Locate the plugin directory** — for Obsidian: `<vault>/.obsidian/plugins/<plugin-id>/`. Read `data.json` first to understand configured behavior (folder patterns, naming conventions, feature toggles).
3. **Search `main.js`** for error keywords (function names, path patterns from the trace). Use `search_files` on the plugin directory.
4. **Trace the event handler chain** — most plugins register handlers on `file-open`, `create`, `rename`, `delete`, or `layout-change` in the Plugin class's `onload()`. Read each handler to understand when and why it touches the filesystem or API.
5. **Patch `main.js` directly** — plugin code is plain JS, usually not minified. Changes take effect after app reload (Ctrl+R in Obsidian).

## Pitfalls

- **Do NOT batch-create missing resources to satisfy a plugin.** If a plugin expects a directory to exist and crashes when it doesn't, the bug is in the plugin (it should `exists()` check or `createFolder()` first). Creating hundreds of empty directories clutters the workspace and masks the real issue. User correction: "不需要创建" — fix the code, not the symptom.
- **`var` hoisting in bundled plugin JS** — all `var` declarations are module-scoped and hoisted. A `var` at line 500 is readable at line 200. The VALUE assignment runs sequentially, but all handlers fire after module-level code completes, so everything is populated.
- **`vault.setConfig('attachmentFolderPath', path)` triggers a filesystem scan** of that path in Obsidian. If the path doesn't exist → `ENOENT: scandir`. Always ensure the directory exists before setting this config.
- **Don't confuse `adapter.list()` with `adapter.exists()`** — `list()` throws on non-existent paths, `exists()` returns false gracefully. Use `exists()` for guards.
- **Obsidian plugin settings tabs are in `main.js` too** — search for `Setting` or `SettingTab` to find config UI code that reveals what each toggle actually does.

## Obsidian-specific paths

| What | Path |
|------|------|
| Plugin directory | `<vault>/.obsidian/plugins/<plugin-id>/` |
| Plugin config | `<vault>/.obsidian/plugins/<plugin-id>/data.json` |
| Plugin source | `<vault>/.obsidian/plugins/<plugin-id>/main.js` |
| Vault config | `<vault>/.obsidian/app.json` |
| Installed plugins list | `<vault>/.obsidian/community-plugins.json` |