# 给既有备份首次加 --delete：删除审计流程（2026-10 外置 exFAT 盘实测）

场景：单行 `rsync -avz SRC/ DST/` 镜像备份、多年无 --delete，目标端已积累大量"源端已删/已移"的陈旧内容。目标：加 `--delete` 让镜像反映真实状态，且不丢任何唯一副本。

## 流程（按序执行，不可跳步）

1. **只改脚本，不执行**。加 `--delete` 本身零风险，真跑才是危险动作。
2. **干跑一轮**：`rsync -avzn --delete ... > /tmp/dry1.log`；统计 `grep -c '^deleting '`、`grep -c 'rsync:'`、退出码。
3. **删除集分类审计**（对 `deleting ` 行按两级目录 Counter 分组，逐类核验）：
   - **移动/重构类**（占大头）：对可疑路径在源端 `find -name '<basename>'`——找到同名 = 移动，安全。目录重构（如笔记库换结构）会让整个旧树出现在删除清单里，全部是"旧路径空壳"。
   - **升级淘汰类**：同名新版本在源端存在（如 Clash 2.2.3 → 2.5.2）。
   - **垃圾类**：git repack 后的孤儿 `.git/objects`、旧日志、`~$` 锁文件、`*-journal`。
   - **唯一副本（源端 find 无果）= 决策点**：停下问用户，三选一——拷回源端保底（**须用户同意，别自作主张写入源目录**）／`--filter=protect` 留在目标端／确认删除。本次案例：`Reference.tar.gz` 64.4GB 快照归档 → protect 保留。
4. **保护机制用合成样例实测**（秒级，别凭记忆）：

   ```bash
   # /tmp 建 src/dst，dst 放三个 dest-only 文件：裸的、protect 规则的、被 exclude 目录内的
   rsync -avn --delete --filter='protect /prot.txt' --exclude=/excl_dir/ src/ dst/
   # 看删除清单：基线全删；protect 与 exclude 目录内的都不出现在 deleting 里
   ```

   实测结论：`--filter=protect /path` 与 `--exclude=/dir/` **都保护目标端独有文件**（默认不带 `--delete-excluded` 时）。
5. **干跑有错误时删除清单不可信**——权限错误会让删除遍历**扫到出错目录即中断**（本次 run1 仅 896 条全在 Code 段，修错后 run2 是完整 5,976 条）。先修错误、重跑干跑，再 diff 两轮删除集（新增部分必须全部归类），清单才可用于审批。
6. **真跑前单独向用户要一次点头**。批准"加 --delete"≠ 批准"执行首次大规模同步"；用户明确要求过执行前再确认。

## exit 23 的两类根因（看日志原文区分）

- `rsync: [sender] opendir ... Permission denied` = 源端读不了 → 多为 Docker 数据卷（mysql/redis root 属主）。用 `--exclude` 掉：运行时数据库文件本不该做文件级备份（该备份的是 mysqldump）。通过标准：`grep -c 'rsync:'` == 0。
- `chown/chmod ... Operation not permitted` = exFAT 属主 → `--no-o --no-g --no-perms`（见 SKILL 主文 exFAT 节）。

## du 与 rsync 数字对不上的两个原因（exFAT）

- **簇 slack**：du 按簇分配计、rsync 按逻辑大小。512K+ 簇让小文件集合虚胖——本次外置 Reference "比源端多 66GB" 实为同内容虚胖，干跑零动作。**别把 du 差值当"目标端独有内容"**。
- 删回收站时 df 实增（174G）> 逻辑和（149G）：簇 slack 随删除一并回收。

## 本次最终脚本形态（供参照）

```bash
rsync -avz --delete --filter='protect /Reference/Reference.tar.gz' \
  --exclude='/Code/blog/database/mysql/' --exclude='/Code/blog/database/redis/data/' \
  /home/<USER>/Work/<USER>/ ./<USER>
```

5,976 条删除审计结论：笔记/research-group 为目录重构移动（同名文件逐一在新路径验证存在）、Code 下为 repack 孤儿与旧版本、minio/data 为镜像实时态；唯一副本 tar.gz 用 protect 保留；mysql/redis 排除后 exit 23 清零。
