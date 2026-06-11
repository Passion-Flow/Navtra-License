# 前端架构设计：Forge（forge-web）

> 第二步设计文档 5/6。约定来源：`Project-Docs/01-Frontend/{overview,tech-stack,browser-compatibility,performance-budget}.md` + `00-Global/{i18n,accessibility}.md`。
> forge-web = 厂商内部管理端（SPA），无前台业务端、无 License 激活锁定页（Forge 是签发方）。

## 1. 技术栈
- **React 18 + TypeScript + Vite**（SPA，内部工具）。
- **Tailwind CSS + shadcn/ui**（组件拷进仓库，design token 集中 Tailwind config + CSS 变量）。
- **TanStack Query v5**（所有服务端数据/缓存/重试/loading；禁手写 useEffect+fetch）。
- **React Router v6**（data-router，loader/action）。
- 客户端状态 React Context + useState（>5 个再上 Zustand）；服务端数据绝不进 Context。
- 校验 Zod（与后端 Pydantic 同源 JSON Schema 生成）；表单 react-hook-form + zodResolver。
- 依赖精确版本（无 `^`/`~`），lockfile 提交；私有交付无公网 CDN（字体/图标本地化）。

## 2. 路由结构（URL 路径式 i18n）
```
/                         → 探测 Accept-Language → 302 /<lang>/
/:lang(zh|en)/login
/:lang/reset-password
/:lang/dashboard
/:lang/products            （列表 + 新建/编辑/删除）
/:lang/customers
/:lang/issue               （签发：在线 / 离线 双 Tab）
/:lang/licenses            （列表 + 详情 + 吊销/续期/替换/删除）
/:lang/licenses/:id
/:lang/audit-logs          （Super Admin / Auditor）
/:lang/settings/keys       （签名密钥；私钥不回显）
/:lang/settings/login
/:lang/settings/password-policy
/:lang/settings/2fa
/:lang/settings/email
/:lang/settings/crl
/:lang/account/security    （个人 2FA / 改密）
```
- `:lang` 贯穿所有子路由；语言切换 = 重写 URL 前缀（可书签可分享，URL 为唯一源）。
- 路由级 + 组件级懒加载；长列表虚拟化（react-window）。

## 3. 状态管理
- Server state：TanStack Query（License 列表、审计、产品、客户等）。
- Client state：当前语言（URL）、当前用户 + 权限（登录返回 + `/me/permissions`，Context）、UI 临时态（useState）。

## 4. 关键页面线框

**签发页（/issue）** —— 核心：
```
┌ 签发 License ───────────────────────────────┐
│ [ 在线 ] [ 离线 ]   ← Tab                    │
│ 客户  [下拉▼]      产品 [下拉▼]              │
│ 有效期 [1月/3月/6月/1年/3年/5年/永久 ▼]      │
│ 订阅 [Enterprise▼]  Seat上限 [ 1 ]（仅在线）│
│ 离线专属: 部署ID [____________ 粘贴]         │
│ features ☑..  quotas {..}                    │
│ [ 生成 License ]                             │
├─ 结果 ──────────────────────────────────────┤
│ 在线: 短码  0ef3...db6d1   [复制]            │
│ 离线: eyJ1d...（长）       [复制] [下载.forge]│
│ 有效期 2026-.. ~ 2027-..                      │
└─────────────────────────────────────────────┘
```

**License 列表（/licenses）**：表格（License ID 脱敏 `<前4>****<后4> Show` / 客户 / 产品 / mode / 状态点 / 有效期+倒计时徽标 / seat 用量 / `···`菜单[吊销/续期/替换/删除]）+ 过滤栏（客户/产品/状态/mode/Reset ×）+ 分页（`X items found` / Rows per page / Page X of Y）。

**审计日志（/audit-logs）**：Time / Operator(+角色后缀) / Action / Resource Type / Resource Name；过滤（操作类型/资源类型/资源ID/日期范围/Reset）；`Download Logs` CSV；默认 50/页；仅 Super Admin/Auditor。

**设置·密钥（/settings/keys）**：密钥列表（key_id 脱敏 / alg / 状态）；操作 [轮换][导出公钥]；**私钥永不显示**；无"生成密钥"显式按钮（密钥管理隐式）。

## 5. 主题 / Branding
- §11.1 不做白标；用 shadcn/ui 默认 + Forge 品牌色 token；支持暗黑/高对比；动画 200–300ms ease-out。

## 6. 浏览器兼容
- 最低 Chrome90/FF88/Safari14/Edge90 + 国内 360/搜狗/QQ(Chromium90)；IE11 不支持。
- 最小宽 **1024px**（<1024 显"请用更大屏"页，不破版）；断点 lg/xl/2xl。
- **5 档缩放 100/125/150/175/200% 全测**（rem + clamp，不锁 viewport scale）；DPR 1x/2x/3x（SVG 图标优先）。
- Playwright CI 矩阵：chromium/firefox/webkit × 1024/1280/1920 × zoom 1.0/1.5/2.0 × DPR 1/2。

## 7. 性能预算
- Lighthouse Performance ≥90 / A11y ≥95 / Best Practices ≥95（CI 阻塞）。
- Web Vitals：LCP ≤2.5s / INP ≤200ms / CLS ≤0.1；`web-vitals.js` → OTel。
- Bundle（gzip）：初始 JS ≤200KB / CSS ≤50KB / 单 chunk ≤500KB；hash 命名资源。

## 8. 可访问性
- WCAG 2.1 AA：键盘全可达 + Focus 可见 + Skip Link；语义 HTML + ARIA；对比度 4.5:1；不只靠颜色传信息；200% 缩放可用；表单 label + aria-invalid/describedby；`prefers-reduced-motion`；CI axe-core。

## 9. i18n 实现
- 双语 zh-CN(fallback) + en；文案走资源文件（`locales/<lang>/*.json`），禁组件内裸串。
- **§4.6 三铁律全守**：① 语言切换用**下拉组件**（非 toggle）；② 后端回 **code** 前端按 code 翻译（错误/状态/提示）；③ **原生控件文案自定义组件包装**（离线签发的"粘贴部署ID"框、`.forge` 文件下载、确认弹窗等都用自渲染组件，禁裸 `<input type=file>`/`alert`）。
- 错误码 → `locales/<lang>/errors.json`（CI 由 `forge-shared/error-codes.yaml` 同步）。
- 时区后端 UTC、前端按用户设置渲染（默认 Asia/Shanghai）；数字/货币 `Intl.*`。
