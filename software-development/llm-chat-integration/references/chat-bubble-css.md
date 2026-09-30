# Chat Bubble CSS Sizing Patterns

## The Problem

By default, `.message-bubble` inside a flex container takes the **full width** of its parent, making every bubble the same size regardless of content length. Short messages like "服务不可用" get a wide bubble.

## The Fix

```css
.message-bubble {
  width: fit-content;
  max-width: 100%; /* or 75% of parent */
}

/* User messages: right-align the bubble */
.message-bubble.user {
  margin-left: auto;
}
```

## Why This Happens

The parent `.message-body` or `.message-content` has `max-width: 75%`. Without `width: fit-content`, the bubble stretches to fill that 75% even for short text. The fix makes the bubble wrap to its content width.

## Checklist for Chat Components

When styling chat bubbles, ensure:

1. `.message-bubble` has `width: fit-content` + `max-width: 100%`
2. User messages have `margin-left: auto` to push right
3. Assistant messages stay left (default)
4. The parent container has `max-width` to cap bubble width
5. Both front and admin must have identical styling

## Files to Check

- `bioplatform-front/src/components/ChatMessage.vue` — reusable component
- `bioplatform-front/src/views/agent/AgentView.vue` — streaming bubble
- `bioplatform-admin/src/views/agent/AgentView.vue` — admin streaming bubble