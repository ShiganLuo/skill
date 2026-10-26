#!/bin/bash
# 双向 rsync 同步脚本骨架
# 用法: ./sync.sh <server> [push|pull|both]
#   push = 本地 → 远端; pull = 远端 → 本地; both = 先 push 再 pull（并集，冲突以本地为准）
#   省略 direction 时用各分支的默认方向（保持向后兼容）
# 要点:
#   - 路径字符串按原脚本逐字保留；方向性差异只在使用点归一化（pull 源 ${remote%/}/）
#   - both 顺序不能反：pull→push 会用远端旧版覆盖本地新文件（rsync 默认无 --update）
#   - 不带 --delete = 两边只增不删的并集语义

LOCAL_DIR="/local/path/Database"

sync(){
	server=$1
	direction=$2

	# 每个分支只声明三样: ssh 选项、远端路径、默认方向
	case ${server} in
		server_a)
			ssh_opt="ssh -p 22 -i ~/.ssh/key_a"
			remote="user@host-a:/data/Database"      # push 的目标, 原样保留（可不带尾斜杠）
			def="push"
			;;
		server_b)
			ssh_opt="ssh -p 22 -i ~/.ssh/key_b"
			remote="user@host-b:/data/Database/"
			def="pull"
			;;
		*)
			echo "unknown server: ${server}"
			echo "usage: $0 <server_a|server_b> [push|pull|both]"
			return 1
			;;
	esac

	[ -z "${direction}" ] && direction=${def}

	push(){
		echo "[push] local -> ${server}"
		rsync -avzP -e "${ssh_opt}" "${LOCAL_DIR}/" "${remote}"        # 源带斜杠=拷贝内容
	}
	pull(){
		echo "[pull] ${server} -> local"
		rsync -avzP -e "${ssh_opt}" "${remote%/}/" "${LOCAL_DIR}"      # 源统一补斜杠, 否则嵌套
	}

	case ${direction} in
		push) push ;;
		pull) pull ;;
		both) push && pull ;;    # 顺序: 先 push 再 pull, 冲突以本地为准
		*)
			echo "unknown direction: ${direction} (push|pull|both)"
			return 1
			;;
	esac
}
sync "$1" "$2"
