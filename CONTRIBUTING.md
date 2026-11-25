# 贡献指南

本指南适用于 NeMoClaw 中文 DLI 课程仓库中的内容、构建工具和验证工具，不适用于 NemoClaw 产品本身、其 launchable 或产品运行时。公开发布状态由 [`RELEASE_STATUS.json`](RELEASE_STATUS.json) 记录；提交贡献不代表获得发布或部署权限。

## 两种贡献方式

### 提交问题或建议

如果你有相关经验，但尚未准备好可供合并的补丁，请提交结构化 Issue，说明受影响的内容、实际行为、预期结果和支持证据。问题描述规范见 [`docs/issue_standards.md`](docs/issue_standards.md)。

当 Discussions 获准启用后，可在那里提出开放性问题或早期想法。安全漏洞不得通过公开 Issue 或 Discussion 报告，请遵循 [`SECURITY.md`](SECURITY.md) 的私密报告流程。

### 直接提交补丁

如果你能完成变更、验证和评审流程，可以提交合并请求（MR/PR）。发布边界见 [`docs/release_playbook.md`](docs/release_playbook.md)。补丁应同时更新源文件和声明的影响范围内的文件；对于可能再次出现的问题，应补充验证器或回归测试。

满足关联 Issue 的全部验收条件时，使用 `Closes #N`。只完成部分工作时，使用 `Addresses #N`，并在 `Remaining issue work` 部分列出剩余条件。交接前应逐项核对最终差异、证据和 Issue 验收清单。

无论补丁由人工还是智能体生成，都不能仅凭来源或某条本地命令通过就视为可信。必须在提交的确切 commit 上运行所需 CI，记录证据和剩余风险，明确评审责任，并满足受保护分支规则。发布和部署写入需要单独授权。

MR 顶部应保留紧凑的提交约定。GitLab 的 CI 只能读取描述开头的一定范围，请保留模板中 Summary 到 Out of scope 的顺序，并将必需标题置于前 2,700 个字符内；详细说明放在其后。

## 开始之前

先阅读 [`AGENTS.md`](AGENTS.md)。各源目录的 `SKILL.html` 包含机器可读的 `skill-meta` 元数据，格式见 [`SKILL_CONTRACT.md`](SKILL_CONTRACT.md)。根目录 `SKILL.html` 和验证套件定义内容要求。

新增目录时也要新增对应的引导文件。运行 `python3 scripts/skills/gen_directory_beacons.py`，并检查生成的摘要和链接。CI 根据受跟踪及拟新增文件推导完整目录集合，不提供豁免机制。

本仓库面向中文课程。英文内容是含义和可执行结构的参考，但不应将英文措辞检查直接套用于中文文档。不要仅因英文表述变化而自动改写中文。中文术语、表达和教学说明由中文评审者确认。共享运行时、资源和数据不应为了翻译而复制；可执行结构必须保持等价，面向学习者的文字可以本地化。有关工具说明见 [`scripts/translate/SKILL.html`](scripts/translate/SKILL.html)，课程说明写作规范见 [`docs/course-prose-style.md`](docs/course-prose-style.md)。页面级决策记录在 Issue 或 MR 中。

## 结构化提交流程

1. 从干净分支开始，一次只处理一个明确的变更主题。
2. 编辑前先阅读相关 Issue 或 MR。
3. 按 [`DCO.md`](DCO.md) 要求为每个 commit 添加来源签署。
4. 更新源文件及声明影响范围内的文件。
5. 遵守 [`web/nemoclaw/COURSE_CANON.md`](web/nemoclaw/COURSE_CANON.md) 中课程标题、摘要和目标的约定；翻译应保持原意。
6. 对可能复发的问题新增或更新验证器及测试。
7. 运行下述验证流程。
8. 提交 MR/PR，写明 Issue 关系和验证结果。

使用 `git commit --signoff` 添加与作者一致的 `Signed-off-by` 尾注。CI 会检查拟提交范围内的全部 commit。失败时按 `DCO.md` 修复，不得抹去其他贡献者的作者信息，也不得将签署视为提交第三方材料的许可。

对于目标分支本身尚未合并的堆叠合并请求，应保留原始签署 commit。不要使用平台的 squash 或 merge 按钮，因为自动生成的 commit 不会继承 DCO 尾注，可能导致父请求的完整范围检查失败。按 [`DCO.md`](DCO.md) 采用由维护者负责的快进或明确的 rebase/cherry-pick 流程。

### 贡献者署名与本地化责任

集成他人的工作时保留签署和作者信息。学习者可见的翻译或其他重要贡献合入时，在 [`CHANGELOG.md`](CHANGELOG.md) 的 Unreleased 部分公开致谢，但不要加入私人联系方式。

英文参考定义原意和可执行结构，中文表达由中文贡献者及评审者负责。只影响英文措辞而不改变含义的修改，不应强制改写中文 HTML。中文内容修改需要具备相应语言能力的人评审，并在 MR 中使用公开署名记录：

```text
Localization-Review: zh-CN=Public Reviewer Name
```

## 安装本地钩子

```bash
bash scripts/build/install-hooks.sh
```

脚本会解析真实 Git hooks 目录（包括关联 worktree），并安装：

- `pre-commit`：检查受保护分支写入、贡献者本地文件与敏感内容边界、贡献约定、文件损坏、canvas HTML 及页面运行时基本功能。
- `pre-push`：检查分支落后、完整历史签署和内容、发布提醒，并运行感知变更范围的统一 ship 检查。只有完全相同且干净的本地成功结果才可复用；所需 CI 始终在提交的 commit 上重新执行。

