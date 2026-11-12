# NeMoClaw 本地启动指南（无需 Brev）

本指南适用于两种部署环境：

- **Windows 11 + WSL2 + Docker**：所有服务均在 WSL2 的 Ubuntu-24.04 中运行。
- **DGX Spark Station（原生 Ubuntu Linux）**：采用相同的步骤，通过原生 Docker 运行；可以直接使用 DGX 上的浏览器（Firefox）访问 `http://localhost:8081`，也可以通过 SSH 隧道从 Windows 浏览器访问（见第 0.5 节）。

第 0 节是**一次性设置**（如果 `nemoclaw --version` 已能正常运行，可以跳过）。
第 1 节及后续内容是完成设置后**每次使用时的启动步骤**。

命令中的 `<username>`、`<your-username>`、`<your-github-username>` 和 `<dgx-ip>` 均为占位符，请替换为实际的用户名或地址，不要原样执行。

---

## 0 — 一次性设置（仅首次使用）

### 0.1 Windows 11 + WSL2 + Docker

**安装 WSL2 和 Ubuntu 24.04**（以管理员身份运行 PowerShell）：
```powershell
wsl --install -d Ubuntu-24.04
wsl --set-default Ubuntu-24.04
```

在 Ubuntu-24.04 中**配置 `~/.bashrc`**，将 NeMoClaw 加入 PATH：
```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
export PATH="$HOME/.local/bin:$PATH"
export no_proxy="${no_proxy},localhost,127.0.0.1,::1"
export NO_PROXY="${NO_PROXY},localhost,127.0.0.1,::1"
```
然后运行 `source ~/.bashrc`。

在 Ubuntu-24.04 中**安装 Docker Engine**（不是 Docker Desktop）：
按 https://docs.docker.com/engine/install/ubuntu/ 中的说明操作。然后在 `/etc/wsl.conf` 中加入以下配置，使 Docker 自动启动：
```ini
[boot]
command = service docker start
```

**安装 aiohttp**：
```bash
pip3 install aiohttp --break-system-packages
```

### 0.2 DGX Spark Station（原生 Ubuntu Linux）

**将当前用户加入 Docker 组**（运行一次，然后注销并重新登录）：
```bash
sudo usermod -aG docker $USER
newgrp docker   # 无需重新登录，直接在当前会话中应用组权限
 docker ps      # 验证：应能列出容器，不出现权限错误
```

**安装 aiohttp**：
```bash
pip3 install aiohttp --break-system-packages
```

**仅针对中国网络环境：添加 Docker Hub 镜像源**（用于无法直接访问 Docker Hub 的环境）：
```bash
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "registry-mirrors": [
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com",
    "https://docker.m.daocloud.io",
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
 docker pull hello-world   # 验证镜像源是否可用
```

**生成 SSH 密钥并在 GitHub 中注册**：
```bash
# 1. 生成密钥；按原指南使用默认路径，并在提示中选择是否设置口令
ssh-keygen -t ed25519 -C "your-email@example.com"

# 2. 复制公钥
cat ~/.ssh/id_ed25519.pub
```
打开 **github.com → Settings → SSH and GPG keys → New SSH key**，粘贴输出并保存。

验证密钥是否被接受：
```bash
ssh -T git@github.com
# 预期：Hi <your-github-username>! You've successfully authenticated...
```

**克隆课程仓库**：
```bash
git clone git@github.com:NVDLI/NemoClawDLI-zh.git ~/nemoclaw-zh
```

### 0.3 安装 NeMoClaw（两种平台均适用）

在之后使用 NeMoClaw 的终端中运行：WSL2 使用 Ubuntu-24.04 终端；DGX 使用任意终端。

```bash
# 分两步执行，避免慢速连接下将下载内容通过管道传给 bash 导致标准输入阻塞
curl -fsSL https://www.nvidia.com/nemoclaw.sh -o /tmp/nemoclaw-install.sh
bash /tmp/nemoclaw-install.sh
source ~/.bashrc
nemoclaw --version    # 预期：nemoclaw v0.0.55 或更新版本
```

> **注意：** 下载缓慢时，`curl ... | bash` 可能阻塞，因为管道会占用标准输入。以上两步执行方式可避免该问题。

### 0.4 NeMoClaw 初始配置（两种平台均适用）

> ⚠️ **仅 WSL2：** 请始终加上 `NEMOCLAW_SANDBOX_GPU=0` 前缀。否则初始配置会强制使用 `--gpu`，导致 WSL2 上的 sandbox 无法正常工作。

> ⚠️ **DGX + SSH：** 初始配置需要下载容器镜像，慢速连接下可能耗时 30–90 分钟。请在 `tmux` 中运行，避免 SSH 断开后进程被终止：
> ```bash
> tmux new-session -s nemoclaw
> # 在此 tmux 窗口中执行初始配置
> # SSH 断开后，重新连接并运行：tmux attach -t nemoclaw
> ```

