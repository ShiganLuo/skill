# Stat Card / Callout Layout Pattern

Tested pattern for stat callout boxes (2x2 number grid with labels) using pptxgenjs.

## Pattern

Each number and its label are SEPARATE `addText()` calls. No breakLine.

```javascript
function addStatCard(slide, { x, y, w, h, borderColor, title, titleColor, stats, filterText }) {
  slide.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: "FFFFFF" }, shadow: mkShadow() });
  slide.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.07, h, fill: { color: borderColor } });
  slide.addText(title, { x: x + 0.3, y: y + 0.1, w: w - 0.5, h: 0.3, fontSize: 13, fontFace: "Calibri", color: titleColor, bold: true, margin: 0 });

  const gridTop = y + 0.5;
  const rowH = 0.65;
  const colW = (w - 0.6) / 2;
  const colX = [x + 0.3, x + 0.3 + colW + 0.2];

  stats.forEach((s, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    slide.addText(s.value, { x: colX[col], y: gridTop + row * rowH, w: colW, h: 0.38, fontSize: 24, fontFace: "Calibri", color: s.color, bold: true, margin: 0 });
    slide.addText(s.label, { x: colX[col], y: gridTop + row * rowH + 0.38, w: colW, h: 0.22, fontSize: 9.5, fontFace: "Calibri", color: "636E72", margin: 0 });
  });

  slide.addText(filterText, { x: x + 0.3, y: y + h - 0.35, w: w - 0.5, h: 0.25, fontSize: 9.5, fontFace: "Calibri", color: "636E72", italic: true, margin: 0 });
}
```

## Key coordinates (card at y=0.95, h=2.0)

| Element | Y offset | Height |
|---------|----------|--------|
| Title | +0.1 | 0.3 |
| Row 1 numbers | +0.5 | 0.38 |
| Row 1 labels | +0.88 | 0.22 |
| Row 2 numbers | +1.15 | 0.38 |
| Row 2 labels | +1.53 | 0.22 |
| Filter text | +1.65 | 0.25 |