本地钩子仅提供提前反馈；必需的 CI 和受保护引用规则始终具有约束力。人工评审用于明确责任，不能替代有效的控制措施。未解决的发布风险必须保持阻断，直至防护措施得到验证，或受保护的发布检查能获取授权决定并与确切构建产物进行比对。目前该自动比对尚未实现，因此单有决定记录不能解除发布阻断。

## 推送前验证

```bash
python3 scripts/validation/release_gate.py --tier fast --no-write --changed-since nvdli/main --jobs 4
```

推送提案前再运行一次：

```bash
python3 scripts/validation/release_gate.py --tier ship --no-write --changed-since nvdli/main --jobs 4
```

上述 `nvdli/main` 是本地发布目标的远程跟踪引用；若远程别名不同，请替换为实际目标基线。发布候选版本应省略 `--changed-since`，执行完整检查。

统一检查始终审计完整当前文件树，仅跳过不受变更影响的检测器变异测试。新增、删除、改名、复制或未归类的路径会选择完整测试矩阵，不受目录或扩展名限制。各组成命令仅用于定向调试，证据映射见 [`docs/release-test-plan.md`](docs/release-test-plan.md)。

Python 验证器测试使用标准库 `unittest`，JavaScript 测试使用 Node 内置 `node:test`。将测试放在 `tests/validation` 中；统一检查在测试变更时和每个发布候选版本上自动发现它们，不必修改注册表。不要在共享 fast/ship 输出中硬编码固定测试总数。

涉及浏览器或 Studio 时，还需运行 [`docs/lab_runtime_testing.md`](docs/lab_runtime_testing.md) 中的浏览器测试。

## 编写约定

完整约定见根目录 `SKILL.html` 的 `skill-meta`，可运行 `python3 scripts/validation/tenets.py` 检查。

- 原位修改源内容；临时材料放在工作区临时目录，且不得提交。
- 撰写说明时避免使用英文长破折号，优先重写句子。
- `web/` 保持浏览器端边界；本地部署的服务要求应在启动指南中明确，不应隐含在浏览器代码中。
- 主机上的 Python、Node.js 和 Chromium 用于仓库验证；外部隔离环境由操作者负责。
- 不得提交实验生成的运行时输出、缓存或 `public/` Pages 构建目录。

### 学习者可见代码

可运行单元是教学内容，应将传输和渲染等实现细节封装在有明确名称的辅助函数中。

- 可编辑 RunCell 不超过 120 个非空行；会话、兼容和底层实现放入辅助函数，单元只展示接口和结果。
- 使用描述性名称；单字母仅用于常见坐标或简短循环下标。
- 每行表达一个逻辑语句，不用密集的多语句行代替清晰结构。
- 返回结构化结果，使用 `helpers.log` 展示过程和证据；需要时同时保留返回值与日志。
- 长操作使用 RunCell 或 CanvasFlow 的 Stop 信号；优先使用 `helpers.delay(ms)`，并将单元信号与超时 AbortController 结合。
- 在有助于理解的位置保留清晰标注且默认注释的 `helpers.log.json(...)`、`helpers.log.details(...)` 或替代赋值，便于学习者自行启用。
- 在单元开头明确跨单元 `state` 的输入和输出，检查前置条件，并返回本步状态写入的简要摘要。

`python3 -m unittest discover -v -s tests/validation` 对规则进行变异测试；常规 `cell_audit.py` 检查会对所有编号课程页面执行其中可确定性验证的部分。

## 贡献条款

本仓库采用双许可证。NVIDIA 编写的源代码适用 Apache-2.0；NVIDIA 编写的文档、skills 和资源适用 CC-BY-4.0。混合文档与代码的文件同时适用两组条款。第三方材料保留原许可证，不作重新许可。详见 [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md)、[`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) 和包含两份完整许可证正文的 [`LICENSE`](LICENSE)。

除非明确将提交标记为 `Not a Contribution`，有意提交以纳入本项目的贡献均按相同条款提供：源代码适用 Apache-2.0，文档、skills 和资源适用 CC-BY-4.0，混合文件同时适用两组条款。

无需另行签署贡献者许可协议（CLA）。

### 为贡献签署来源证明

每个 commit 必须包含 Developer Certificate of Origin（DCO）来源签署。签署表示你自行创作了该贡献，或具有按本项目许可证提交它的充分权利。**不接受缺少签署的 commit。**

```bash
git commit -s -m "Describe your change"
```

commit 消息将包含：

```text
Signed-off-by: Your Name <your@email.com>
```

请使用真实姓名和你控制的邮箱。签署记录来源及提交权利，不转移版权，也不能替代来源证明、许可证审核、测试或所需人工评审。

对于尚未发布的 commit，可用 `git commit --amend --signoff` 修复。多个 commit 应有意逐个 rebase 并修复。不要擅自重写他人已基于其开展工作的历史，应追加修复或先协调。不得为机器人或其他贡献者伪造签署。详见 [`DCO.md`](DCO.md)。

以下保留未经修改的 DCO 原文，避免翻译改变认证内容：

```text
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.

Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

不得提交无权贡献的材料。第三方文字、图片、数据集、模型产物、复制示例、缓存网页和生成资源在提交前都需确认来源及许可证处理方式。规则见 [`scripts/compliance/docs/vendor_policy.md`](scripts/compliance/docs/vendor_policy.md)，必需检查为：

```bash
python3 scripts/compliance/source_gate.py
```
