# md-editor-v3 Custom Toolbar API

## NormalToolbar

Used to add custom buttons to the md-editor-v3 toolbar via `#defToolbars` slot.

```vue
<MdEditor v-model="text" :toolbars="toolbars" :onUploadImg="onUploadImg">
  <template #defToolbars>
    <NormalToolbar title="tooltip text" :onClick="handler">
      <template #trigger>
        <svg>...</svg>  <!-- custom icon -->
      </template>
    </NormalToolbar>
  </template>
</MdEditor>
```

## Key API Details

- `NormalToolbar` is exported from `md-editor-v3` (NOT `EditorToolbar`)
- Props: `title` (string), `onClick` (function), `trigger` (string | VNode)
- `trigger` slot renders the button icon — without it, nothing visible
- `onClick` uses `:onClick` (prop binding), NOT `@onClick` (event)
- `#defToolbars` slot on `MdEditor` for custom toolbar items

## Available Toolbar Components

```ts
import { MdEditor, MdPreview, NormalToolbar, DropdownToolbar, ModalToolbar } from 'md-editor-v3'
```

## WangEditor (Editor.vue) — Different Library

WangEditor uses `customUpload` in `MENU_CONF.uploadImage`:

```ts
uploadImage: {
  async customUpload(file: File, insertFn: Function) {
    const res = await fetch(url, { method: 'POST', body: formData })
    const data = await res.json()
    // insertFn(src, alt, href) — inserts image at cursor
    insertFn(data.result.imageUrl, '', data.result.imageUrl)
  }
}
```

Key: WangEditor's `server` mode expects `{ errno: 0, data: { url } }` format.
If backend returns different format (e.g. `{ code: 200, result: { imageUrl } }`),
use `customUpload` instead of `server`.
