# Secure Boot 拒签 NVIDIA 模块：外接屏无信号的完整取证（2026-10-22 实测，MSI Alpha 17 C7VG）

## 症状
外接显示器插上完全无反应。`/sys/class/drm/` 只见 AMD iGPU 的 card1（eDP + DP-1/2/3 全 disconnected），无 NVIDIA card，无任何 HPD 事件。

## 判据链
1. HDMI/DP 音频 pin 挂在 dGPU：`journalctl -b -k | grep 'HDA NVidia'` → 0000:01:00.1 = 视频口也在 dGPU
2. `lsmod | grep -c nvidia` = 0 且 `sudo modprobe nvidia` → `Key was rejected by service` = **Secure Boot 拒绝模块签名**（root 也一样报）
3. 模块存在且 dkms 构建正常：`dkms status` 两内核都 installed → 不是构建问题
4. 模块签名者 = 本机 MOK：`modinfo -F signer <ko>` → "<USER>-xxx Secure Boot Module Signature key"
5. 上一次启动（旧内核）nvidia 正常加载（`journalctl -b -1 -k | grep NVRM`）→ 期间固件侧 MOK 登记丢失/失效

## 修复：绕开 MOK，用 Canonical 官方签名模块
系统常已装 `linux-modules-nvidia-580-<kernel>`（官方签名模块在 `kernel/nvidia-580/`），但被 `updates/dkms/` 里本机 MOK 签名的 DKMS 模块**遮蔽**（depmod 解析优先级 updates/dkms 更高）。移走 DKMS 模块即可：

```bash
modinfo nvidia | grep filename        # 指向 updates/dkms = 被遮蔽
sudo mkdir -p /root/dkms-nvidia-backup-580
sudo mv /lib/modules/$(uname -r)/updates/dkms/nvidia*.ko.zst /root/dkms-nvidia-backup-580/
sudo depmod -a $(uname -r)
sudo modprobe nvidia nvidia-drm nvidia-modeset
```

验证：`nvidia-smi -L` 有输出；`/sys/class/drm/` 出现 card0（NVIDIA）且其 HDMI-A-1/DP-* 变 connected；`kscreen-doctor -o` 自动列出输出并 enabled。物理屏仍黑则拔插一次线触发 HPD。

## 坑
- **MOK 重登记不可靠**：`mokutil --import` + 重启蓝屏确认后，pending 请求可能静默消失（MokListRT 仍无密钥）。别在这条路上反复浪费时间——官方签名模块是更短的路。
- **换内核/更新驱动后复发**：DKMS 会把 MOK 签名模块重新塞回 updates/dkms/。复发识别法：外接屏又没信号 + `modprobe nvidia` 报 Key rejected → 同法再移。根治=卸载 `nvidia-dkms-580` 包只留官方模块。
- 与本 skill 模式四（EDID 骤降）区分：那是"有信号但分辨率降"，这是"连接器根本不存在/无 HPD"。