> ⚠️ **DGX + pip 安装的 openshell 虚拟环境：** 如果通过 pip 将 openshell 安装在虚拟环境中，**运行 `nemoclaw onboard` 前请先退出虚拟环境**。否则 nemoclaw 会检测到 pip 版本（0.0.109）并尝试降级；无法访问 GitHub 时，降级会失败。
> ```bash
> deactivate       # 退出当前虚拟环境
> which openshell  # 应显示 /usr/local/bin/openshell
> ```

```bash
# WSL2：
NEMOCLAW_SANDBOX_GPU=0 nemoclaw onboard

# DGX：原生 Linux，在 tmux 内执行，且已退出虚拟环境
nemoclaw onboard
```

初始配置时选择：
- Provider：**NVIDIA Endpoints**（`integrate.api.nvidia.com`），这是原指南推荐的提供商。本地 vLLM（DGX Spark 的可选方案）需要下载 HuggingFace 模型，中国网络环境可能无法访问。
- Chat model：例如 `nvidia/nemotron-3-super-120b-a12b`。
- Resource profile：DGX Spark 选择 **No profile**（选项 6）。
- Web search：选择 **No web search**（选项 1）。
- Messaging channel：跳过，课程练习不需要。

配置完成后运行：
```bash
nemoclaw my-assistant status
```

### 0.5 DGX — SSH 端口转发（从 Windows 浏览器访问页面）

在 **Windows 电脑**上建立 SSH 隧道，使 Windows 浏览器能够访问 DGX 上的课程页面和代理服务。整个使用期间请保持该终端打开。

**场景 A：仅运行 DGX 部署，没有运行 WSL2 部署。**
Windows 上的标准端口均未被占用：
```bash
# 在 Windows 的 Git Bash 中运行；请替换最后一行的占位符
ssh -L 8081:localhost:8081 \
    -L 8010:localhost:8010 \
    -L 8011:localhost:8011 \
    <username>@<dgx-ip>
```
在 Windows 浏览器中打开 `http://localhost:8081/zh/nemoclaw/03a-kickstart.html`。
Chat 和 Embedder 的 base URL 均设为 `http://127.0.0.1:8010/v1`。

**场景 B：DGX 和 WSL2 同时运行。**
WSL2 已占用 Windows 上的 8081/8010/8011 端口，DGX 请使用其他本地端口：
```bash
ssh -L 8082:localhost:8081 \
    -L 8013:localhost:8010 \
    -L 8014:localhost:8011 \
    <username>@<dgx-ip>
```
在 Windows 浏览器中打开 `http://localhost:8082/zh/nemoclaw/03a-kickstart.html`。
Chat 和 Embedder 的 base URL 均设为 `http://127.0.0.1:8013/v1`。

> **无需隧道的替代方案：** 如果 DGX 已连接显示器，直接在 DGX 浏览器中打开 `http://localhost:8081/zh/nemoclaw/03a-kickstart.html`，并将 base URL 设为 `http://127.0.0.1:8010/v1`。这样无需 SSH 隧道，也不会与 Windows 端口发生冲突。

---

## 1 — 每次使用时的启动步骤

在 **WSL2 的 Ubuntu-24.04 终端**中按顺序运行；DGX 用户在 DGX 终端中运行，并使用下方对应的启动脚本路径。

```bash
# ── 1a. 设置 NVIDIA API 密钥 ──
export NVAPI_KEY="nvapi-..."   # 在此填写自己的密钥

# ── 1b. 启动全部后台服务：Web 服务器和代理 ──
# WSL2：请根据自己的仓库位置修改路径
bash "/mnt/c/Users/<your-username>/OneDrive - NVIDIA Corporation/NVIDIA/DLI/Courses/NeMoClaw/repo/start_proxies.sh"
# DGX：
# bash ~/nemoclaw-zh/start_proxies.sh
# 启动：http.server :8081、cors_proxy :8010、openclaw_proxy :8011、policy_proxy :8012
# 再次运行时会先终止残留实例，因此崩溃后可以重新执行。

# ── 1c. 恢复 OpenClaw 容器（如有需要）──
nemoclaw my-assistant recover
# 预期："Probe complete: OpenClaw gateway is running in 'my-assistant'."

# ── 1d. 将 SSH 转发替换为基于 gRPC 的转发 ──
openshell forward stop 18789
nohup openshell forward service my-assistant --target-port 18789 --local 18789 \
  > /tmp/openclaw-fwd.log 2>&1 &

# ── 1e. 修复推理服务所需的 Docker iptables 规则（关键步骤）──
# 每次 WSL2/Docker 重启后这些规则会丢失，必须重新应用。
# Docker 29.x 不会为自定义桥接网络自动创建 conntrack 规则。
BRIDGE=$(docker network inspect openshell-docker \
  --format '{{index .Options "com.docker.network.bridge.name"}}')
[ -z "$BRIDGE" ] && BRIDGE="br-$(docker network inspect openshell-docker \
  --format '{{.Id}}' | cut -c1-12)"
echo "Bridge: $BRIDGE"
sudo iptables -I DOCKER-FORWARD 3 -i $BRIDGE -j ACCEPT
sudo iptables -I DOCKER-CT 1 -o $BRIDGE -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

# ── 1f. 验证所有服务是否正常 ──
CONTAINER=$(docker ps --filter name=openshell-my-assistant --format "{{.Names}}" | head -1)
docker exec $CONTAINER curl --noproxy '*' -sk --max-time 10 \
  -o /dev/null -w "NVIDIA reachability: %{http_code} in %{time_total}s\n" \
  https://integrate.api.nvidia.com/v1/models
# 预期：NVIDIA reachability: 200 in ~0.5s

curl -s http://localhost:18789/healthz   # → {"ok":true,"status":"live"}
curl -s http://localhost:8011/healthz    # → {"ok":true,"status":"live"}
```

