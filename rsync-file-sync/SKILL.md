---
name: rsync-file-sync
version: 1.0
license: MIT
description: "Use when writing rsync sync scripts — 尾斜杠语义与双向同步方向顺序."
metadata:
  hermes:
    tags: [linux, rsync, shell, backup, sync]
    related_skills: [linux-system-administration]
tags: [linux, rsync, shell, backup, sync]
author: curator
---

# rsync 同步脚本编写

多服务器/多方向的同步脚本（单脚本多分支，每分支 push/pull/both 可选）。

## When to Use

- 编写或修改 rsync 同步脚本（多远端、多方向、定时备份）
- 用户报告"同步后目标下多嵌套一层目录"、"双向同步把新文件覆盖了"
- 把只单向用过的脚本扩展成双向
- backup.sh 类单行 rsync 脚本报 `change_dir "/root/..." failed` 或刷屏 `chown ... Operation not permitted`
- 把 rsync 目标指向 U盘/移动硬盘（exFAT/NTFS）
- 给既有备份首次加 `--delete`（删除清单审计、唯一副本保护、exit 23 排查 → `references/delete-audit-workflow.md`）

## sudo 与外接盘的两个坑（backup.sh 实测）

**坑 1：`sudo bash script.sh` 让脚本里的 `~` 展开成 /root**

`~` 由**解析脚本的那个 shell** 展开：普通用户跑 → `/home/用户`；`sudo bash` 跑 → root 解析 → `/root` → `rsync: change_dir "/root/Work/..." failed: No such file or directory (2)`。规则：给 sudo 场景用的脚本，源/目标一律写绝对路径，不依赖 `~`/`$HOME`（展开机制详见 linux-system-administration 的 Shell Configuration）。

**坑 2：目标是 exFAT/NTFS → `-a` 的 chown 刷屏 EPERM**

先 `findmnt -T <目标>` 确认 FSTYPE。exFAT 不存属主/权限位，chown/chmod 一律 `Operation not permitted`（root 也一样，不是权限不够）。`-a`（= `-rlptgoD`）含 `-o -g -p` → 每个文件报 chown 失败、退出码 23，**但数据其实已传完，错误全发生在"恢复属主"这步**。修法：

```bash
rsync -avz --no-o --no-g --no-perms SRC/ DST/
```

配套：这类盘的挂载点常属 root 且 `dmask=022`，普通用户连 touch 都失败、必须 sudo 跑 rsync；根治是在 fstab 用 `uid=<用户>,fmask=133` 挂载（见 linux-system-administration）。

## 尾斜杠语义（本技能的核心）

| 写法 | 含义 |
|------|------|
| `rsync -a src/ dest` | 拷贝 src 的**内容**到 dest |
| `rsync -a src dest` | 拷贝 **src 目录本身**到 dest → dest 已存在时生成 `dest/src/...`（嵌套） |

关键认知：**斜杠语义属于"源/目标"这个角色，不属于路径字符串本身**。同一条路径当源和当目标时语义相反——这是把单向脚本泛化成双向时最常踩的坑。

交付前用本地目录复现验证（不碰网络，几秒完成）：

```bash
T=/tmp/rsync_slash; rm -rf $T; mkdir -p $T/src/sub $T/dest; echo x > $T/src/a.txt
rsync -a $T/src  $T/dest/; find $T/dest -mindepth 1   # 源无斜杠 → dest/src/a.txt（嵌套）
rm -rf $T/dest; mkdir -p $T/dest
rsync -a $T/src/ $T/dest;  find $T/dest -mindepth 1   # 源带斜杠 → dest/a.txt（内容直入）
```

## 重构纪律（用户纠正过的偏差）

把"只当过目标的路径"（push 目标通常不带尾斜杠）复用为 pull 的源 → 斜杠语义翻转 → 嵌套错误。规则：

1. 原脚本的路径/SSH 参数**逐字保留**，改完用 `grep -F` 逐条核对原字符串清单
2. 方向性差异在**使用点**归一化：pull 源统一写 `${remote%/}/`（先剥尾斜杠再补，避免双斜杠）
3. 语义用上面的本地复现验证，再声称正确

## 双向同步（push / pull / both 模式）

脚本骨架见 `templates/bidirectional-rsync.sh`：每分支只声明 ssh_opt、remote、默认方向；push/pull 两个子函数；direction 参数分发，省略时用分支默认方向（保持向后兼容）。

**both 的顺序必须 push → pull，不能反**：rsync 默认不带 `--update`，按 size/mtime 判定传输，**后执行的方向决定冲突文件的最终版本**：

- push→pull：远端先拿到本地版本，随后 pull 只补回远端独有的文件 → 两边取并集，冲突以**本地**为准
- pull→push：远端旧版本先覆盖本地新文件，push 再把这份旧版推回去 → 本地新文件**丢失**

注意：不带 `--delete` 时两边只增不删（并集语义）；要清掉对端多余文件才加 `--delete`。**给既有备份首次加 `--delete` 必须走删除审计流程**：干跑 → 删除集分类核验（移动/淘汰/垃圾 vs 唯一副本）→ 合成样例实测 protect/exclude 保护语义 → 单独向用户要执行确认再真跑；干跑有权限错误时删除清单会截断、不可信。完整步骤、exit 23 排查与 exFAT 簇 slack 陷阱见 `references/delete-audit-workflow.md`。

## 验证清单

1. `bash -n` 语法检查
2. 错误路径（未知 server/direction）打印用法且**不触发 rsync**
3. 斜杠语义本地复现
4. 真实连通性用 `rsync -n` 干跑——干跑没跑通（超时/不通）必须如实告知"连通性未验证"，不得当作已完成
