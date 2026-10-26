#!/usr/bin/env python3
"""减肥计划.md 例行校验：体重差值计算 + 条目排序校验。每次记体重/写条目后运行。

用法: python3 diet_check.py [新体重kg]        # 不带参数只做排序校验
输出: 较基准差、较上一条环比、排序是否升序、条目数
"""
import re
import sys

BASE = 88.60  # kg, 2026-10-11
MD = '/home/<USER>/Work/<USER>/work/笔记/Schedule/长期计划/减肥计划.md'

txt = open(MD, encoding='utf-8').read()

# 1) 排序校验
times = re.findall(r'### (\d{4}-\d{2}-\d{2} \d{2}:\d{2})', txt)
print(f"entries: {len(times)}, sorted: {times == sorted(times)}")
if times != sorted(times):
    for a, b in zip(times, times[1:]):
        if a > b:
            print(f"  OUT OF ORDER: {a} -> {b}")

# 2) 体重差值
rows = re.findall(r'\| (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| ([\d.]+) kg \| ([-+\d.]+) kg \|', txt)
if rows:
    w, diff_col = float(rows[-1][1]), float(rows[-1][2])
    expect = round(w - BASE, 2)
    print(f"last row {rows[-1][0]}: {w} kg, 变化列 {diff_col:+.2f} (应≈{expect:+.2f}) "
          f"{'OK' if abs(diff_col - expect) < 0.005 else 'MISMATCH'}")

if len(sys.argv) > 1:
    w = float(sys.argv[1])
    prev = float(rows[-1][1]) if rows else None
    print(f"new {w} kg: 较基准 {w - BASE:+.2f}"
          + (f", 较上一条({prev}) {w - prev:+.2f}" if prev else ""))