---

## 2 — 获取网关 Bearer Token（浏览器每次使用时需要）

```bash
docker exec $CONTAINER \
  cat /sandbox/.openclaw/openclaw.json | python3 -c \
  "import json,sys; c=json.load(sys.stdin); print(c['gateway']['token'])"
```

复制此 token，稍后将其粘贴到浏览器中 03a 页面的对应字段。

---

## 3 — 浏览器设置

1. 打开 **http://localhost:8081/zh/nemoclaw/03a-kickstart.html**。
2. 在 **API key** 字段中输入 NVIDIA API 密钥。
3. 在 **Bearer token** 字段中输入第 2 节获取的 token。
4. 完成 03a 页面上的健康检查，确认整条链路正常工作。
5. 按顺序学习：01a、01b、01c、02a……03a、03b、03c、04a、04b、04c。

---

## 4 — 特定页面的说明

### 所有页面：重新构建或恢复之后

如果页面显示 **DEGRADED**，或健康检查失败且显示 `toolSearch: true`：
- 在健康检查前运行当前页面的 **🛠 Recover** 单元。
- 该操作会将 `toolSearch` 重置为 `false`。

### 仅 04a 页面：实时策略

无需手动操作，以下两项改动已包含在 HTML 中：
1. 每次加载页面时，`window.__SBX_POLICY` 都会预先加载到页面的 `<head>` 中。
2. 当操作终端无法访问控制平面时（本地部署），"Read your live policy" 的 RUN 单元会自动回退到 `window.__SBX_POLICY`。

正常点击该单元的 RUN 即可。它会记录 "(local deployment) using pre-loaded policy"，随后继续绘制策略图并填充后续所有单元。

---

## 5 — 快速诊断

| 现象 | 处理方式 |
|---|---|
| 健康检查超时（约 92 秒） | 重新应用第 1e 步的 iptables 规则；重启后规则会丢失 |
| 健康检查显示 DEGRADED / `toolSearch: true` | 运行当前页面的 🛠 Recover 单元 |
| doctor 显示 `[fail] Docker container: openshell-cluster-nemoclaw` | 原指南将其标为误报；本地部署采用不同的容器命名方式 |
| `openshell forward` 未运行 | 重新执行第 1d 步 |
| 18789 端口返回 Squid HTML，而不是网关响应 | 转发服务未运行或命名空间不匹配；重新执行第 1c 和 1d 步 |
| 04a 页面的 `helpers.policyGet()` 失败 | 本地部署中可能出现此情况；使用预加载的 `window.__SBX_POLICY`（见第 4 节） |
| 页面似乎未应用 JS 改动 | 浏览器缓存了旧的 ES module；使用 **Ctrl+Shift+R** 强制刷新，绕过模块缓存 |

---

## 6 — 各后台进程的作用

| 进程 | 端口 | 作用 |
|---|---|---|
| `python3 -m http.server 8081` | 8081 | 向浏览器提供课程 HTML 页面 |
| `cors_proxy.py` | 8010 | CORS 适配层，将浏览器请求代理到 NVIDIA NIM API（integrate.api.nvidia.com） |
| `openclaw_proxy.py` | 8011 | 将浏览器请求代理到 OpenClaw 网关（localhost:18789），提供 TLS 终止和 CORS 响应头 |
| `openshell forward service` | 18789 | gRPC 隧道，连接 WSL2:18789 与 openshell-sandbox 容器中的 OpenClaw 隔离命名空间 |
| `openshell-sandbox` 容器 | 内部端口 | 运行 OpenClaw 智能体运行时、Squid 出站代理和用于推理的 openshell_router |
