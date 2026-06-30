"""
Exchange OWA (Outlook Web App) 选择器集中管理。
针对 https://mail.hengtiansoft.com/owa/ 的 DOM 结构。

原则：
1. 优先使用 role / aria-label 等语义属性（OWA 用 React 渲染，class 名动态生成）
2. 每个元素配置多级回退选择器
3. 中文 + 英文界面兼容
"""


class OWASelectors:
    """OWA 页面选择器配置。"""

    # ===== 邮件列表区域 =====
    # 邮件列表容器
    MAIL_LIST = [
        'div[role="listbox"][aria-label*="邮件"]',
        'div[role="listbox"][aria-label*="Message"]',
        'div[role="listbox"]',
        'div[aria-label*="邮件列表"]',
        'div[aria-label*="message list"]',
        'div.ms-FocusZone[role="listbox"]',            # OWA 旧版
    ]

    # 单封邮件条目（列表中的每一项）
    MAIL_ITEM = [
        'div[role="option"]',
        'div[role="listbox"] div[role="option"]',
        'div[role="listbox"] > div[role="listitem"]',
        'div[data-convid]',                             # 部分版本有 conversation ID
        'div.ms-List-cell',                             # OWA 旧版
    ]

    # ===== 邮件详情区域 =====
    # 邮件主题（详情页中）
    MAIL_SUBJECT = [
        'div[role="heading"][aria-level="1"]',
        'div[role="heading"][aria-level="2"]',
        'h1[class*="subject"]',
        'span[class*="Subject"]',
        'div[aria-label*="主题"]',
        'div[aria-label*="Subject"]',
    ]

    # 邮件正文容器（多种选择器，OWA 版本不同 DOM 结构不同）
    MAIL_BODY = [
        'div[role="document"]',
        'div[aria-label*="邮件正文"]',
        'div[aria-label*="message body"]',
        'div[aria-label*="Body"]',
        'div[class*="ReadingPane"]',
        'div[class*="ItemBody"]',
        'div[class*="ContentWell"]',
        'div[class*="MessageContent"]',
        'div[class*="BodyContainer"]',
        'div[class*="mailbody"]',
        'div[class*="MailBody"]',
        # OWA 新版可能用这些
        'div[data-app="mail"] div[class*="Body"]',
        'div[class*="ReadingPaneContainer"]',
        # 邮件详情区域的 contenteditable
        'div[contenteditable="true"][class*="Body"]',
        # iframe（某些 OWA 版本）
        'iframe[id*="editor"]',
        'iframe[name*="body"]',
    ]

    # 发件人信息（邮件详情页）
    # 注意：OWA 通常只显示发件人名字，邮箱在 title/aria-label 属性中
    MAIL_SENDER = [
        'span[class*="EmailAddress"]',
        'span[role="heading"][aria-level="2"]',
        'div[aria-label*="发件人"]',
        'div[aria-label*="From"]',
        'span[class*="Sender"]',
        'div[class*="Persona"] span[class*="EmailAddress"]',
        # 邮件详情页发件人区域
        'span[class*="Sender"]',
        'div[class*="ReadingPane"] span[class*="Persona"]',
        # 列表中的发件人（含 title 属性可能有邮箱）
        'div[role="option"] span[class*="Sender"]',
        'div[data-convid] span[class*="Sender"]',
    ]

    # 发件人邮箱（可能藏在 title / aria-label 属性中）
    MAIL_SENDER_EMAIL_ATTR = [
        # title 属性常含 "姓名 <email@example.com>"
        'span[class*="Sender"][title]',
        'span[class*="Persona"][title]',
        'div[class*="Persona"][title]',
        # aria-label 属性
        'span[aria-label*="@"]',
        'div[aria-label*="@"]',
        # email 格式的文本
        'span[class*="EmailAddress"]',
    ]

    # 未读邮件计数（用于快速检测新邮件）
    UNREAD_COUNT = [
        'span[class*="unreadCount"]',
        'span[class*="UnreadCount"]',
        'div[aria-label*="未读"]',
        'div[aria-label*="unread" i]',
        'span[class*="folderCount"]',
        # 收件箱文件夹旁的未读数字
        'div[role="treeitem"][aria-label*="收件箱"] span',
        'div[role="treeitem"][aria-label*="Inbox"] span',
    ]

    # ===== 回复操作区域 =====
    # 回复按钮（点击后会弹出回复操作菜单：答复/全部答复/转发）
    REPLY_BUTTON = [
        'button[aria-label*="回复"]',
        'button[aria-label*="Reply"]',
        'button[title*="回复"]',
        'button[title*="Reply"]',
        'div[role="button"][aria-label*="回复"]',
        'div[role="button"][aria-label*="Reply"]',
        'button.ms-Button[aria-label*="Reply"]',
        # OWA 工具栏中的回复按钮图标
        'button[aria-label*="Respond"]',
        'div[role="button"][aria-label*="Respond"]',
        'button[aria-label*="响应"]',
        'div[role="button"][aria-label*="响应"]',
    ]

    # 答复选项（点击回复按钮后弹出的菜单中的"答复"选项）
    # OWA 点击回复后会弹出菜单：答复 / 全部答复 / 转发
    REPLY_REPLY_OPTION = [
        # 菜单项
        'button[aria-label*="答复"]',
        'button[aria-label*="Reply"]',
        'div[role="menuitem"][aria-label*="答复"]',
        'div[role="menuitem"][aria-label*="Reply"]',
        'div[role="menuitemradio"][aria-label*="答复"]',
        'div[role="menuitemradio"][aria-label*="Reply"]',
        'li[role="menuitem"]:has-text("答复")',
        'li[role="menuitem"]:has-text("Reply")',
        'button:has-text("答复")',
        'button:has-text("Reply")',
        # OWA 可能用 class
        'div[class*="ContextualMenuItem"]:has-text("答复")',
        'div[class*="ContextualMenuItem"]:has-text("Reply")',
        'div[class*="menuItem"]:has-text("答复")',
        'div[class*="menuItem"]:has-text("Reply")',
    ]

    # 全部答复选项（备用，如果只需要答复发件人用上面的）
    REPLY_ALL_OPTION = [
        'button[aria-label*="全部答复"]',
        'button[aria-label*="Reply all"]',
        'button[aria-label*="Reply All"]',
        'div[role="menuitem"][aria-label*="全部答复"]',
        'div[role="menuitem"][aria-label*="Reply all"]',
        'li[role="menuitem"]:has-text("全部答复")',
        'li[role="menuitem"]:has-text("Reply all")',
        'button:has-text("全部答复")',
        'button:has-text("Reply all")',
    ]

    # 回复输入框（contenteditable div）
    REPLY_INPUT = [
        'div[role="textbox"][contenteditable="true"]',
        'div[contenteditable="true"][aria-label*="邮件"]',
        'div[contenteditable="true"][aria-label*="message"]',
        'div[contenteditable="true"][aria-label*="Body"]',
        'div[class*="Editor"] div[contenteditable="true"]',
        'iframe[id*="editor"]',                         # 某些旧版用 iframe
    ]

    # 发送按钮
    SEND_BUTTON = [
        'button[aria-label*="发送"]',
        'button[aria-label*="Send"]',
        'button[title*="发送"]',
        'button[title*="Send"]',
        'button[class*="Send"]',
        'div[role="button"][aria-label*="发送"]',
        'div[role="button"][aria-label*="Send"]',
    ]

    # ===== 其他 =====
    # 关闭邮件详情 / 返回列表按钮
    CLOSE_BUTTON = [
        'button[aria-label*="关闭"]',
        'button[aria-label*="Close"]',
        'button[aria-label*="返回"]',
        'button[aria-label*="Back"]',
        'button[title*="关闭"]',
    ]

    # 收件箱文件夹（侧边栏导航）
    INBOX_FOLDER = [
        'div[role="treeitem"][aria-label*="收件箱"]',
        'div[role="treeitem"][aria-label*="Inbox"]',
        'div[class*="Inbox"]',
    ]

    # 新邮件提示（OWA 有时弹出新邮件通知）
    NEW_MAIL_NOTIFICATION = [
        'div[class*="Notification"]',
        'div[role="alert"]',
    ]

    # 登录后特征元素（用于判断是否已登录）
    LOGGED_IN_INDICATORS = [
        'div[role="navigation"]',
        'div[class*="AppBar"]',
        'div[aria-label*="导航"]',
        'div[class*="OwaShell"]',
    ]

    # ===== 登录表单元素 =====
    # 用户名输入框（OWA 标准登录页）
    USERNAME_INPUT = [
        'input[name="username"]',
        'input[id="username"]',
        'input[autocomplete="username"]',
        'input[type="email"]',
        'input[type="text"][name*="user" i]',
        'input[aria-label*="用户名"]',
        'input[aria-label*="User name" i]',
        'input[aria-label*="Email" i]',
        'input[placeholder*="用户名"]',
        'input[placeholder*="User name" i]',
        'input[placeholder*="邮箱"]',
    ]

    # 密码输入框
    PASSWORD_INPUT = [
        'input[name="password"]',
        'input[id="password"]',
        'input[type="password"]',
        'input[autocomplete="current-password"]',
        'input[aria-label*="密码"]',
        'input[aria-label*="Password" i]',
        'input[placeholder*="密码"]',
        'input[placeholder*="Password" i]',
    ]

    # 登录/提交按钮
    SIGN_IN_BUTTON = [
        'button[type="submit"]',
        'input[type="submit"]',
        'button[id*="signIn" i]',
        'button[class*="signIn" i]',
        'button[aria-label*="登录"]',
        'button[aria-label*="Sign in" i]',
        'button[aria-label*="登入"]',
        'button:has-text("登录")',
        'button:has-text("登 入")',
        'button:has-text("Sign in")',
        'div[role="button"][aria-label*="登录"]',
        'div[role="button"][aria-label*="Sign in" i]',
    ]

    # "下一步"按钮（分步登录：先输用户名，再输密码）
    NEXT_BUTTON = [
        'button[type="submit"]',
        'button[id*="next" i]',
        'button[class*="next" i]',
        'button[aria-label*="下一步"]',
        'button[aria-label*="Next" i]',
        'button:has-text("下一步")',
        'button:has-text("Next")',
    ]

    # "保持登录状态"提示的"是"按钮
    STAY_SIGNED_IN_YES = [
        'button[id*="dontShow" i]',
        'button:has-text("是")',
        'button:has-text("Yes")',
        'button:has-text("Don\'t show this again")',
        'input[type="submit"][value*="是"]',
        'input[type="submit"][value*="Yes"]',
    ]

    # 二次验证 (MFA) 检测指示器 —— 检测到这些元素表示进入 MFA 流程
    MFA_INDICATORS = [
        'div[id*="idDiv_SAOTCS_Proofs"]',                 # Microsoft 默认 MFA 页
        'div[class*="multi-factor"]',
        'div:has-text("验证你的身份")',
        'div:has-text("Verify your identity")',
        'div:has-text("输入验证码")',
        'div:has-text("Enter code")',
        'div:has-text("approve the request")',
        'div:has-text("审批登录请求")',
        'input[name*="otc" i]',                            # 一次性验证码输入框
        'input[autocomplete*="one-time-code"]',
        'img[alt*="Authenticator"]',
    ]

    # 登录错误提示元素
    LOGIN_ERROR_INDICATORS = [
        'div[id*="error" i][class*="error" i]',
        'div[class*="error-message"]',
        'span[id="errorText"]',
        'div[role="alert"]:has-text("密码")',
        'div[role="alert"]:has-text("password")',
        'div:has-text("帐户或密码不正确")',
        'div:has-text("incorrect")',
        'div:has-text("无效")',
        'div:has-text("locked")',
        'div:has-text("已锁定")',
    ]

    # ===== OWA 运行时弹窗/提示 =====
    # 存储容量警告弹窗（"即将超过邮箱的存储限制..."）
    # 注意：放宽匹配，不强制 role="dialog"，OWA 弹窗可能用自定义 div
    STORAGE_WARNING_POPUP = [
        'div:has-text("存储限制")',
        'div:has-text("即将超过")',
        'div:has-text("删除一些邮件")',
        'div:has-text("storage limit")',
        'div:has-text("delete some messages")',
        'div:has-text("邮箱存储")',
        'div:has-text("邮箱空间")',
        # OWA 常见 class
        'div[class*="Dialog"][class*="Visible"]',
        'div[class*="dialog"][class*="visible"]',
    ]

    # 弹窗的确认/确定按钮（通用）
    POPUP_CONFIRM_BUTTON = [
        'button:has-text("确定")',
        'button:has-text("确 定")',
        'button:has-text("OK")',
        'button:has-text("关闭")',
        'button:has-text("Close")',
        'button:has-text("我知道了")',
        'button:has-text("知道了")',
        'button:has-text("取消")',         # 有些弹窗只能点取消关闭
        'button:has-text("Dismiss")',
        'button[aria-label*="确定"]',
        'button[aria-label*="OK" i]',
        'button[aria-label*="关闭"]',
        'button[aria-label*="Close" i]',
        'button[aria-label*="Dismiss"]',
        'button[type="submit"][value*="确定"]',
        'input[type="submit"][value*="确定"]',
        'input[type="button"][value*="确定"]',
        'input[type="button"][value*="OK"]',
    ]
