# 发布到 GitHub（新手版）

## 一、注册与建仓库

1. 打开 https://github.com ，注册账号（邮箱要能收验证邮件）；
2. 右上角 `+` → **New repository**；
3. 填写：
   - Repository name：`cyberbadge`（可换）
   - 选 **Public**
   - **不要**勾 "Add a README file"（仓库里已经有了）
4. 点 **Create repository**，会看到一行 `git@github.com:你的用户名/cyberbadge.git`。

## 二、两种授权方式

### 方式 A：SSH 密钥（推荐，不共享密码/token）

1. 把下面这把公钥加到 GitHub：
   - 复制公钥全文（一整行，`ssh-ed25519 ...` 开头）；
   - GitHub → 右上头像 → **Settings** → 左侧 **SSH and GPG keys** → **New SSH key**；
   - Title 随便写（如 `cyberbadge deploy`），Key 粘贴，保存。

2. 我这边执行推送（等同你本机 `git push`）：
   ```bash
   git remote add origin git@github.com:<你的用户名>/cyberbadge.git
   git push -u origin main
   ```

### 方式 B：个人访问令牌（PAT）

如果 SSH 被网络挡住，可以建一个 Fine-grained token（只给 `repo` 权限），用 HTTPS 推送，用完随时在 GitHub 设置里吊销。**不要把 token 提交进仓库**。

## 三、日常会用到的命令

| 命令 | 作用 |
|---|---|
| `git status` | 看哪些文件改了 |
| `git add -A` | 把改动加入暂存区 |
| `git commit -m "feat: 说明"` | 提交到本地历史 |
| `git push` | 推到 GitHub |
| `git log --oneline` | 看提交记录 |

## 四、之后可以做的事

- **Issues**：记录想法与 bug；
- **Releases**：打 tag 发布版本；
- **README**：放演示 GIF/截图；
- **Actions**：自动跑测试、自动构建（后面再加）。
