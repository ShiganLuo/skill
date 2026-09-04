# Markdown Editor Migration (wangEditor → md-editor-v3)

## Problem

Admin page uses wangEditor (HTML editor) for content creation, but the frontend renders content as plain text or with `v-html` (showing raw HTML tags). The fix is to migrate both sides to markdown.

## Migration Steps

### Admin (blog-vue3-back)

1. **Replace `<Editor>` with `<MdEditor>` in template:**
   ```vue
   <!-- Before -->
   <Editor v-model="content" style="max-height: 350px" />
   <!-- After -->
   <MdEditor v-model="content" :theme="'light'" :preview="true" style="max-height: 500px" />
   ```

2. **Replace `v-html` with `<MdPreview>` for content display:**
   ```vue
   <!-- Before -->
   <div class="talk-content" v-html="item.content" />
   <!-- After -->
   <MdPreview class="talk-content-preview" :modelValue="item.content" :theme="'light'" />
   ```

3. **Add imports:**
   ```ts
   import { MdEditor, MdPreview } from 'md-editor-v3'
   import 'md-editor-v3/lib/style.css'
   ```

4. **Fix initial state and empty checks:**
   ```ts
   // Before
   const initialFormState = { content: '<p><br></p>', ... }
   if (content.trim() == '<p><br></p>') { ... }
   // After
   const initialFormState = { content: '', ... }
   if (!content || content.trim() === '') { ... }
   ```

5. **Fix submit button disabled check:**
   ```vue
   <!-- Before -->
   :disabled="content == '<p><br></p>'"
   <!-- After -->
   :disabled="!content || content.trim() === ''"
   ```

### Frontend (blog-vue3-front)

1. **Replace `TextOverflow` or `v-html` with `<MdPreview>`:**
   ```vue
   <!-- Before -->
   <TextOverflow :text="talk.content" :maxLines="3" :font-size="14">
     <template v-slot:default="{ clickToggle, expanded }">
       <span @click="clickToggle" class="btn">{{ expanded ? "收起" : "展开" }}</span>
     </template>
   </TextOverflow>
   <!-- After -->
   <MdPreview class="talk-md-preview" :modelValue="talk.content" :theme="'light'" preview-only />
   ```

2. **Add imports:**
   ```ts
   import { MdPreview } from "md-editor-v3"
   import "md-editor-v3/lib/style.css"
   ```

3. **Remove old import:**
   ```ts
   // Remove
   import TextOverflow from "@/components/TextOverflow/index.vue"
   ```

## Pitfalls

- **Both projects need `md-editor-v3` installed.** Check `package.json` before starting.
- **`preview-only` prop** on `MdPreview` in frontend prevents editing interactions.
- **`:theme="'light'"`** — use string literal, not boolean. The prop expects `'light'` or `'dark'`.
- **Old HTML content in database** — existing records may have HTML content. Either migrate with a SQL UPDATE or handle both formats in the renderer.
- **`MdEditor` preview mode** — use `:preview="true"` to show side-by-side preview in admin editor.
